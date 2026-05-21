import os
import asyncio
import uuid
from google.adk.runners import Runner
from src.swarm_coder.core.models import ImplementationPlan
from src.swarm_coder.core.agents import get_planner_agent, get_coder_agent
from src.swarm_coder.cli.ui import get_user_input
from src.swarm_coder.cli.interaction import run_agent_interaction
from src.swarm_coder.cli.workspace import save_plan
from src.swarm_coder.core.timing import profiler
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from src.swarm_coder.tools.ollama_client import OllamaClient

async def run_planning_phase(workspace_path: str, session_service) -> ImplementationPlan:
    """
    Handles the requirements loading and planning phase.
    """
    req_path = await get_user_input("Enter path to requirements file (.md): ")
    if not os.path.exists(req_path):
        print(f"Error: Requirements file not found at {req_path}")
        return None
    
    try:
        with open(req_path, 'r', encoding='utf-8') as f:
            requirements_content = f.read()
    except Exception as e:
        print(f"Error reading requirements file: {e}")
        return None

    try:
        planner_agent = get_planner_agent()
        planner_runner = Runner(app_name="PlannerApp", agent=planner_agent, session_service=session_service, auto_create_session=True)
    except Exception as e:
        print(f"\n[Error] Failed to initialize planner agent: {e}")
        return None

    current_message = (
        f"USER OBJECTIVE: Implementation in workspace '{workspace_path}'\n\n"
        f"REQUIREMENTS CONTENT:\n{requirements_content}"
    )
    
    while True:
        with profiler.track_step("Planner Step"):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                transient=True,
            ) as progress:
                progress.add_task(description="Planner is thinking...", total=None)
                plan, response = await run_agent_interaction(planner_runner, current_message, is_planner=True)
        print(response)
        
        if plan:
            print("\n[Implementation Plan Generated]")
            for i, task in enumerate(plan.tasks):
                status = "[Done]" if task.completed else "[Pending]"
                print(f"  {i+1}. {status} {task.filename}: {task.instruction}")
            
            approval = await get_user_input("\nDo you approve this plan? (yes/no/modify): ")
            if approval.lower() == 'yes':
                save_plan(workspace_path, plan)
                print(f"\n[Plan saved to {os.path.join(workspace_path, 'plan.json')}]")
                return plan
            elif approval.lower() == 'no':
                return None
            else:
                current_message = f"Please modify the plan based on this feedback: {approval}"
                continue
        else:
            if response.strip():
                print(f"\nPlanner: {response}")
            user_feedback = await get_user_input("\nYour response: ")
            current_message = user_feedback

