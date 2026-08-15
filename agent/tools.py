"""Tool registry exposed to the model.

Each tool is a plain Python function decorated with ``@tool``; the decorator
records an OpenAI-style JSON schema so the same registry drives both the
function-calling API and the local CLI (``/tools``).
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable

from . import selfedit
from .config import CONFIG, PROJECT_ROOT
from .memory import Memory


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., Any]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


REGISTRY: dict[str, Tool] = {}


def tool(description: str, **properties: dict[str, Any]):
    """Register a function as a tool. Keyword args describe its parameters.

    Mark a parameter optional by adding ``"optional": True`` to its schema.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        required = [k for k, v in properties.items() if not v.pop("optional", False)]
        REGISTRY[func.__name__] = Tool(
            name=func.__name__,
            description=description,
            parameters={
                "type": "object",
                "properties": properties,
                "required": required,
            },
            func=func,
        )
        return func

    return decorator


def _s(desc: str, optional: bool = False) -> dict[str, Any]:
    d: dict[str, Any] = {"type": "string", "description": desc}
    if optional:
        d["optional"] = True
    return d


# --------------------------------------------------------------------- memory
@tool(
    "Store a durable fact in long-term memory. Use for user preferences, "
    "project details, and lessons learned so they survive restarts.",
    key=_s("Short unique identifier, e.g. 'user.name' or 'pref.language'"),
    value=_s("The information to remember"),
    tags=_s("Optional comma-separated tags", optional=True),
)
def remember(key: str, value: str, tags: str = "", *, memory: Memory) -> str:
    memory.remember(key, value, tags)
    return f"remembered {key!r}"


@tool(
    "Look up a fact previously stored in long-term memory by exact key.",
    key=_s("The key to look up"),
)
def recall(key: str, *, memory: Memory) -> str:
    value = memory.recall(key)
    return value if value is not None else f"(nothing stored under {key!r})"


@tool(
    "Full-text search long-term memory across keys, values and tags.",
    query=_s("Substring to search for"),
)
def search_memory(query: str, *, memory: Memory) -> str:
    hits = memory.search(query)
    if not hits:
        return "(no matches)"
    return json.dumps([h.as_dict() for h in hits], indent=2)


@tool(
    "Delete a fact from long-term memory.",
    key=_s("The key to delete"),
)
def forget(key: str, *, memory: Memory) -> str:
    return f"deleted {key!r}" if memory.forget(key) else f"{key!r} was not stored"


# ---------------------------------------------------------------- self-access
@tool("List the source files that make up this agent.")
def list_own_code(*, memory: Memory) -> str:
    return "\n".join(selfedit.list_source_files())


@tool(
    "Read one of the agent's own source files (line-numbered).",
    path=_s("Path relative to the agent package, e.g. 'tools.py'"),
)
def read_own_code(path: str, *, memory: Memory) -> str:
    try:
        return selfedit.read_source(path)
    except selfedit.SelfEditError as exc:
        return f"error: {exc}"


@tool(
    "Replace an exact snippet inside one of the agent's own source files. "
    "Preferred over write_own_code for small changes. Python files are "
    "syntax-checked; invalid edits are rejected and the file is left intact.",
    path=_s("Path relative to the agent package"),
    find=_s("Exact text to find (must be unique in the file)"),
    replace=_s("Replacement text"),
)
def patch_own_code(path: str, find: str, replace: str, *, memory: Memory) -> str:
    result = selfedit.patch_source(path, find, replace)
    memory.journal(
        "self-edit" if result.ok else "self-edit-failed",
        f"patch {path}: {result.message}",
        result.diff,
    )
    return f"{'OK' if result.ok else 'FAILED'}: {result.message}\n{result.diff[:2000]}"


@tool(
    "Create or fully overwrite one of the agent's own source files.",
    path=_s("Path relative to the agent package"),
    content=_s("Complete new file content"),
)
def write_own_code(path: str, content: str, *, memory: Memory) -> str:
    result = selfedit.write_source(path, content)
    memory.journal(
        "self-edit" if result.ok else "self-edit-failed",
        f"write {path}: {result.message}",
        result.diff,
    )
    return f"{'OK' if result.ok else 'FAILED'}: {result.message}\n{result.diff[:2000]}"


@tool(
    "Undo the most recent change to one of the agent's files by restoring "
    "its latest backup.",
    path=_s("Path relative to the agent package"),
)
def rollback_own_code(path: str, *, memory: Memory) -> str:
    result = selfedit.rollback(path)
    memory.journal("rollback", f"{path}: {result.message}")
    return f"{'OK' if result.ok else 'FAILED'}: {result.message}"


@tool("Show the recent self-modification history from the journal.")
def change_history(*, memory: Memory) -> str:
    entries = memory.recent_journal()
    if not entries:
        return "(no recorded changes)"
    return "\n".join(f"[{e['kind']}] {e['summary']}" for e in entries)


@tool(
    "Import-check the agent package in a subprocess to verify the current "
    "code still loads. Run this after editing yourself.",
)
def self_check(*, memory: Memory) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", "import importlib, agent, agent.tools, agent.core; print('import ok')"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    out = (proc.stdout + proc.stderr).strip()
    memory.journal("self-check", f"exit={proc.returncode}", out)
    return f"exit={proc.returncode}\n{out[:2000]}"


# ---------------------------------------------------------------------- shell
@tool(
    "Run a shell command in the project directory (tests, git, grep...).",
    command=_s("The command to run"),
)
def run_shell(command: str, *, memory: Memory) -> str:
    if not CONFIG.allow_shell:
        return "shell access is disabled (AGENT_ALLOW_SHELL=0)"
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=CONFIG.shell_timeout,
        )
    except subprocess.TimeoutExpired:
        return f"timed out after {CONFIG.shell_timeout}s"
    out = (proc.stdout + proc.stderr)[:4000]
    return f"exit={proc.returncode}\n{out}"


# ----------------------------------------------------------------- dispatcher
def schemas() -> list[dict[str, Any]]:
    return [t.schema() for t in REGISTRY.values()]


def call(name: str, arguments: dict[str, Any], memory: Memory) -> str:
    tool_obj = REGISTRY.get(name)
    if tool_obj is None:
        return f"error: unknown tool {name!r}"
    try:
        result = tool_obj.func(**arguments, memory=memory)
    except TypeError as exc:
        return f"error: bad arguments for {name}: {exc}"
    except Exception as exc:  # tools must never crash the loop
        return f"error: {type(exc).__name__}: {exc}"
    return result if isinstance(result, str) else json.dumps(result, default=str)
