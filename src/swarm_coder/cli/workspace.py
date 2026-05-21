import os
from typing import Optional
from src.swarm_coder.config import config
from src.swarm_coder.core.models import ImplementationPlan
from src.swarm_coder.cli.ui import get_user_input

async def setup_workspace() -> Optional[str]:
    """
    Handles workspace path input and initialization.
    Returns the workspace path if successful, None otherwise.
    """
    workspace_path = await get_user_input("Enter the target workspace path for code generation: ")
    if not os.path.exists(workspace_path):
        create_choice = await get_user_input(f"Path '{workspace_path}' does not exist. Create it? (yes/no): ")
        if create_choice.lower() == 'yes':
            try:
                os.makedirs(workspace_path, exist_ok=True)
                print(f"Created workspace at: {workspace_path}")
            except Exception as e:
                print(f"Error creating workspace '{workspace_path}': {e}")
                return None
        else:
            print("Exiting.")
            return None
            
    config.set_workspace_root(workspace_path)
    return workspace_path

async def load_or_resume_plan(workspace_path: str) -> Optional[ImplementationPlan]:
    """
    Checks for an existing plan.json and asks the user if they want to resume.
    """
    plan_file_path = os.path.join(workspace_path, "plan.json")
    if os.path.exists(plan_file_path):
        resume = await get_user_input(f"Existing plan found at {plan_file_path}. Resume coding from it? (yes/no): ")
        if resume.lower() == 'yes':
            try:
                with open(plan_file_path, 'r', encoding='utf-8') as f:
                    plan = ImplementationPlan.model_validate_json(f.read())
                print("\n[Resuming Implementation Plan]")
                for i, task in enumerate(plan.tasks):
                    status = "[Done]" if task.completed else "[Pending]"
                    print(f"  {i+1}. {status} {task.filename}: {task.instruction}")
                return plan
            except Exception as e:
                print(f"Error loading existing plan: {e}")
    return None

def save_plan(workspace_path: str, plan: ImplementationPlan) -> None:
    """
    Saves the implementation plan to plan.json.
    """
    plan_file_path = os.path.join(workspace_path, "plan.json")
    try:
        with open(plan_file_path, 'w', encoding='utf-8') as f:
            f.write(plan.model_dump_json(indent=2))
    except Exception as e:
        print(f"\n[Warning: Failed to save plan: {e}]")
