"""Configuration for the self-editing agent.

Everything is env-overridable so the agent can be pointed at any
OpenAI-compatible endpoint (OpenAI, OpenRouter, Groq, Ollama, vLLM...).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Root of the agent's own source tree (the directory this file lives in).
AGENT_ROOT = Path(__file__).resolve().parent
# Repository / project root (parent of the package).
PROJECT_ROOT = AGENT_ROOT.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # --- LLM ---
    provider: str = field(default_factory=lambda: os.getenv("AGENT_PROVIDER", "openai"))
    base_url: str = field(
        default_factory=lambda: os.getenv("AGENT_BASE_URL", "https://api.openai.com/v1")
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("AGENT_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    )
    model: str = field(default_factory=lambda: os.getenv("AGENT_MODEL", "gpt-4o-mini"))
    temperature: float = field(default_factory=lambda: float(os.getenv("AGENT_TEMPERATURE", "0.2")))
    request_timeout: int = field(default_factory=lambda: int(os.getenv("AGENT_TIMEOUT", "120")))

    # --- Agent behaviour ---
    max_steps: int = field(default_factory=lambda: int(os.getenv("AGENT_MAX_STEPS", "12")))
    max_history_messages: int = field(
        default_factory=lambda: int(os.getenv("AGENT_MAX_HISTORY", "40"))
    )

    # --- Storage ---
    state_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("AGENT_STATE_DIR", str(PROJECT_ROOT / ".agent_state"))
        ).expanduser()
    )

    # --- Self-editing safety ---
    allow_self_edit: bool = field(default_factory=lambda: _env_bool("AGENT_ALLOW_SELF_EDIT", True))
    allow_shell: bool = field(default_factory=lambda: _env_bool("AGENT_ALLOW_SHELL", True))
    shell_timeout: int = field(default_factory=lambda: int(os.getenv("AGENT_SHELL_TIMEOUT", "60")))
    require_confirmation: bool = field(
        default_factory=lambda: _env_bool("AGENT_CONFIRM_EDITS", False)
    )

    @property
    def db_path(self) -> Path:
        return self.state_dir / "memory.sqlite3"

    @property
    def backup_dir(self) -> Path:
        return self.state_dir / "backups"

    def ensure_dirs(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)


CONFIG = Config()
