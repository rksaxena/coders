import asyncio
import os
import re
import uuid
from typing import Optional

from google.adk.models import Gemini, LiteLlm
from google.adk.runners import Runner
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.swarm_coder.cli.interaction import run_agent_interaction
from src.swarm_coder.cli.ui import console, get_user_input
from src.swarm_coder.cli.workspace import save_plan
from src.swarm_coder.config.config import config
from src.swarm_coder.core.agents import get_coder_agent, get_planner_agent
from src.swarm_coder.core.logger import logger
from src.swarm_coder.core.models import OrchestratorPlan, TaskStatus
from src.swarm_coder.core.timing import profiler
from src.swarm_coder.tools.indexer import CodeIndexer
from src.swarm_coder.tools.ollama_client import OllamaClient


async def _execute_planner_interaction(
    agent,
    runner,
    current_message: str,
    description: str = "Planner is thinking...",
    session_id: Optional[str] = None,
):
    with profiler.track_step("Planner Step"):
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            transient=True,
        ) as progress:
            progress.add_task(description=description, total=None)

            last_err = None
            plan = None
            response = None
            for pm_config in config.get_model_iterator("planner"):
                pm = pm_config["name"]
                m_type = pm_config.get("type", "cloud")
                try:
                    if m_type == "local":
                        model_name = pm if pm.startswith("ollama/") else f"ollama/{pm}"
                        agent.model = LiteLlm(model=model_name)
                    else:
                        agent.model = Gemini(model=pm)

                    plan, response = await run_agent_interaction(
                        runner, current_message, is_planner=True, session_id=session_id
                    )
                    last_err = None
                    break
                except Exception as e:
                    logger.warning(f"Model '{pm}' failed: {e}. Trying next...")
                    last_err = e
            if last_err:
                raise last_err
    return plan, response


async def _print_and_get_approval(plan: OrchestratorPlan) -> str:
    logger.info("Implementation Plan Generated")
    console.print("\n[bold green]Implementation Plan Generated[/bold green]")
    for i, task in enumerate(plan.tasks):
        status = (
            "[Done]"
            if task.status == TaskStatus.COMPLETED
            else f"[{task.status.value}]"
        )
        scope_str = ", ".join(task.scope) if task.scope else "Global"
        logger.info(f"  {i + 1}. {status} {scope_str}: {task.goal}")
        console.print(f"  {i + 1}. {status} [cyan]{scope_str}[/cyan]: {task.goal}")

    return await get_user_input("\nDo you approve this plan? (yes/no/modify): ")


async def run_planning_phase(
    workspace_path: str, session_service
) -> Optional[OrchestratorPlan]:
    """
    Handles the requirements loading and planning phase.
    """
    req_path = await get_user_input("Enter path to requirements file (.md): ")
    if not os.path.exists(req_path):
        logger.error(f"Requirements file not found at {req_path}")
        return None

    try:
        with open(req_path, "r", encoding="utf-8") as f:
            requirements_content = f.read()
    except Exception as e:
        logger.error(f"Error reading requirements file: {e}")
        return None

    try:
        planner_agent = get_planner_agent()
        planner_runner = Runner(
            app_name="PlannerApp",
            agent=planner_agent,
            session_service=session_service,
            auto_create_session=True,
        )
    except Exception as e:
        logger.error(f"Failed to initialize planner agent: {e}")
        return None

    current_message = (
        f"USER OBJECTIVE: Implementation in workspace '{workspace_path}'\n\n"
        f"REQUIREMENTS CONTENT:\n{requirements_content}"
    )

    while True:
        plan, response = await _execute_planner_interaction(
            planner_agent, planner_runner, current_message
        )

        if response:
            logger.info(response)

        if plan:
            approval = await _print_and_get_approval(plan)
            if approval.lower() == "yes":
                save_plan(workspace_path, plan)
                logger.info(
                    f"Plan saved to {os.path.join(workspace_path, 'plan.json')}"
                )
                return plan
            if approval.lower() == "no":
                return None

            current_message = (
                f"Please modify the plan based on this feedback: {approval}"
            )
            continue

        if response and response.strip():
            logger.info(f"Planner: {response}")
        user_feedback = await get_user_input("\nYour response: ")
        current_message = user_feedback


def _get_existing_content_prompt(filepath: str, target_file: str) -> str:
    if not os.path.exists(filepath):
        return ""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            existing_content = f.read()
            if existing_content.strip():
                return (
                    f"\nEXISTING FILE CONTENT:\n```\n{existing_content}\n```\n"
                    f"IMPORTANT: This file already exists. You must output the ENTIRE "
                    f"updated file, preserving existing code while applying the new "
                    f"instructions."
                )
    except Exception as e:
        logger.warning(f"Could not read existing file {target_file}: {e}")
    return ""


