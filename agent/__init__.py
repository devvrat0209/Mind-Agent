"""
AURA - Autonomous Universal Reasoning Agent
A powerful, tool-using AI agent that works with any LLM.
"""
__version__ = "0.1.0"
__agent_name__ = "AURA"

from .core import AURAAgent
from .config import AgentConfig

__all__ = ["AURAAgent", "AgentConfig"]
