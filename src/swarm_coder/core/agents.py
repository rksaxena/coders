from google import adk
from google.adk.models import LiteLlm
from google.adk.models import Gemini
from src.swarm_coder.core.models import ImplementationPlan
from src.swarm_coder.tools.file_ops import read_file_content, write_file_content, list_files

def get_planner_agent() -> adk.Agent:
    """
    Creates and returns the Planner Agent.
    """
    instructions = """
    You are the Principal Architect. Your primary goal is to generate an 'ImplementationPlan' to fulfill the user's requirements.
    
    CRITICAL RULES:
    1. REQUIREMENTS: The user will provide the requirements directly in the prompt or through a file path. Analyze them carefully. Use the read_file_content tool to read any files if necessary to fully understand the requirements.  
    2. TARGET DISCOVERY: Use 'list_files' to understand the current project structure and 'read_file_content' to inspect relevant existing files before planning.
    3. MINIMAL QUESTIONS: Only ask clarification questions if implementation is IMPOSSIBLE without them. If you can make reasonable assumptions, do so and state them in the plan.
    4. PLAN FORMAT: Your final output MUST be a valid JSON object matching the 'ImplementationPlan' schema. Output the JSON directly without conversational filler.
    5. ATOMIC TASKS: Decompose the work into clear, file-specific tasks.
    
    If the requirements are clear, DO NOT talk or ask questions. Immediately perform discovery tool calls and then output the 'ImplementationPlan'.

    **PLANNER'S OUTPUT MUST BE A SINGLE JSON OBJECT IN THE IMPLEMENTATIONPLAN FORMAT. DO NOT OUTPUT ANYTHING ELSE.**
    **ENSURE THE JSON IS WELL-FORMED AND VALIDATES AGAINST THE IMPLEMENTATIONPLAN SCHEMA.**
    """
    
    planner = adk.Agent(
        name="PlannerAgent",
        model=Gemini(model="gemini-3.5-flash"),
        instruction=instructions,
        tools=[read_file_content, list_files],
        output_schema=ImplementationPlan
    )
    
    return planner

def get_coder_agent() -> adk.Agent:
    """
    Creates and returns the Coder Agent.
    """
    instructions = """
    You are the SDE Coder. Your role is to execute specific file rewrite tasks assigned to you.
    
    1. Read the provided instructions and context carefully.
    2. Use 'read_file_content' tool if you need to see the current state of the file again.
    3. Generate the updated code for the target file.
    4. Use 'write_file_content' tool to save the changes to the file system.
    5. Ensure the code is production-grade, follows best practices, and includes error handling.

    **DO NOT** 
    * output any text other than the updated file content. The response to the user should be the content of the file after applying the instructions.
    
    IMPORTANT: You must write the FULL content of the file when using 'write_file_content'.
    """
    
    coder = adk.Agent(
        name="CoderAgent",
        model=LiteLlm(model="ollama/qwen2.5-coder:7b"),
        instruction=instructions,
        tools=[read_file_content, write_file_content]
    )
    
    return coder
