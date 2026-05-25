import asyncio

from src.swarm_coder.config.config import config
from src.swarm_coder.core.logger import logger
from src.swarm_coder.tools.file_ops import search_codebase


async def test_lancedb_search():
    # Mock the workspace initialization
    config.set_workspace_root(".")

    query = "How is the Orchestrator plan validated?"
    logger.info(f"Querying LanceDB for: '{query}'")

    results = await search_codebase(query, top_k=2)
    logger.info(results)


if __name__ == "__main__":
    asyncio.run(test_lancedb_search())
