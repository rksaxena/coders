import os
from typing import Any, Dict, List

import yaml

DEFAULT_PLANNER_MODELS = [
    {"name": "gemini-2.5-flash", "type": "cloud", "priority": 0},
    {"name": "gemma4:26b", "type": "local", "priority": 1},
]
DEFAULT_CODER_MODELS = [
    {"name": "ollama/qwen2.5-coder:7b", "type": "local", "priority": 0}
]


class AppConfig:
    """
    Configuration for the Swarm Coder application.
    Parses config.yaml and manages workspace state.
    """

    def __init__(self, config_path: str = None):
        self.workspace_root = os.getcwd()

        if config_path is None:
            # Point directly to the config.yaml in the same directory
            config_path = os.path.join(os.path.dirname(__file__), "config.yaml")

        self.config_path = config_path
        self.data: Dict[str, Any] = self._load_yaml()

        self.models = self.data.get("models", {})
        self.settings = self.data.get("settings", {})
        self.prompts = self.data.get("prompts", {})

        self.planner_models = self._parse_model_config(
            "planner", DEFAULT_PLANNER_MODELS
        )
        self.coder_models = self._parse_model_config("coder", DEFAULT_CODER_MODELS)

        # Expose the primary models as strings for backward compatibility
        self.planner_model = (
            self.planner_models[0]["name"]
            if self.planner_models
            else DEFAULT_PLANNER_MODELS[0]["name"]
        )
        self.coder_model = (
            self.coder_models[0]["name"]
            if self.coder_models
            else DEFAULT_CODER_MODELS[0]["name"]
        )

        self.ollama_base_url = self.models.get(
            "ollama_base_url", "http://127.0.0.1:11434"
        )
        self.planner_instructions = self.prompts.get("planner_instructions", "")
        self.coder_instructions = self.prompts.get("coder_instructions", "")
        self.coder_task_prompt = self.prompts.get(
            "coder_task_prompt",
            "GOAL: {goal}\nTarget File: {target_file}\n{existing_content_prompt}\n"
            "IMPORTANT: You MUST output ONLY the complete implementation code "
            "enclosed in a single Markdown code block (```language ... ```).\n"
            "Do NOT provide any conversational text, explanations, or tool calls.",
        )
        self.reviewer_prompt = self.prompts.get(
            "reviewer_prompt",
            "You are an Expert Code Reviewer. Review the code in the workspace and "
            "verify if the following original tasks were implemented correctly and "
            "completely:\n"
            "{original_tasks_str}\n\n"
            "{workspace_context}\n"
            "Analyze the codebase for completeness, accuracy, and potential bugs. "
            "If there are issues, errors, or missing parts, output a detailed "
            "explanation, and you MUST generate a new ImplementationPlan "
            "(using the correct JSON format or tool) with specific tasks for the "
            "coders to fix them.\n"
            "If the work is 100% complete and accurate, output a short confirmation "
            "message and generate an ImplementationPlan with an empty tasks list.",
        )

        self.max_coders = self.settings.get("max_coders", 1)
        self.api_timeout = self.settings.get(
            "api_timeout", {"sock_read": 120, "connect": 15}
        )
        self.ollama_num_ctx = self.settings.get("ollama_num_ctx", 16384)
        self.ignore_dirs = set(
            self.settings.get("workspace", {}).get(
                "ignore_dirs",
                [".git", "__pycache__", "node_modules", "venv", ".venv", "env"],
            )
        )
        self.valid_exts = set(
            self.settings.get("workspace", {}).get(
                "valid_exts",
                [
                    ".py",
                    ".js",
                    ".ts",
                    ".jsx",
                    ".tsx",
                    ".html",
                    ".css",
                    ".json",
                    ".md",
                    ".txt",
                    ".yml",
                    ".yaml",
                ],
            )
        )

    def _parse_model_config(
        self, key: str, default: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        val = self.models.get(key, default)
        parsed_list = []

        if isinstance(val, str):
            for i, m in enumerate(val.split(",")):
                if m.strip():
                    m_str = m.strip()
                    m_type = (
                        "local"
                        if m_str.startswith("ollama/") or m_str.startswith("localhost")
                        else "cloud"
                    )
                    parsed_list.append({"name": m_str, "type": m_type, "priority": i})
        elif isinstance(val, list):
            for i, item in enumerate(val):
                if isinstance(item, str):
                    m_type = "local" if item.startswith("ollama/") else "cloud"
                    parsed_list.append({"name": item, "type": m_type, "priority": i})
                elif isinstance(item, dict) and "name" in item:
                    if "priority" not in item:
                        item["priority"] = i
                    if "type" not in item:
                        item["type"] = (
                            "local" if item["name"].startswith("ollama/") else "cloud"
                        )
                    parsed_list.append(item)
        else:
            parsed_list = default

        return sorted(parsed_list, key=lambda x: x.get("priority", 999))

    def get_model_iterator(self, role: str, current_agent_model: str = None):
        """
        Yields models in prioritized order for a specific role without needing
        state management.
        """
        if role == "planner":
            for m in self.planner_models:
                yield m

        elif role == "coder":
            seen_models = set()

            # 1. Yield the model explicitly attached to the agent (if any)
            if current_agent_model:
                c_name = (
                    current_agent_model.replace("ollama/", "")
                    if current_agent_model.startswith("ollama/")
                    else current_agent_model
                )
                seen_models.add(c_name)
                yield {"name": c_name, "type": "local"}

            # 2. Yield runtime override models from environment variables
            env_models = os.getenv("OLLAMA_MODEL")
            if env_models:
                for m in env_models.split(","):
                    m_clean = m.strip()
                    if m_clean and m_clean not in seen_models:
                        seen_models.add(m_clean)
                        yield {"name": m_clean, "type": "local"}

            # 3. Yield default configuration fallbacks ensuring no duplicates
            for fb in self.coder_models:
                fb_name = (
                    fb["name"].replace("ollama/", "")
                    if fb["name"].startswith("ollama/")
                    else fb["name"]
                )
                if fb_name not in seen_models:
                    seen_models.add(fb_name)
                    new_m = {"name": fb_name, "type": fb.get("type", "local")}
                    if "url" in fb:
                        new_m["url"] = fb["url"]
                    yield new_m

    def _load_yaml(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Failed to parse {self.config_path}: {e}")
        return {}

    def set_workspace_root(self, path: str) -> None:
        """Sets the absolute workspace root."""
        self.workspace_root = os.path.abspath(path)

    def get_abs_path(self, file_path: str) -> str:
        """Get the absolute path relative to workspace_root.

        If the provided path is already absolute, it is returned unchanged.
        """
        if os.path.isabs(file_path):
            return file_path
        return os.path.join(self.workspace_root, file_path)


# Expose a singleton instance
config = AppConfig()
