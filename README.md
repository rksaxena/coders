# Swarm Coder

This project implements an advanced AI-driven **Swarm Coder** framework designed to autonomously rewrite, modify, and extend codebases. It relies on a hybrid LLM approach, balancing high-level cognitive reasoning in the cloud (via Google Gemini) with secure, fast, and context-aware execution on your local machine (via Ollama).

## Features

- **Hybrid Orchestration:** Uses the Google Agent Development Kit (`google-adk`) to route complex reasoning to the cloud and sensitive code-generation to local models.
- **Intelligent Task Planning:** The Planner Agent (Gemini) analyzes requirements and breaks them down into strict JSON `TaskBlueprint` contracts.
- **Local Swarm Workers:** The Coder Agent executes granular tasks entirely locally using models like `qwen2.5-coder`, ensuring maximum token efficiency and privacy.
- **Local RAG & Context:** Incorporates `LanceDB` to dynamically chunk and semantically index your workspace, allowing the swarm to retrieve precise code snippets without blowing up the context window.
- **Phased Execution Workflow:** Moves systematically through Planning, Execution, and Review phases, supporting automated fixes and user approval gates.

## Tech Stack

- **Orchestration:** `google-adk`
- **Cloud LLM (Planner):** Google Gemini API (Gemini 2.5 Flash / Pro)
- **Local LLM (Coder):** Ollama (e.g., `qwen2.5-coder:7b`, `nomic-embed-text`)
- **Vector Storage:** `LanceDB` & `PyArrow`
- **Language:** Python 3.10+

## Architecture Overview

1. **Cloud Planning Layer:** The Planner Agent acts as the Architect. It reviews your intent and outputs an `OrchestratorPlan` mapping multiple sequential or parallel `FileTask` actions.
2. **Local Control Plane:** Maintains an in-memory ledger (`StateTracker`) of active tasks and a lightweight vector index (`LanceDB`) for semantic workspace search.
3. **Local Swarm Execution:** Tasks are iteratively delegated to local Coder Agents, which stream modifications directly to the file system.
4. **Review & Validation:** A Reviewer Phase checks the implemented code against the original tasks, proposing new plans for missed edge cases or bugs.

## Prerequisites

- Ollama installed locally and running.
- Necessary local models pulled: `ollama pull qwen2.5-coder:7b` and `ollama pull nomic-embed-text`.
- A valid [Google Gemini API Key](https://aistudio.google.com/).

## Setup and Installation

1. **Clone the repository:**

   ```bash
   git clone <your-repo-url>
   cd coders
   ```

2. **Configure Environment Variables:**
   Copy the provided example environment file to create your active `.env` file:

   ```bash
   cp .env.example .env
   ```

3. **Update `.env`:**
   - `GEMINI_API_KEY`: Enter your Gemini API key for the Planner Agent.
   - `OLLAMA_API_BASE`: (Optional) Base URL for your local Ollama instance (Defaults to `http://localhost:11434`).
   - `OLLAMA_MODEL`: (Optional) Overrides the local model used for code execution.

4. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   # Ensure vector search dependencies are installed:
   pip install lancedb pyarrow aiohttp
   ```

## Usage

To start Swarm Coder, run the main entry point of the application:

```bash
python main.py
```

### Example Interaction
```text
System: "Agent initialized. What would you like to accomplish?"
User: "Write a script to analyze local log files and summarize the errors."
Agent: "Planning complete. Delegating data sanitization locally to Ollama, and analysis logic to Gemini..."
```

## Architecture Overview

- **The Planner (Gemini):** Acts as the "brain". It parses the user request, generates a sequential or parallel execution plan, and determines which model is best suited for each step.
- **The Executor (Ollama):** Acts as the local "worker". It receives granular tasks from the Planner, processes them locally without sending sensitive data to the cloud, and returns the output.
- **State Manager:** Keeps track of the workflow context, conversation memory, and intermediate results across the multi-agent system.

## Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page or submit a Pull Request.