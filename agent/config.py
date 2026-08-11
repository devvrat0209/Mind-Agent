import os
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class AgentConfig(BaseModel):
    # Identity
    agent_name: str = Field(default_factory=lambda: os.getenv("AGENT_NAME", "AURA"))
    agent_description: str = "Autonomous Universal Reasoning Agent - Your all-rounder AI companion"
    
    # LLM
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    openai_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    openai_base_url: Optional[str] = Field(default_factory=lambda: os.getenv("OPENAI_BASE_URL"))
    anthropic_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    google_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY"))
    ollama_base_url: str = Field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    ollama_model: str = Field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3"))
    
    # Agent behavior
    max_steps: int = Field(default_factory=lambda: int(os.getenv("AGENT_MAX_STEPS", "20")))
    verbose: bool = Field(default_factory=lambda: os.getenv("AGENT_VERBOSE", "true").lower() == "true")
    workspace_dir: Path = Field(default_factory=lambda: Path(os.getenv("AGENT_WORKSPACE", "./workspace")))
    memory_file: Path = Field(default_factory=lambda: Path(os.getenv("AGENT_MEMORY_FILE", "./memory/memory.jsonl")))
    
    # Tools
    enable_web_search: bool = Field(default_factory=lambda: os.getenv("ENABLE_WEB_SEARCH", "true").lower() == "true")
    enable_shell: bool = Field(default_factory=lambda: os.getenv("ENABLE_SHELL", "true").lower() == "true")
    enable_filesystem: bool = Field(default_factory=lambda: os.getenv("ENABLE_FILESYSTEM", "true").lower() == "true")
    enable_code_exec: bool = Field(default_factory=lambda: os.getenv("ENABLE_CODE_EXEC", "true").lower() == "true")
    
    def model_post_init(self, __context):
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        
    def get_llm_config(self) -> dict:
        provider = self.llm_provider.lower()
        if provider == "openai":
            return {
                "api_key": self.openai_api_key,
                "base_url": self.openai_base_url or "https://api.openai.com/v1",
                "model": self.llm_model,
            }
        elif provider == "openrouter":
            return {
                "api_key": self.openai_api_key,
                "base_url": self.openai_base_url or "https://openrouter.ai/api/v1",
                "model": self.llm_model,
            }
        elif provider in ("groq", "together", "custom"):
            return {
                "api_key": self.openai_api_key,
                "base_url": self.openai_base_url,
                "model": self.llm_model,
            }
        elif provider == "ollama":
            return {
                "api_key": "ollama",
                "base_url": self.ollama_base_url,
                "model": self.ollama_model,
            }
        elif provider == "anthropic":
            return {
                "api_key": self.anthropic_api_key,
                "model": self.llm_model,
            }
        elif provider in ("google", "gemini"):
            return {
                "api_key": self.google_api_key,
                "model": self.llm_model,
            }
        else:
            return {
                "api_key": self.openai_api_key,
                "base_url": self.openai_base_url,
                "model": self.llm_model,
            }
