Here is the complete architectural map of the final **Swarm Coder** stack.

This topology illustrates how the system balances high-level cognitive reasoning in the cloud with secure, context-aware execution on your local machine.

# Architecture
```
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

## Technical Component Decomposition

To implement this architecture seamlessly via Gemini Code Assist or the Gemini CLI, the blueprint breaks down into four clear structural layers:

### 1. The Cloud Planning Interface

The cloud orchestrator manages high-level logic without absorbing your entire codebase into memory.

* **Inbound Interface:** Receives system prompts and high-level architectural intent.
* **Outbound Contract:** Constrained by a strict JSON Schema via Gemini Structured Outputs. It yields a structured checklist (`TaskBlueprint`) containing task IDs, multi-agent dependencies, and file path scopes.

### 2. The Local Control Plane

This acts as the state synchronization layer, keeping track of tasks and running a lightweight local vector store.

* **`StateTracker`:** A thread-safe, in-memory ledger written using Pydantic. It monitors task states (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`) and maps structural code adjustments.
* **`LanceDB Layer`:** A serverless, local vector database embedded in the application. It splits your workspace into semantic chunks locally using a fast local embedding model (e.g., `nomic-embed-text` via Ollama), ensuring zero raw file text is uploaded to cloud APIs during planning.

### 3. The Local Swarm Layer

An asynchronous event bus that handles worker communication, maximizing the performance of your hardware stack.

* **Async Event Bus:** Utilizes `asyncio.Queue` to decouple tasks.
* **`CoderAgent`:** Connects to a high-throughput local instance (such as Qwen 2.5 Coder 32B running via Ollama). It parses target files using localized search-and-replace strings or minimal AST (Abstract Syntax Tree) modifications rather than processing wasteful full-file rewrites.

### 4. The Isolated Sandbox Layer

The safety mechanism of the framework. It executes and validates untrusted code before changes are permanently checked in.

| Component | Responsibility | Technical Driver |
| --- | --- | --- |
| **`DockerSandboxTool`** | Builds execution contexts and manages active lifecycle hooks. | Docker SDK for Python |
| **Volume Controller** | Binds your active workspace workspace paths as scoped, read-only mounts. | Docker Engine API |
| **Self-Healing Pipeline** | Traps `stderr` runtime crash traces and directs them back to the `CoderAgent` for autonomous retries. | Python `subprocess` & Stream Capturing |

---