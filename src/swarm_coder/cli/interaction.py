import json
from typing import Optional, Tuple
from google.adk.runners import Runner
from google.adk.models import LiteLlm
from google.genai import types
from src.swarm_coder.core.models import ImplementationPlan
from src.swarm_coder.cli.ui import console

async def run_agent_interaction(runner: Runner, message: str, is_planner: bool = True, retried: bool = False, session_id: Optional[str] = None) -> Tuple[Optional[ImplementationPlan], str]:
    """
    General agent interaction loop that prints tool calls and captures output.
    """
    user_id = "user"
    if session_id is None:
        session_id = "planning_session" if is_planner else "coding_session"
    
    plan: Optional[ImplementationPlan] = None
    response_text = ""
    
    message_content = types.Content(role="user", parts=[types.Part(text=message)])
    
    spinner_message = "Planner is thinking..." if is_planner else "Coder is generating..."
    status = console.status(spinner_message, spinner="dots")
    status.start()
    spinner_active = True

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message_content
        ):
            if spinner_active:
                status.stop()
                spinner_active = False
                
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text
                        if not is_planner: # Print coder's thoughts in real-time
                            print(part.text, end="", flush=True)
                    
                        if is_planner:
                            try:
                                text_content = part.text.strip()
                                if "```json" in text_content:
                                    text_content = text_content.split("```json")[1].split("```")[0]
                                elif "```" in text_content:
                                    text_content = text_content.split("```")[1].split("```")[0]
                                
                                parsed_json = json.loads(text_content.strip())
                                if "tasks" in parsed_json:
                                    plan = ImplementationPlan.model_validate(parsed_json)
                            except Exception as e: 
                                # print("\n[Debug] Failed to parse ImplementationPlan from planner response. Continuing to check for tool calls...")
                                # print(f"[Debug] Parsing error: {e}")
                                pass
                    
                    if is_planner and part.function_call:
                        if part.function_call.name in ["set_model_response", "ImplementationPlan"]:
                            plan = ImplementationPlan.model_validate(part.function_call.args)
                        elif isinstance(part.function_call.args, dict) and "tasks" in part.function_call.args:
                            plan = ImplementationPlan.model_validate(part.function_call.args)
    except Exception as e:
        if spinner_active:
            status.stop()
            spinner_active = False
            
        error_str = str(e).lower()
        if not retried and is_planner and any(x in error_str for x in ["503", "429", "500", "internal", "throttle"]):
            print(f"\n[Warning] CloudAPI error ({e}). Falling back to local ollama model: gemma4:26b...")
            runner.agent.model = LiteLlm(model="ollama/gemma4:26b")
            return await run_agent_interaction(runner, message, is_planner, retried=True)
        print(f"\n[Error] Agent interaction encountered an issue: {e}")
    
    if spinner_active:
        status.stop()
        spinner_active = False

    return plan, response_text
