import os
from typing import Optional

from src.swarm_coder.cli.ui import console, get_user_input
from src.swarm_coder.config.config import config
from src.swarm_coder.core.logger import logger
from src.swarm_coder.core.models import OrchestratorPlan, TaskStatus
from src.swarm_coder.tools.indexer import CodeIndexer


async def setup_workspace() -> Optional[str]:
    """
    Handles workspace path input and initialization.
    Returns the workspace path if successful, None otherwise.
    """
    workspace_path = await get_user_input(
        "Enter the target workspace path for code generation: "
    )
    if not os.path.exists(workspace_path):
        create_choice = await get_user_input(
            f"Path '{workspace_path}' does not exist. Create it? (yes/no): "
        )
        if create_choice.lower() == "yes":
            try:
                os.makedirs(workspace_path, exist_ok=True)
                logger.info(f"Created workspace at: {workspace_path}")
            except Exception as e:
                logger.error(f"Error creating workspace '{workspace_path}': {e}")
                return None
        else:
            logger.info("Exiting.")
            return None

    config.set_workspace_root(workspace_path)

    while True:
        index_choice = await get_user_input(
            "Do you want to index this workspace for local semantic search? (yes/no): "
        )
        if index_choice.lower() in ["yes", "y", "no", "n"]:
            break
        logger.warning("Please enter 'yes' or 'no'.")

    if index_choice.lower() in ["yes", "y"]:
        try:
            indexer = CodeIndexer(workspace_path)
            with console.status(
                "[bold green]Indexing workspace with LanceDB...", spinner="dots"
            ):
                chunks = await indexer.index_workspace()
                logger.info(
                    f"Workspace indexed successfully! ({chunks} code chunks vectorized)"
                )
        except Exception as e:
            logger.warning(
                f"Could not index workspace: {e}\nEnsure you have installed "
                f"lancedb, pyarrow, and aiohttp. Also ensure Ollama has the "
                f"'nomic-embed-text' model."
            )

    return workspace_path


async def load_or_resume_plan(workspace_path: str) -> Optional[OrchestratorPlan]:
    """
    Checks for an existing plan.json and asks the user if they want to resume.
    """
    plan_file_path = os.path.join(workspace_path, "plan.json")
    if os.path.exists(plan_file_path):
        resume = await get_user_input(
            f"Existing plan found at {plan_file_path}. "
            f"Resume coding from it? (yes/no): "
        )
        if resume.lower() == "yes":
            try:
                with open(plan_file_path, "r", encoding="utf-8") as f:
                    plan = OrchestratorPlan.model_validate_json(f.read())
                logger.info("Resuming Implementation Plan")
                console.print("\n[bold green]Resuming Implementation Plan[/bold green]")
                for i, task in enumerate(plan.tasks):
                    status = (
                        "[Done]"
                        if task.status == TaskStatus.COMPLETED
                        else f"[{task.status.value}]"
                    )
                    scope_str = ", ".join(task.scope) if task.scope else "Global"
                    logger.info(f"  {i + 1}. {status} {scope_str}: {task.goal}")
                    console.print(
                        f"  {i + 1}. {status} [cyan]{scope_str}[/cyan]: {task.goal}"
                    )
                return plan
            except Exception as e:
                logger.error(f"Error loading existing plan: {e}")
    return None


def save_plan(workspace_path: str, plan: OrchestratorPlan) -> None:
    """
    Saves the implementation plan to plan.json.
    """
    plan_file_path = os.path.join(workspace_path, "plan.json")
    try:
        with open(plan_file_path, "w", encoding="utf-8") as f:
            f.write(plan.model_dump_json(indent=2))
    except Exception as e:
        logger.warning(f"Failed to save plan: {e}")