def _prepare_coder_client_and_models(coder_agent):
    try:
        full_model = coder_agent.model.model
    except AttributeError:
        full_model = None

    model_configs = list(
        config.get_model_iterator("coder", current_agent_model=full_model)
    )
    if not model_configs:
        raise ValueError(
            "No valid coder models found in configuration. Please check your config.yaml."
        )

    api_base = os.getenv("OLLAMA_API_BASE", config.ollama_base_url).rstrip("/")
    if not api_base.endswith("/api/generate"):
        api_base = f"{api_base}/api/generate"

    client = OllamaClient(base_url=api_base)
    return client, model_configs


async def _write_stream_to_file(stream, filepath: str) -> None:
    buffer = ""
    in_code_block = False
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            async for chunk in stream:
                buffer += chunk
                if not in_code_block:
                    if "```" in buffer:
                        newline_idx = buffer.find("\n", buffer.find("```"))
                        if newline_idx != -1:
                            in_code_block = True
                            buffer = buffer[newline_idx + 1 :]
                if in_code_block:
                    if "```" in buffer:
                        content = buffer[: buffer.find("```")]
                        f.write(content)
                        buffer = ""
                        break
                    elif len(buffer) > 3:
                        f.write(buffer[:-3])
                        buffer = buffer[-3:]
            if buffer and not in_code_block:
                f.write(buffer)
            elif buffer and in_code_block:
                f.write(buffer.replace("`", ""))
    finally:
        if hasattr(stream, "aclose"):
            await stream.aclose()


async def _update_local_index(
    filepath: str, workspace_path: str, target_file: str
) -> None:
    try:
        indexer = CodeIndexer(workspace_path)
        chunks_indexed = await indexer.index_file(filepath)
        if chunks_indexed > 0:
            logger.info(
                f"Dynamically indexed {chunks_indexed} semantic chunks for {target_file}"
            )
    except Exception as e:
        logger.warning(f"Failed to update local index for {target_file}: {e}")


