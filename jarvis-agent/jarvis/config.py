"""Configuration — LLM provider, paths, settings."""

import os
from pathlib import Path
from dataclasses import dataclass, field


def _load_dotenv():
    """Load .env file from workspace or agent home."""
    try:
        from dotenv import load_dotenv
        # Try workspace first, then agent home
        for p in [Path.cwd() / ".env", Path(__file__).parent.parent / ".env"]:
            if p.exists():
                load_dotenv(p, override=False)
                return
    except ImportError:
        pass


_load_dotenv()


@dataclass
class Config:
    # LLM
    llm_model: str = field(default_factory=lambda: os.getenv("JARVIS_LLM", "openai/gpt-4o"))
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096

    # NVIDIA NIM
    nim_api_key: str = field(default_factory=lambda: os.getenv("NVIDIA_NIM_API_KEY", ""))
    nim_api_base: str = field(default_factory=lambda: os.getenv(
        "NVIDIA_NIM_API_BASE", "https://integrate.api.nvidia.com/v1"))
    nim_mode: str = field(default_factory=lambda: os.getenv("JARVIS_NIM_MODE", "hosted"))

    # REST API
    api_enabled: bool = field(default_factory=lambda: os.getenv("JARVIS_API_ENABLED", "0") == "1")
    api_host: str = field(default_factory=lambda: os.getenv("JARVIS_API_HOST", "127.0.0.1"))
    api_port: int = field(default_factory=lambda: int(os.getenv("JARVIS_API_PORT", "8088")))
    api_key: str = field(default_factory=lambda: os.getenv("JARVIS_API_KEY", ""))

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

    @property
    def uses_nim(self) -> bool:
        return self.llm_model.startswith("nvidia_nim/")

    @property
    def device(self):
        """Detected hardware for this machine (cached)."""
        from .platform_detect import device as _device
        return _device()

    def llm_kwargs(self) -> dict:
        """Provider-specific extras for the LLM call."""
        if not self.uses_nim:
            return {}
        kw = {"api_base": self.nim_api_base}
        if self.nim_api_key:
            kw["api_key"] = self.nim_api_key
        elif self.nim_mode == "local":
            kw["api_key"] = "not-needed"   # local containers accept anything
        return kw
