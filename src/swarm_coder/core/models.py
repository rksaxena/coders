from typing import List
from pydantic import BaseModel, Field

class FileTask(BaseModel):
    """
    Represents a single file implementation or modification task.
    """
    filename: str = Field(description="The path to the file to be created or modified.")
    instruction: str = Field(description="Specific instructions for implementing this file.")
    context: str = Field(description="Relevant code snippets or context for the task.")
    completed: bool = Field(default=False, description="Whether the task has been successfully completed.")

class ImplementationPlan(BaseModel):
    """
    Represents a full implementation plan containing multiple tasks.
    """
    tasks: List[FileTask] = Field(description="List of atomic coding tasks.")
