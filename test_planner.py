import asyncio

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.swarm_coder.core.agents import get_planner_agent
from src.swarm_coder.core.logger import logger

load_dotenv()


async def main():
    """Run planner agent to output the implementation plan."""
    agent = get_planner_agent()
    # Modify instruction to skip discovery and output plan immediately
    agent.instruction = "You are Planner. Output the ImplementationPlan immediately."

    service = InMemorySessionService()
    runner = Runner(
        app_name="PlannerApp",
        agent=agent,
        session_service=service,
        auto_create_session=True,
    )

    msg = types.Content(
        role="user",
        parts=[
            types.Part(
                text="Output the implementation plan for hello.py with instruction "
                "'print hello world' and context 'entry point'."
            )
        ],
    )

    async for event in runner.run_async(
        user_id="user", session_id="test", new_message=msg
    ):
        if hasattr(event, "content") and event.content:
            if hasattr(event.content, "parts") and event.content.parts:
                for part in event.content.parts:
                    logger.info(f"PART: {part}")
                    if hasattr(part, "function_call") and part.function_call:
                        logger.info(f"FUNCTION_CALL: {part.function_call.name}")
                        logger.info(f"ARGS: {part.function_call.args}")


asyncio.run(main())
