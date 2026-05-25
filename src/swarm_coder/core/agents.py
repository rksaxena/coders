from google import adk
from google.adk.models import Gemini, LiteLlm

from src.swarm_coder.config.config import config
from src.swarm_coder.core.models import (
    OrchestratorPlan,
)
from src.swarm_coder.tools.file_ops import (
    list_files,
    read_file_content,
    search_codebase,
    write_file_content,
)


def get_planner_agent() -> adk.Agent:
    """
    Creates and returns the Planner Agent.
    """
    planner = adk.Agent(
        name="OrchestratorAgent",
        model=Gemini(model=config.planner_model),
        instruction=config.planner_instructions,
        tools=[read_file_content, list_files, search_codebase],
        output_schema=OrchestratorPlan,
    )

    return planner


def get_coder_agent() -> adk.Agent:
    """
    Creates and returns the Coder Agent.
    """
    coder = adk.Agent(
        name="CoderAgent",
        model=LiteLlm(model=config.coder_model),
        instruction=config.coder_instructions,
        tools=[read_file_content, write_file_content],
    )

    return coder
