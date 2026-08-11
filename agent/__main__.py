from .core import JARVISAgent
from .config import AgentConfig

if __name__ == "__main__":
    config = AgentConfig()
    agent = JARVISAgent(config)
    print(f"🤖 {config.agent_name} {config.agent_description} ready with {len(agent.registry.tools)} tools")
    print("At your service, Sir.")
