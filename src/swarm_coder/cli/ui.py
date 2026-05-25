import asyncio
from rich.console import Console

console = Console()


async def get_user_input(prompt: str) -> str:
    """
    Asynchronously get input from the user.
    """
    return await asyncio.to_thread(input, prompt)
