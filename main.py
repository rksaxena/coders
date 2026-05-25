import asyncio
from src.swarm_coder.cli.main import async_main
from src.swarm_coder.core.logger import logger

if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
