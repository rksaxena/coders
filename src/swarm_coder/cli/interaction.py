import json
import os
import sys
from typing import Optional, Tuple

from google.adk.models import LiteLlm
from google.adk.runners import Runner
from google.genai import types

from src.swarm_coder.cli.ui import console
from src.swarm_coder.core.logger import logger
from src.swarm_coder.core.models import OrchestratorPlan


def _parse_plan_from_text(text: str) -> Optional[OrchestratorPlan]:
    try:
        text_content = text.strip()
        if "```json" in text_content:
            text_content = text_content.split("```json")[1].split("```")[0]
        elif "```" in text_content:
            text_content = text_content.split("```")[1].split("```")[0]

        parsed_json = json.loads(text_content.strip())
        if "tasks" in parsed_json:
            return OrchestratorPlan.model_validate(parsed_json)
    except Exception as e:
        if not isinstance(e, json.JSONDecodeError):
            logger.warning(f"Schema Validation Error in text output: {e}")
    return None


def _parse_plan_from_function_call(part) -> Optional[OrchestratorPlan]:
    call_name = part.function_call.name
    args = part.function_call.args
    args_dict = dict(args) if hasattr(args, "items") else args

    if call_name in ["set_model_response", "OrchestratorPlan"]:
        try:
            return OrchestratorPlan.model_validate(args_dict)
        except Exception as e:
            logger.warning(f"Schema Validation Error in function call: {e}")
    elif isinstance(args_dict, dict) and "tasks" in args_dict:
        try:
            return OrchestratorPlan.model_validate(args_dict)
        except Exception as e:
            logger.warning(f"Schema Validation Error in tool call args: {e}")
    else:
        logger.info(f"Planner is using tool: {call_name}")
    return None


async def run_agent_interaction(
    runner: Runner,
    message: str,
    is_planner: bool = True,
    retried: bool = False,
    session_id: Optional[str] = None,
) -> Tuple[Optional[OrchestratorPlan], str]:
    """
    General agent interaction loop that prints tool calls and captures output.
    """
    session_id = session_id or ("planning_session" if is_planner else "coding_session")

    plan: Optional[OrchestratorPlan] = None
    response_text = ""
    message_content = types.Content(role="user", parts=[types.Part(text=message)])

    spinner_message = (
        "Planner is thinking..." if is_planner else "Coder is generating..."
    )
    status = console.status(spinner_message, spinner="dots")
    status.start()
    spinner_active = True

    try:
        async for event in runner.run_async(
            user_id="user", session_id=session_id, new_message=message_content
        ):
            if spinner_active:
                status.stop()
                spinner_active = False

            if not (event.content and event.content.parts):
                continue

            for part in event.content.parts:
                if part.text:
                    response_text += part.text
                    if not is_planner:  # Print coder's thoughts in real-time
                        sys.stdout.write(part.text)
                        sys.stdout.flush()
                    elif not plan:
                        new_plan = _parse_plan_from_text(part.text)
                        if new_plan:
                            plan = new_plan

                if is_planner and part.function_call and not plan:
                    new_plan = _parse_plan_from_function_call(part)
                    if new_plan:
                        plan = new_plan

    except Exception as e:
        if spinner_active:
            status.stop()
            spinner_active = False

        error_str = str(e).lower()
        retry_triggers = ["503", "429", "500", "internal", "throttle"]
        if not retried and is_planner and any(x in error_str for x in retry_triggers):
            fallback_model = os.getenv("OLLAMA_PLANNER_MODEL", "qwen2.5-coder:7b")
            logger.warning(
                f"CloudAPI error ({e}). Falling back to local ollama model: "
                f"{fallback_model}..."
            )
            runner.agent.model = LiteLlm(model=f"ollama/{fallback_model}")
            return await run_agent_interaction(
                runner, message, is_planner, retried=True, session_id=session_id
            )
        logger.error(f"Agent interaction encountered an issue: {e}")

    if spinner_active:
        status.stop()
        spinner_active = False

    return plan, response_text
