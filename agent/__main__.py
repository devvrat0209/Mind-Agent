from .core import AURAAgent
from .config import AgentConfig

if __name__ == "__main__":
    config = AgentConfig()
    agent = AURAAgent(config)
    print(f"AURA {config.agent_name} ready with {len(agent.registry.tools)} tools")
