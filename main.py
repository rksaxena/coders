import asyncio
from src.swarm_coder.cli.main import async_main

if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nExiting...")
