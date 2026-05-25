## Core Architecture Overview

Before implementing, this is the target state for the `coders` framework:

+-------------------------------------------------------------------------+
 |                         1. CLOUD PLANNING LAYER                         |
 |                                                                         |
 |                     +-----------------------------+                     |
 |                     |      Gemini Cloud API       |                     |
 |                     | (Lead Architect / Planner)  |                     |
 |                     +--------------+--------------+                     |
 +------------------------------------+------------------------------------+
                                      |
                         [JSON TaskBlueprint Contract]
                                      |
                                      v
 +-------------------------------------------------------------------------+
 |                         2. LOCAL CONTROL PLANE                          |
 |                                                                         |
 |   +--------------------+     +--------------------+     +-----------+   |
 |   |    StateTracker    |     |   asyncio.Queue    |     |  LanceDB  |   |
 |   | (Pydantic Ledger)  |<--->|  (Pub/Sub Event)   |     | (LocalRAG)|   |
 |   +---------^----------+     +----------+---------+     +-----^-----+   |
 +-------------|---------------------------|---------------------|---------+
               |                           |                     |
         [Success/Logs]            [Dispatched Task]      [Context Query]
               |                           |                     |
               |                           v                     |
 +-------------|-------------------------------------------------|---------+
 |             |               3. LOCAL SWARM WORKERS            |         |
 |             |                                                 |         |
 |   +---------+--------+       +--------------------+           |         |
 |   |   TesterAgent    |       |  OrchestratorAgent |-----------+         |
 |   | (Validation Drv) |       |   (Task Router)    |                     |
 |   +---------^--------+       +----------+---------+                     |
 |             |                           |                               |
 |       [Error Logs]                      v                               |
 |             |                +--------------------+                     |
 |             +----------------|     CoderAgent     |                     |
 |                              | (Ollama Qwen-Coder)|                     |
 |                              +----------+---------+                     |
 +-----------------------------------------|-------------------------------+
                                           |
                                  [Targeted AST Diff]
                                           |
                                           v
 +-------------------------------------------------------------------------+
 |                   4. CLEAN ROOM VALIDATION SANDBOX                      |
 |                                                                         |
 |   +--------------------+     +--------------------+     +-----------+   |
 |   |     Host FS        |     |     Docker SDK     |     | Ephemeral |   |
 |   | (Workspace Mount)  |<--->|     for Python     |---->| Container |   |
 |   +--------------------+     +--------------------+     +-----+-----+   |
 |                                                               |         |
 |                                                               v         |
 |                                                         [Runs Pytest]   |
 +-------------------------------------------------------------------------+
```

---

## Phase-by-Phase Implementation Blueprint

1. **Phase 1: Foundation - JSON Blueprints & Abstract State Tracking:** Goal: Establish a deterministic, token-efficient contract between Cloud and Local..
### Prompt for Gemini Code Assist / CLI:

```text
In my 'coders' framework, I want to migrate away from raw text conversational handovers. 
Implement a structured state management system using Pydantic. 

Requirements:
1. Define a 'TaskBlueprint' Pydantic model containing:
   - 'task_id': unique uuid
   - 'goal': string description
   - 'dependencies': list of task_ids
   - 'scope': list of file paths involved
   - 'status': enum (PENDING, RUNNING, COMPLETED, FAILED)
   - 'assigned_tier': enum (FRONTIER, LOCAL)
2. Implement an in-memory 'StateTracker' class that stores the global system state, active workspace context, and an audit log of mutations.
3. Write an abstraction layer for the Gemini Orchestrator that forces it to output strictly JSON matching the TaskBlueprint schema using Gemini Structured Outputs.

```


2. **Phase 2: Local Context Layer - Zero-Cloud Vector Storage:** Goal: Give local agents workspace-wide awareness without leaking proprietary code to the cloud..
### Prompt for Gemini Code Assist / CLI:

```text
Add a local codebase indexing and context retrieval engine to 'coders' using LanceDB and a local embedding model via Ollama (e.g., nomic-embed-text).

Requirements:
1. Create a 'CodeIndexer' utility that walks the local workspace directory, ignores paths in .gitignore, chunks files syntactically (by functions/classes if possible, fallback to 500-token semantic chunks), and writes embeddings into a local LanceDB instance.
2. Implement an asynchronous 'ContextRetriever' tool. When a local Ollama agent receives a sub-task, it should query LanceDB using vector search to fetch the top-K relevant code blocks or function definitions.
3. Update the state context so that retrieved context is injected into the local agent's prompt window dynamically, ensuring zero code content leaves the local machine during local sub-task execution.

```


3. **Phase 3: The Event-Driven Swarm Layer:** Goal: Decouple agent execution into a highly scalable, asynchronous task pool..
### Prompt for Gemini Code Assist / CLI:

```text
Refactor the executor execution loop in 'coders' from a synchronous call-and-response into an asynchronous, event-driven local agent swarm.

Requirements:
1. Implement a lightweight, in-memory Event Bus using asyncio.Queue. 
2. Define an 'AgentMessage' payload containing sender, receiver, topic, and a delta payload (changes/results).
3. Create a base class 'BaseSwarmAgent' that runs an internal loop listening to the Event Bus.
4. Implement two specialized worker subclasses:
   - 'FileEditorAgent': connects to Ollama (running Qwen 2.5 Coder 32B), pulls tasks from the queue, modifies files, and emits a 'CODE_MUTATED' event.
   - 'TestRunnerAgent': listens for 'CODE_MUTATED', runs local pytest/linters via subprocess, and emits a 'TEST_PASSED' or 'TEST_FAILED' event back to the queue.

```


4. **Phase 4: Optimization - AST Delta Handover & Memory Management:** Goal: Optimize for 24GB Unified Memory systems by pruning context windows..
### Prompt for Gemini Code Assist / CLI:

```text
Optimize token usage and hardware footprint for the 'coders' framework when running on high-bandwidth unified memory configurations.

Requirements:
1. Implement an 'ASTDiffEngine' using Python's 'ast' or 'difflib' module. When the FileEditorAgent finishes an operation, it must compute a minimal line-based or structural diff.
2. Modify the synchronization logic: Instead of passing whole file contents back up to the Gemini Orchestrator for validation, only append the computed 'AST Diff' to the TaskBlueprint history.
3. Implement a lightweight VRAM runtime gatekeeper. When switching workloads between a massive coding model (like Qwen 32B) and an embedding/routing model, invoke Ollama's '/api/generate' with a 'keep_alive: 0' flag on the idle model to gracefully unload it from VRAM, avoiding memory thrashing.

```