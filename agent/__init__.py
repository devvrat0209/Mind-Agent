"""A self-editing agent with persistent memory."""
from .config import CONFIG, Config
from .core import Agent
from .memory import Memory

__all__ = ["Agent", "Memory", "Config", "CONFIG"]
__version__ = "0.1.0"
