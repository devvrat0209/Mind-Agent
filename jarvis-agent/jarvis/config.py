"""Configuration — LLM provider, paths, settings."""

import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Config:
    # LLM
    llm_model: str = field(default_factory=lambda: os.getenv("JARVIS_LLM", "openai/gpt-4o"))
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096

    # Paths
    home_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.resolve())
    workspace: Path = field(default_factory=lambda: Path.cwd())

    # Safety
    auto_approve: bool = field(default_factory=lambda: os.getenv("JARVIS_AUTO_APPROVE", "0") == "1")
    allow_outside_edits: bool = False

    # Memory
    max_context_messages: int = 50
    max_file_size_kb: int = 500  # refuse to read files larger than this

    # Agent
    agent_name: str = "JARVIS"
    max_tool_calls_per_turn: int = 10
    edit_history_size: int = 100

    @property
    def source_dir(self) -> Path:
        return self.home_dir / "jarvis"

    @property
    def is_self_edit_allowed(self) -> bool:
        return True  # always — that's the whole point
