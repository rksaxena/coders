# Technical Specification: Swarm Coding Agents

## 1. Overview
This document outlines the technical specification for building a swarm of coding agents designed to rewrite and modify codebases. The system relies on a hybrid LLM approach, leveraging both state-of-the-art (SOTA) cloud models for complex reasoning and planning, and local, efficient models for actual code generation and execution. 

The framework of choice for orchestrating these agents is **`google-adk`**.

## 2. Architecture & Tech Stack

*   **Orchestration Framework**: `google-adk` (Google Agent Development Kit / GenAI SDK). Used to define agents, tools, memory, and the delegation workflow.
*   **Planner Agent (SOTA Cloud Model)**: Gemini API (specifically Gemma/Gemini variants) for high-level reasoning, analyzing the codebase, and creating step-by-step rewrite plans.
*   **Coder Agent (Local Model)**: Local Ollama instance running Qwen-based models (e.g., `qwen2.5-coder`). Used for generating code, rewriting specific files based on instructions, and executing edits securely.
*   **Language**: Python 3.10+

## 3. Agent Roles and Capabilities

### 3.1 Planner Agent (The "Architect")
*   **Model**: Gemini / Gemma via Gemini API.
*   **Role**: Analyze the user's intent, review the targeted files, and decompose the task into atomic coding steps.
*   **Capabilities**:
    *   Read directory structures and file contents.
    *   Formulate a sequential, file-by-file `RewritePlan`.
    *   Delegate specific code rewrite tasks to the Coder Agent.
    *   Verify the final output against the original plan.

### 3.2 Coder Agent (The "Executor")
*   **Model**: Local Qwen model via Ollama API (`http://localhost:11434/api/generate`).
*   **Role**: Receive specific file rewrite instructions from the Planner, generate the updated code, and write it to disk.
*   **Capabilities**:
    *   Read file (specific lines or full file).
    *   Perform syntax-aware code rewrites.
    *   Save modifications to the file system.
    *   Return execution status (success/failure/errors) back to the Planner Agent.

## 4. Phase 1 Workflow: "Rewriting Files"

The initial implementation will focus on the foundational use case: safely and accurately rewriting files based on a high-level prompt.

### Execution Flow:
1.  **User Input**: User provides a prompt (e.g., "Refactor the authentication module to use JWT").
2.  **Context Gathering**: The Planner Agent uses `google-adk` tools to inspect the workspace (`agents/`, `tools/`, etc.) and read necessary files to understand the current state.
3.  **Planning Phase**: 
    *   The Planner Agent outputs a structured plan (JSON/Pydantic model) containing a list of `FileTask` objects (filename, instruction, context).
4.  **Delegation (Swarm Interaction)**:
    *   The Planner loops through the `FileTask` objects and delegates them one-by-step to the Coder Agent.
5.  **Execution Phase**:
    *   The Coder Agent queries the local Ollama Qwen model with the specific instruction and the current file content.
    *   The Coder Agent processes the response and overwrites/modifies the target file.
    *   The Coder Agent reports back to the Planner.
6.  **Finalization**: The Planner Agent reviews the status of all delegated tasks and reports completion to the user.

## 5. Implementation Roadmap

### Step 1: Initialize Project Structure
```text
/
├── main.py                  # Entry point for the CLI/App
├── requirements.txt         # google-adk, requests, etc.
├── agents/
│   ├── __init__.py
│   ├── planner.py           # Gemini-backed planner agent definition
│   └── coder.py             # Ollama-backed coder agent definition
└── tools/
    ├── __init__.py
    ├── file_tools.py        # File reading, writing, and listing tools
    └── ollama_client.py     # Custom integration to call local Ollama API
```

### Step 2: Implement Tooling (`tools/`)
*   Create robust file read/write tools that the agents can invoke.
*   Create an HTTP client wrapper for Ollama (`tools/ollama_client.py`) that formats prompts specifically for `qwen` models and parses the response.

### Step 3: Define Agents with `google-adk`
*   Define the **Planner Agent** using the `google-adk` agent definitions, hooking it up to the Gemini API with instructions to output structured tasks.
*   Define the **Coder Agent**. Since standard cloud-based frameworks might not natively support local Ollama out of the box, use a custom LLM binding or tool-based delegation within `google-adk` to route the Coder Agent's thought process through the local Qwen model.

### Step 4: Implement Orchestration (`main.py`)
*   Instantiate both agents.
*   Set up the main loop where the Planner receives the user objective, generates the task list, and hands off execution context to the Coder Agent iteratively.

## 6. Security & Performance Considerations
*   **Context Window limits**: Ensure the Planner does not read overly large files natively. Implement a snippet/chunking tool if necessary.
*   **Local Latency**: Qwen models running locally will vary in speed based on hardware. The orchestration loop should handle timeouts and retries gracefully.
*   **Destructive Edits**: Implement a dry-run mode or a temporary staging directory where the Coder Agent writes changes before they are committed or approved by the Planner.