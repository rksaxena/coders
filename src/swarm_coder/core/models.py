import time
import uuid
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator


class FileTask(BaseModel):
    """
    Represents a single file implementation or modification task.
    """

    filename: str = Field(description="The path to the file to be created or modified.")
    instruction: str = Field(
        description="Specific instructions for implementing this file."
    )
    context: str = Field(description="Relevant code snippets or context for the task.")
    completed: bool = Field(
        default=False,
        description="Whether the task has been successfully completed.",
    )


class ImplementationPlan(BaseModel):
    """
    Represents a full implementation plan containing multiple tasks.
    """

    tasks: List[FileTask] = Field(description="List of atomic coding tasks.")


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AssignedTier(str, Enum):
    FRONTIER = "FRONTIER"
    LOCAL = "LOCAL"


class TaskBlueprint(BaseModel):
    """
    Represents a deterministic contract for a task execution.
    """

    task_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the task.",
    )
    goal: str = Field(description="Description of what this task aims to achieve.")
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of task_ids that must be completed before this task.",
    )
    scope: List[str] = Field(
        default_factory=list, description="List of file paths involved in this task."
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING, description="Current status of the task."
    )
    assigned_tier: AssignedTier = Field(
        default=AssignedTier.LOCAL,
        description="The tier assigned to execute this task.",
    )

    @field_validator("scope", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            return [v]
        return v

    @field_validator("status", mode="before")
    @classmethod
    def uppercase_status(cls, v):
        return v.upper() if isinstance(v, str) else v

    @field_validator("assigned_tier", mode="before")
    @classmethod
    def uppercase_tier(cls, v):
        return v.upper() if isinstance(v, str) else v


class OrchestratorPlan(BaseModel):
    """
    A wrapper schema that forces the Orchestrator to output a list of
    TaskBlueprints.
    """

    tasks: List[TaskBlueprint]


class StateTracker(BaseModel):
    """
    In-memory ledger that stores the global system state, active workspace context,
    and an audit log of mutations.
    """

    tasks: Dict[str, TaskBlueprint] = Field(
        default_factory=dict, description="Map of task_id to TaskBlueprint."
    )
    workspace_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Active workspace context information.",
    )
    audit_log: List[Dict[str, Any]] = Field(
        default_factory=list, description="Log of state mutations."
    )

    def add_task(self, task: TaskBlueprint) -> None:
        self.tasks[task.task_id] = task
        self._log_mutation("ADD_TASK", {"task_id": task.task_id, "goal": task.goal})

    def update_task_status(self, task_id: str, status: TaskStatus) -> None:
        if task_id in self.tasks:
            old_status = self.tasks[task_id].status
            self.tasks[task_id].status = status
            self._log_mutation(
                "UPDATE_TASK_STATUS",
                {"task_id": task_id, "old_status": old_status, "new_status": status},
            )

    def _log_mutation(self, action: str, details: Dict[str, Any]) -> None:
        self.audit_log.append(
            {"timestamp": time.time(), "action": action, "details": details}
        )
