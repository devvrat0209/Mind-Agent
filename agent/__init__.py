"""
JARVIS - Just A Rather Very Intelligent System
A powerful, tool-using AI agent that works with any LLM.
"""
__version__ = "0.2.0"
__agent_name__ = "JARVIS"

from .core import AURAAgent as JARVISAgent
from .core import AURAAgent
from .config import AgentConfig

__all__ = ["JARVISAgent", "AURAAgent", "AgentConfig"]
