import os
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AppConfig:
    """
    Configuration for the Swarm Coder application.
    """
    workspace_root: str = field(default_factory=lambda: os.getcwd())
    
    def set_workspace_root(self, path: str) -> None:
        """Sets the absolute workspace root."""
        self.workspace_root = os.path.abspath(path)
        
    def get_abs_path(self, file_path: str) -> str:
        """Helper to get absolute path relative to workspace_root if not already absolute."""
        if os.path.isabs(file_path):
            return file_path
        return os.path.join(self.workspace_root, file_path)

# Global configuration instance
config = AppConfig()