async def run_execution_phase(workspace_path: str, plan: ImplementationPlan, session_service, max_coders: int = 1) -> None:
    """
    Handles the execution of tasks in the implementation plan.
    """
    print("\n[Step 2: Execution Phase]")
    semaphore = asyncio.Semaphore(max_coders)
    plan_lock = asyncio.Lock()

    async def process_task(i, task, progress_ctx):
        async with semaphore:
            if task.completed:
                progress_ctx.console.print(f"\n--- Task {i+1}/{len(plan.tasks)}: {task.filename} [ALREADY COMPLETED, SKIPPING] ---")
                return
                
            progress_ctx.console.print(f"\n--- Task {i+1}/{len(plan.tasks)}: {task.filename} ---")
            
            try:
                coder_agent = get_coder_agent()
                coder_runner = Runner(app_name=f"CoderApp_{i}", agent=coder_agent, session_service=session_service, auto_create_session=True)
            except Exception as e:
                progress_ctx.console.print(f"\n[Error] Failed to initialize coder agent for {task.filename}: {e}")
                return

            filepath = os.path.join(workspace_path, task.filename) if not os.path.isabs(task.filename) else task.filename
            
            existing_content_prompt = ""
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                        if existing_content.strip():
                            existing_content_prompt = (
                                f"\nEXISTING FILE CONTENT:\n```\n{existing_content}\n```\n"
                                f"IMPORTANT: This file already exists. You must output the ENTIRE updated file, preserving existing code while applying the new instructions."
                            )
                except Exception as e:
                    progress_ctx.console.print(f"[dim]Could not read existing file {task.filename}: {e}[/dim]")

            coder_prompt = (
                f"INSTRUCTION: {task.instruction}\n"
                f"CONTEXT: {task.context}\n"
                f"Target File: {task.filename}\n"
                f"{existing_content_prompt}\n"
                f"IMPORTANT: You MUST output ONLY the complete implementation code enclosed in a single Markdown code block (```language ... ```).\n"
                f"Do NOT provide any conversational text, explanations, or tool calls."
            )
            try:
                with profiler.track_step(f"Coder Step: {task.filename}"):
                    task_id = progress_ctx.add_task(description=f"Coder is writing {task.filename}...", total=None)
                    
                    # Extract the exact model name from your ADK agent config (e.g. 'ollama/qwen2.5-coder:7b' -> 'qwen2.5-coder:7b')
                    try:
                        full_model = coder_agent.model.model
                        model_name = full_model.replace("ollama/", "") if full_model.startswith("ollama/") else full_model
                    except AttributeError:
                        model_name = os.getenv("OLLAMA_MODEL", "qwen2.5-coder")
                        
                    api_base = os.getenv('OLLAMA_API_BASE', 'http://127.0.0.1:11434').rstrip('/')
                    if not api_base.endswith('/api/generate'):
                        api_base = f"{api_base}/api/generate"
                        
                    client = OllamaClient(base_url=api_base)
                    progress_ctx.console.print(f"[dim]Streaming directly using model: '{model_name}'...[/dim]")
                    
                    stream = await client.generate(model=model_name, prompt=coder_prompt, stream=True)
                    
                    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
                    
                    buffer = ""
                    in_code_block = False
                    
                    try:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            async for chunk in stream:
                                buffer += chunk
                                if not in_code_block:
                                    if "```" in buffer:
                                        newline_idx = buffer.find("\n", buffer.find("```"))
                                        if newline_idx != -1:
                                            in_code_block = True
                                            buffer = buffer[newline_idx + 1:]
                                
                                if in_code_block:
                                    if "```" in buffer:
                                        content = buffer[:buffer.find("```")]
                                        f.write(content)
                                        buffer = ""
                                        break
                                    else:
                                        if len(buffer) > 3:
                                            f.write(buffer[:-3])
                                            buffer = buffer[-3:]
                                            
                            if buffer and not in_code_block:
                                f.write(buffer)
                            elif buffer and in_code_block:
                                f.write(buffer.replace("`", ""))
                    finally:
                        if hasattr(stream, 'aclose'):
                            await stream.aclose()
                            
                    progress_ctx.remove_task(task_id)
                # Checkpoint: mark completed and rewrite plan.json
                async with plan_lock:
                    task.completed = True
                    save_plan(workspace_path, plan)
            except Exception as e:
                progress_ctx.console.print(f"\n[Error] Task {task.filename} failed unexpectedly: {e}")
                progress_ctx.console.print("Continuing to the next task...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress_ctx:
        await asyncio.gather(*(process_task(i, task, progress_ctx) for i, task in enumerate(plan.tasks)))

    print("\n--- Swarm execution completed successfully ---")

async def run_reviewer_phase(workspace_path: str, original_plan: ImplementationPlan, session_service):
    """
    Handles the review phase, checking the coders' work against the plan and asking user for confirmation to apply fixes.
    """
    print("\n[Step 3: Review Phase]")
    
    workspace_context = ""
    ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.venv', 'env'}
    valid_exts = {'.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.json', '.md', '.txt', '.yml', '.yaml'}
    
    workspace_files_content = []
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
        for file in files:
            if any(file.endswith(ext) for ext in valid_exts):
                f_path = os.path.join(root, file)
                rel_path = os.path.relpath(f_path, workspace_path)
                try:
                    with open(f_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if content.strip():
                            workspace_files_content.append(f"--- {rel_path} ---\n```\n{content}\n```")
                except Exception:
                    pass
    
    if workspace_files_content:
        workspace_context = "\nCURRENT WORKSPACE FILES (For Context):\n" + "\n\n".join(workspace_files_content) + "\n"
    else:
        workspace_context = "\nCURRENT WORKSPACE FILES: (No files found)\n"

    original_tasks_str = "\n".join([f"- {t.filename}: {t.instruction}" for t in original_plan.tasks])

    current_message = (
        f"You are an Expert Code Reviewer. Review the code in the workspace and verify if the following original tasks were implemented correctly and completely:\n"
        f"{original_tasks_str}\n\n"
        f"{workspace_context}\n"
        f"Analyze the codebase for completeness, accuracy, and potential bugs. "
        f"If there are issues, errors, or missing parts, output a detailed explanation, and you MUST generate a new ImplementationPlan (using the correct JSON format or tool) with specific tasks for the coders to fix them.\n"
        f"If the work is 100% complete and accurate, output a short confirmation message and generate an ImplementationPlan with an empty tasks list."
    )

    try:
        # We reuse the planner agent as the reviewer since it is designed to output an ImplementationPlan
        reviewer_agent = get_planner_agent()
        reviewer_runner = Runner(app_name="ReviewerApp", agent=reviewer_agent, session_service=session_service, auto_create_session=True)
    except Exception as e:
        print(f"\n[Error] Failed to initialize reviewer agent: {e}")
        return None

    review_session_id = f"review_session_{uuid.uuid4().hex}"

    while True:
        with profiler.track_step("Reviewer Step"):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                transient=True,
            ) as progress:
                progress.add_task(description="Reviewer is analyzing the codebase...", total=None)
                new_plan, response = await run_agent_interaction(reviewer_runner, current_message, is_planner=True, session_id=review_session_id)
        
        if response and response.strip():
            print(f"\nReviewer Feedback:\n{response}")
        
        if new_plan and new_plan.tasks:
            print("\n[Suggested Fixes / New Tasks Generated]")
            for i, task in enumerate(new_plan.tasks):
                print(f"  {i+1}. {task.filename}: {task.instruction}")
            
            approval = await get_user_input("\nDo you want the coders to implement these changes? (yes/no/modify): ")
            if approval.lower() == 'yes':
                return new_plan
            elif approval.lower() == 'no':
                return None
            else:
                current_message = f"Please modify your review/plan based on this feedback: {approval}"
                continue
        else:
            if not new_plan:
                approval = await get_user_input("\nDo you have any feedback or manual corrections? (Enter feedback or type 'no' if satisfied): ")
                if approval.lower() in ['no', 'none', 'nothing']:
                    return None
                else:
                    current_message = approval
                    continue
            else:
                print("\n[Review Complete] Reviewer found no issues.")
                return None
