# End-to-End Test Spec: In-Memory Task Manager

## 1. Overview
This specification is designed to test the Swarm Coder framework end-to-end. It verifies the Orchestrator's JSON planning, the Coder's targeted file creation, and the real-time LanceDB semantic indexing of newly generated files.

## 2. Requirements

### 2.1. Core Data Model (`src/task_models.py`)
- Create a Pydantic model named `TaskItem`.
- Fields required: `id` (string, UUID), `title` (string), `completed` (boolean, default False).

### 2.2. Storage Layer (`src/task_store.py`)
- Create an in-memory class `TaskStore`.
- It must use the `TaskItem` model from `src/task_models.py`.
- Methods required: `create_task(title: str) -> TaskItem`, `get_all_tasks() -> list[TaskItem]`, and `mark_completed(task_id: str) -> bool`.

### 2.3. CLI Application (`src/task_cli.py`)
- Create a simple CLI that initializes the `TaskStore`.
- Provide basic print statements simulating adding a task and listing tasks.

## 3. Orchestration Directives
- Break this down into exactly 3 atomic tasks.
- Assign the `LOCAL` tier to all execution tasks.
- Assign proper dependencies (e.g., the store task depends on the models task being completed first).

## 4. Validation Criteria (For the Human Tester)
- During the execution phase, watch the logs to ensure LanceDB successfully indexes `task_models.py` immediately after the Coder finishes writing it.
- During the review phase, the Reviewer should use the semantic search tools to verify the generated functions.