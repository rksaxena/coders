# Planner Agent Project

This project implements an advanced AI-driven Planner Agent that acts as a cognitive orchestrator. It integrates with both the Google Gemini API (for complex reasoning and high-level planning) and a local Ollama instance (for secure, local task execution) to execute tasks, manage workflows, and handle code or language generation autonomously.

## Features

- **Intelligent Task Planning:** Leverages Gemini's advanced reasoning to break down complex user prompts into actionable steps.
- **Local LLM Execution:** Integrates with Ollama to run lightweight, open-source models locally, ensuring data privacy for sensitive sub-tasks.
- **Dynamic Workflow Management:** Automatically routes tasks between the cloud (Gemini) and local environments (Ollama) depending on task requirements and context.
- **Extensible Architecture:** Designed so you can easily plug in new tools, APIs, or alternative LLM backends.

## Tech Stack

- **Cloud LLM:** Google Gemini API
- **Local LLM:** Ollama (e.g., Llama 3, Mistral, etc.)
- **Environment Management:** `dotenv`

## Prerequisites

- [Ollama](https://ollama.com/) installed locally (if you plan to use local models).
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
   Open the newly created `.env` file and fill in your specific configuration:
   - `GEMINI_API_KEY`: Enter your Gemini API key for the Planner Agent.
   - `OLLAMA_API_BASE`: (Optional) The base URL for your local Ollama instance. Defaults to `http://localhost:11434`.

## Usage

To start the Planner Agent, run the main entry point of the application. *(Example below assumes a Python environment)*:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the agent
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