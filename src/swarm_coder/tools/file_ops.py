import os
from typing import List

from src.swarm_coder.config.config import config
from src.swarm_coder.core.logger import logger
from src.swarm_coder.tools.indexer import ContextRetriever


async def search_codebase(query: str, top_k: int = 3) -> str:
    """
    Searches the local codebase for semantically relevant code snippets using LanceDB.
    Useful for finding where a specific feature, variable, or function is implemented.
    """
    if not config.workspace_root:
        return "Error: Workspace root not set."

    db_path = os.path.join(config.workspace_root, ".lancedb")
    if not os.path.exists(db_path):
        return (
            "Error: Codebase is not indexed. Cannot perform semantic search. "
            "Use list_files or read_file_content instead."
        )

    retriever = ContextRetriever(config.workspace_root)
    try:
        logger.info(f"Semantic Search Triggered: '{query}'")
        return await retriever.retrieve_context(query, top_k)
    except Exception as e:
        return f"Error during search: {str(e)}"


def read_file_content(file_path: str) -> str:
    """
    Reads the full content of a file within the workspace.
    """
    abs_path = config.get_abs_path(file_path)
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return (
            f"File not found: {abs_path}. You can create it using write_file_content."
        )
    except Exception as e:
        return f"Error reading file {abs_path}: {str(e)}"


def write_file_content(file_path: str, content: str) -> str:
    """
    Writes content to a file within the workspace, overwriting existing content.
    """
    abs_path = config.get_abs_path(file_path)
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {abs_path}"
    except Exception as e:
        return f"Error writing to file {abs_path}: {str(e)}"


def list_files(dir_path: str = ".") -> List[str]:
    """
    Lists all files in a directory within the workspace recursively.
    """
    abs_dir = config.get_abs_path(dir_path)
    if not os.path.exists(abs_dir):
        return []

    file_list = []
    for root, _, files in os.walk(abs_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, config.workspace_root)
            file_list.append(rel_path)
    return file_list
