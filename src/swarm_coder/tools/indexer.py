import os

import aiohttp

try:
    import lancedb
    import pyarrow as pa
except ImportError:
    lancedb = None
    pa = None

from typing import List

from src.swarm_coder.core.logger import logger


class CodeIndexer:
    def __init__(self, workspace_path: str, db_name: str = ".lancedb"):
        self.workspace_path = workspace_path
        self.db_path = os.path.join(workspace_path, db_name)
        self.model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        self.api_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434").rstrip(
            "/"
        )

    async def _get_embedding(self, text: str) -> List[float]:
        url = f"{self.api_base}/api/embeddings"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json={"model": self.model, "prompt": text}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("embedding", [])
                else:
                    logger.error(f"Failed to get embedding: {response.status}")
                return []

    def _chunk_content(self, content: str, max_chars: int = 1500) -> List[str]:
        # Semantic chunking by lines to prevent mid-word breaks
        chunks = []
        current_chunk = ""
        for line in content.splitlines(keepends=True):
            if len(current_chunk) + len(line) > max_chars and current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            current_chunk += line
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    def _gather_chunks(self) -> List[tuple]:
        ignore_dirs = {
            ".git",
            "__pycache__",
            "node_modules",
            "venv",
            ".venv",
            "env",
            ".lancedb",
        }
        valid_exts = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".html",
            ".css",
            ".json",
            ".md",
            ".txt",
            ".yml",
            ".yaml",
        }

        chunks_data = []
        for root, dirs, files in os.walk(self.workspace_path):
            dirs[:] = [
                d for d in dirs if d not in ignore_dirs and not d.startswith(".")
            ]
            for file in files:
                if any(file.endswith(ext) for ext in valid_exts):
                    f_path = os.path.join(root, file)
                    rel_path = os.path.relpath(f_path, self.workspace_path)
                    try:
                        with open(f_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            if content.strip():
                                for chunk in self._chunk_content(content):
                                    chunks_data.append((rel_path, chunk))
                    except Exception:
                        pass
        return chunks_data

    async def index_workspace(self) -> int:
        if not lancedb:
            raise ImportError(
                "Please install lancedb and pyarrow: "
                "pip install lancedb pyarrow aiohttp"
            )

        chunks_data = self._gather_chunks()

        if not chunks_data:
            return 0

        # 2. Get the first embedding to determine vector dimension dynamically
        first_rel_path, first_chunk = chunks_data[0]
        first_embedding = await self._get_embedding(first_chunk)
        if not first_embedding:
            raise Exception(
                f"Make sure Ollama is running and has the model '{self.model}'. "
                f"Try: ollama pull {self.model}"
            )

        dim = len(first_embedding)

        # 3. Setup LanceDB Table
        db = lancedb.connect(self.db_path)
        schema = pa.schema(
            [
                pa.field("vector", pa.list_(pa.float32(), dim)),
                pa.field("file_path", pa.string()),
                pa.field("content", pa.string()),
            ]
        )

        table_name = "codebase"
        if table_name in db.table_names():
            db.drop_table(table_name)
        table = db.create_table(table_name, schema=schema)

        # 4. Generate embeddings and populate table
        records = [
            {
                "vector": first_embedding,
                "file_path": first_rel_path,
                "content": first_chunk,
            }
        ]
        for rel_path, chunk in chunks_data[1:]:
            emb = await self._get_embedding(chunk)
            if emb:
                records.append({"vector": emb, "file_path": rel_path, "content": chunk})

        table.add(records)

        try:
            table.create_fts_index("content", replace=True)
        except Exception:
            logger.warning(
                "Could not create Full-Text Search index (sparse). "
                "For better accuracy (Hybrid Search), install the 'tantivy' "
                "package: pip install tantivy"
            )

        return len(records)

    async def index_file(self, f_path: str) -> int:
        """Indexes a single file dynamically and updates the LanceDB table."""
        if not lancedb or not os.path.exists(self.db_path):
            return 0

        rel_path = os.path.relpath(f_path, self.workspace_path)
        chunks_data = []
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    for chunk in self._chunk_content(content):
                        chunks_data.append((rel_path, chunk))
        except Exception:
            pass

        db = lancedb.connect(self.db_path)
        table_name = "codebase"

        if table_name not in db.table_names():
            return 0

        table = db.open_table(table_name)

        try:
            table.delete(f"file_path = '{rel_path}'")
        except Exception:
            pass

        if not chunks_data:
            return 0

        records = []
        for r_path, chunk in chunks_data:
            emb = await self._get_embedding(chunk)
            if emb:
                records.append({"vector": emb, "file_path": r_path, "content": chunk})

        if records:
            table.add(records)
            try:
                table.create_fts_index("content", replace=True)
            except Exception:
                pass

        return len(records)


class ContextRetriever:
    def __init__(self, workspace_path: str, db_name: str = ".lancedb"):
        self.indexer = CodeIndexer(workspace_path, db_name)
        self.db_path = os.path.join(workspace_path, db_name)

    async def retrieve_context(self, query: str, top_k: int = 3) -> str:
        if not lancedb:
            return "Context retrieval failed: lancedb not installed."

        query_embedding = await self.indexer._get_embedding(query)
        if not query_embedding:
            return "Context retrieval failed: could not generate embedding."

        db = lancedb.connect(self.db_path)
        if "codebase" not in db.table_names():
            return "No workspace context available (not indexed)."

        table = db.open_table("codebase")

        try:
            # Attempt Hybrid Search with Reciprocal Rank Fusion (RRF)
            from lancedb.rerankers import RRFReranker

            results = (
                table.search(query, query_type="hybrid")
                .vector(query_embedding)
                .rerank(reranker=RRFReranker())
                .limit(top_k)
                .to_list()
            )
        except Exception:
            # Fallback to pure Dense Vector Search if FTS index or Tantivy is missing
            results = table.search(query_embedding).limit(top_k).to_list()

        context_str = "--- RELEVANT WORKSPACE CONTEXT ---\n"
        for res in results:
            context_str += f"\nFile: {res['file_path']}\n```\n{res['content']}\n```\n"
        return context_str