async def run_execution_phase(
    workspace_path: str,
    plan: OrchestratorPlan,
    session_service,
    max_coders: Optional[int] = None,
) -> None:
    """
    Handles the execution of tasks in the implementation plan.
    """
    logger.info("Step 2: Execution Phase")
    max_coders = max_coders or config.max_coders
    semaphore = asyncio.Semaphore(max_coders)
    plan_lock = asyncio.Lock()

    async def process_task(i, task, progress_ctx):
        async with semaphore:
            if task.status == TaskStatus.COMPLETED:
                scope_str = ", ".join(task.scope) if task.scope else "Global"
                logger.info(
                    f"Task {i + 1}/{len(plan.tasks)}: {scope_str} [ALREADY COMPLETED, SKIPPING]"
                )
                return

            scope_str = ", ".join(task.scope) if task.scope else "Global"
            logger.info(f"Task {i + 1}/{len(plan.tasks)}: {scope_str}")

            try:
                coder_agent = get_coder_agent()
                coder_runner = Runner(
                    app_name=f"CoderApp_{i}",
                    agent=coder_agent,
                    session_service=session_service,
                    auto_create_session=True,
                )
            except Exception as e:
                logger.error(f"Failed to initialize coder agent for {scope_str}: {e}")
                return

            target_file = None
            if task.scope:
                target_file = task.scope[0]
            else:
                # Fallback: extract a file path from the goal if scope is empty
                match = re.search(r"([a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]+)", task.goal)
                target_file = match.group(1) if match else "unknown_file.txt"
            filepath = (
                os.path.join(workspace_path, target_file)
                if not os.path.isabs(target_file)
                else target_file
            )

            existing_content_prompt = _get_existing_content_prompt(
                filepath, target_file
            )

            coder_prompt = config.coder_task_prompt.format(
                goal=task.goal,
                target_file=target_file,
                existing_content_prompt=existing_content_prompt,
            )
            try:
                with profiler.track_step(f"Coder Step: {target_file}"):
                    task_id = progress_ctx.add_task(
                        description=f"Coder is writing {target_file}...", total=None
                    )

                    client, model_configs = _prepare_coder_client_and_models(
                        coder_agent
                    )
                    model_names_str = [m["name"] for m in model_configs]
                    logger.info(
                        f"Streaming directly using model priority list: {model_names_str}..."
                    )

                    stream = await client.generate(
                        model=model_names_str, prompt=coder_prompt, stream=True
                    )

                    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

                    await _write_stream_to_file(stream, filepath)
                    await _update_local_index(filepath, workspace_path, target_file)

                    progress_ctx.remove_task(task_id)
                # Checkpoint: mark completed and rewrite plan.json
                async with plan_lock:
                    task.status = TaskStatus.COMPLETED
                    save_plan(workspace_path, plan)
            except Exception as e:
                logger.error(f"Task {target_file} failed unexpectedly: {e}")
                async with plan_lock:
                    task.status = TaskStatus.FAILED
                    save_plan(workspace_path, plan)
                logger.info("Continuing to the next task...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress_ctx:
        await asyncio.gather(
            *(process_task(i, task, progress_ctx) for i, task in enumerate(plan.tasks))
        )

    logger.info("Swarm execution completed successfully")


def _gather_workspace_context(workspace_path: str) -> str:
    ignore_dirs = config.ignore_dirs
    valid_exts = config.valid_exts

    workspace_files_content = []
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
        for file in files:
            if any(file.endswith(ext) for ext in valid_exts):
                f_path = os.path.join(root, file)
                rel_path = os.path.relpath(f_path, workspace_path)
                try:
                    with open(f_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if content.strip():
                            workspace_files_content.append(
                                f"--- {rel_path} ---\n```\n{content}\n```"
                            )
                except (OSError, UnicodeDecodeError):
                    pass

    if workspace_files_content:
        return (
            "\nCURRENT WORKSPACE FILES (For Context):\n"
            + "\n\n".join(workspace_files_content)
            + "\n"
        )
    return "\nCURRENT WORKSPACE FILES: (No files found)\n"


async def run_reviewer_phase(
    workspace_path: str, original_plan: OrchestratorPlan, session_service
) -> Optional[OrchestratorPlan]:
    """
    Handles the review phase, checking the coders' work against the plan and asking user for confirmation to apply fixes.
    """
    logger.info("Step 3: Review Phase")

    workspace_context = _gather_workspace_context(workspace_path)

    original_tasks_str = "\n".join(
        [
            f"- {', '.join(t.scope) if t.scope else 'Global'}: {t.goal}"
            for t in original_plan.tasks
        ]
    )

    current_message = config.reviewer_prompt.format(
        original_tasks_str=original_tasks_str, workspace_context=workspace_context
    )

    try:
        reviewer_agent = get_planner_agent()
        reviewer_runner = Runner(
            app_name="ReviewerApp",
            agent=reviewer_agent,
            session_service=session_service,
            auto_create_session=True,
        )
    except Exception as e:
        logger.error(f"Failed to initialize reviewer agent: {e}")
        return None

    review_session_id = f"review_session_{uuid.uuid4().hex}"

    while True:
        new_plan, response = await _execute_planner_interaction(
            reviewer_agent,
            reviewer_runner,
            current_message,
            description="Reviewer is analyzing the codebase...",
            session_id=review_session_id,
        )

        if response and response.strip():
            logger.info(f"Reviewer Feedback:\n{response}")
            console.print(f"\n[bold blue]Reviewer Feedback:[/bold blue]\n{response}")

        if new_plan and new_plan.tasks:
            logger.info("Suggested Fixes / New Tasks Generated")
            console.print(
                "\n[bold yellow]Suggested Fixes / New Tasks Generated[/bold yellow]"
            )
            for i, task in enumerate(new_plan.tasks):
                scope_str = ", ".join(task.scope) if task.scope else "Global"
                logger.info(f"  {i + 1}. {scope_str}: {task.goal}")
                console.print(f"  {i + 1}. [cyan]{scope_str}[/cyan]: {task.goal}")

            approval = await get_user_input(
                "\nDo you want the coders to implement these changes? (yes/no/modify): "
            )
            if approval.lower() == "yes":
                return new_plan
            if approval.lower() == "no":
                return None

            current_message = (
                f"Please modify your review/plan based on this feedback: {approval}"
            )
            continue

        if not new_plan:
            approval = await get_user_input(
                (
                    "\nDo you have any feedback or manual corrections? "
                    "(Enter feedback or type 'no' if satisfied): "
                )
            )
            if approval.lower() in ["no", "none", "nothing"]:
                return None

            current_message = approval
            continue

        logger.info("Review Complete. Reviewer found no issues.")
        console.print(
            "\n[bold green]Review Complete. Reviewer found no issues.[/bold green]"
        )
        return None
