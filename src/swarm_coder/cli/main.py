import os
import sys
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService

from src.swarm_coder.cli.workspace import setup_workspace, load_or_resume_plan
from src.swarm_coder.cli.phases import run_planning_phase, run_execution_phase
from src.swarm_coder.core.timing import profiler

# Load environment variables from .env file
load_dotenv()

def validate_environment() -> None:
    """
    Ensures necessary environment variables are set.
    """
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)
    
    if not os.getenv("OLLAMA_API_BASE"):
        os.environ["OLLAMA_API_BASE"] = "http://localhost:11434"

async def async_main() -> None:
    """
    Main interactive loop for the swarm coding agent.
    """
    validate_environment()
    
    print("--- Swarm Coding Agents Interactive CLI ---")
    
    workspace_path = await setup_workspace()
    if not workspace_path:
        return
            
    session_service = InMemorySessionService()
    
    plan = await load_or_resume_plan(workspace_path)
    
    if not plan:
        plan = await run_planning_phase(workspace_path, session_service)
        if not plan:
            return

    await run_execution_phase(workspace_path, plan, session_service)
    """
    while plan:
        has_pending_tasks = any(not task.completed for task in plan.tasks)
        if has_pending_tasks:
            await run_execution_phase(workspace_path, plan, session_service)
        
        new_plan = await run_reviewer_phase(workspace_path, plan, session_service)
        if new_plan and new_plan.tasks:
            plan = new_plan
            save_plan(workspace_path, plan)
        else:
            break
    """
    print(profiler.generate_report())
