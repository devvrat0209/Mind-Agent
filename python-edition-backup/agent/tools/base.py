from typing import Dict, Any, List, Callable
from pydantic import BaseModel, Field
import json

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Any = Field(exclude=True)
    
    def to_openai_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    def to_prompt_description(self) -> str:
        params = self.parameters.get("properties", {})
        required = self.parameters.get("required", [])
        param_str = ", ".join([
            f"{k}{'*' if k in required else ''}: {v.get('description', v.get('type', ''))}"
            for k, v in params.items()
        ])
        return f"- {self.name}({param_str}): {self.description}"

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        
    def register(self, tool: ToolDefinition):
        self.tools[tool.name] = tool
        
    def get_tool(self, name: str) -> ToolDefinition:
        return self.tools.get(name)
    
    def list_tools(self) -> List[ToolDefinition]:
        return list(self.tools.values())
    
    def get_openai_tools(self) -> List[Dict]:
        return [t.to_openai_tool() for t in self.tools.values()]
    
    def get_prompt_description(self) -> str:
        return "\n".join([t.to_prompt_description() for t in self.tools.values()])
    
    def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        tool = self.get_tool(name)
        if not tool:
            return f"Error: Tool '{name}' not found. Available: {list(self.tools.keys())}"
        try:
            result = tool.func(**arguments)
            # Ensure result is string
            if not isinstance(result, str):
                result = json.dumps(result, indent=2, default=str)
            # Truncate very long results
            if len(result) > 10000:
                result = result[:10000] + f"\n...[truncated, total length {len(result)} chars]"
            return result
        except Exception as e:
            return f"Error executing {name}: {str(e)}"

# Global registry
registry = ToolRegistry()

def tool(name: str, description: str, parameters: Dict[str, Any]):
    """Decorator to register a tool"""
    def decorator(func: Callable):
        tool_def = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            func=func
        )
        registry.register(tool_def)
        return func
    return decorator
