import subprocess
import os
from pathlib import Path
from .base import tool

WORKSPACE = Path(os.getenv("AGENT_WORKSPACE", "./workspace"))

@tool(
    name="shell_exec",
    description="Execute a shell command. Use for running code, git, npm, python, ls, etc. Returns stdout + stderr. Workspace is current dir.",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
        },
        "required": ["command"]
    }
)
def shell_exec(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        output += f"Exit code: {result.returncode}"
        if len(output) > 8000:
            output = output[:8000] + "...[truncated]"
        return output or "Command executed with no output"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s: {command}"
    except Exception as e:
        return f"Error executing command: {e}"

@tool(
    name="get_datetime",
    description="Get current date and time. Useful for scheduling, logs, timestamps.",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    }
)
def get_datetime() -> str:
    from datetime import datetime
    now = datetime.now()
    return f"Current datetime: {now.isoformat()} | {now.strftime('%A, %B %d, %Y %I:%M %p')} | Unix: {int(now.timestamp())}"

@tool(
    name="calculator",
    description="Evaluate mathematical expressions. Supports Python math.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression, e.g. '2**10 + sqrt(25)'"}
        },
        "required": ["expression"]
    }
)
def calculator(expression: str) -> str:
    try:
        import math
        allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        allowed.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})
        result = eval(expression, {"__builtins__": {}}, allowed)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Calculation error: {e}"
