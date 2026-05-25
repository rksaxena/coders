import sys
from pathlib import Path

# Allow running directly via `python` by adding the project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest
from src.swarm_coder.core.models import (
    TaskBlueprint,
    StateTracker,
    TaskStatus,
    AssignedTier,
)


def test_task_blueprint_creation():
    task = TaskBlueprint(goal="Create local vector DB", scope=["src/db.py"])

    assert task.goal == "Create local vector DB"
    assert task.status == TaskStatus.PENDING
    assert task.assigned_tier == AssignedTier.LOCAL
    assert len(task.scope) == 1
    assert task.scope[0] == "src/db.py"
    assert task.task_id is not None
    assert isinstance(task.task_id, str)


def test_state_tracker_add_task():
    tracker = StateTracker()
    task = TaskBlueprint(goal="Setup LanceDB", scope=["db.py"])

    tracker.add_task(task)

    assert len(tracker.tasks) == 1
    assert task.task_id in tracker.tasks
    assert len(tracker.audit_log) == 1
    assert tracker.audit_log[0]["action"] == "ADD_TASK"
    assert tracker.audit_log[0]["details"]["task_id"] == task.task_id


def test_state_tracker_update_status():
    tracker = StateTracker()
    task = TaskBlueprint(goal="Test status update", scope=["test.py"])
    tracker.add_task(task)

    tracker.update_task_status(task.task_id, TaskStatus.RUNNING)
    assert tracker.tasks[task.task_id].status == TaskStatus.RUNNING
    assert len(tracker.audit_log) == 2
    assert tracker.audit_log[1]["action"] == "UPDATE_TASK_STATUS"
    assert tracker.audit_log[1]["details"]["new_status"] == TaskStatus.RUNNING
