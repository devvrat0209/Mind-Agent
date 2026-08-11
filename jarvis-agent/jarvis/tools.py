"""Tools the agent can use — including self-editing."""

import os
import subprocess
import difflib
import json
import shutil
from pathlib import Path
from typing import Optional


class ToolResult:
    """Standard result from any tool."""
    def __init__(self, output: str, error: bool = False, data: Optional[dict] = None):
        self.output = output
        self.error = error
        self.data = data or {}

    def __repr__(self):
        prefix = "❌" if self.error else "✓"
        return f"{prefix} {self.output[:200]}"


class ToolRegistry:
    """Registry of all tools the agent can call."""

    def __init__(self, config):
        self.config = config
        self.edit_stack = []  # for rollback

        # Device tools (full system access)
        from .device import DeviceTools
        self.device_tools = DeviceTools(config)

        self._tools = {
            "read_file": self.read_file,
            "write_file": self.write_file,
            "edit_file": self.edit_file,
            "list_files": self.list_files,
            "run_code": self.run_code,
            "shell": self.shell,
            "self_inspect": self.self_inspect,
            "git_diff": self.git_diff,
            "git_commit": self.git_commit,
            "rollback": self.rollback,
            "search_code": self.search_code,
            # Device tools
            "system_info": self._device_call("system_info"),
            "list_processes": self._device_call("list_processes"),
            "network_info": self._device_call("network_info"),
            "disk_usage": self._device_call("disk_usage"),
            "screenshot": self._device_call("screenshot"),
            "clipboard_read": self._device_call("clipboard_read"),
            "clipboard_write": self._device_call("clipboard_write"),
            "open_app": self._device_call("open_app"),
            "download_file": self._device_call("download_file"),
            "notify": self._device_call("notify"),
            "media_capture": self._device_call("media_capture"),
            "environment_vars": self._device_call("environment_vars"),
        }

    def _device_call(self, name: str):
        """Wrap a device tool as a ToolResult-returning callable."""
        def wrapper(**kwargs):
            result = self.device_tools.call(name, kwargs)
            return ToolResult(result["output"], error=result.get("error", False), data=result.get("data", {}))
        return wrapper

    @property
    def tool_schemas(self) -> list[dict]:
        """OpenAI-format tool schemas for the LLM."""
        code_tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file's contents. Can read the agent's own source files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path (relative to workspace or absolute)"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create or overwrite a file. Use to create new tools, modules, or modify existing ones.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "content": {"type": "string", "description": "Full file content to write"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Surgical edit: find text in a file and replace it. Safer than write_file for small changes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "old_text": {"type": "string", "description": "Text to find (will replace first match)"},
                            "new_text": {"type": "string", "description": "Replacement text"},
                        },
                        "required": ["path", "old_text", "new_text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Directory path (default: workspace)", "default": "."},
                            "recursive": {"type": "boolean", "default": False},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_code",
                    "description": "Execute Python code and return stdout/stderr. For testing ideas or running computations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Python code to execute"},
                        },
                        "required": ["code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shell",
                    "description": "Run a shell command. Use for git, pip, tests, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Shell command to run"},
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "self_inspect",
                    "description": "List the agent's own source files with sizes. Use to understand yourself before self-editing.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "git_diff",
                    "description": "Show git diff of changes made.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "git_commit",
                    "description": "Commit current changes with a message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Commit message"},
                        },
                        "required": ["message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "rollback",
                    "description": "Undo the last file edit.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search for text/regex across files in the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Text or pattern to search for"},
                            "path": {"type": "string", "description": "Directory to search in", "default": "."},
                        },
                        "required": ["query"],
                    },
                },
            },
        ]
        return code_tools + self.device_tools.tool_schemas

    def call(self, name: str, args: dict) -> ToolResult:
        """Execute a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(f"Unknown tool: {name}", error=True)
        try:
            return tool(**args)
        except Exception as e:
            return ToolResult(f"Error in {name}: {e}", error=True)

    # --- Tool implementations ---

    def _resolve_path(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.config.workspace / p
        return p.resolve()

    def _is_allowed_path(self, path: Path) -> bool:
        """Check if we're allowed to edit this path."""
        if self.config.allow_outside_edits:
            return True
        # Allow edits within workspace and within agent's own source dir
        try:
            path.relative_to(self.config.workspace)
            return True
        except ValueError:
            pass
        try:
            path.relative_to(self.config.home_dir)
            return True
        except ValueError:
            pass
        return False

    def read_file(self, path: str) -> ToolResult:
        p = self._resolve_path(path)
        if not p.exists():
            return ToolResult(f"File not found: {p}", error=True)
        if p.stat().st_size > self.config.max_file_size_kb * 1024:
            return ToolResult(f"File too large ({p.stat().st_size // 1024}KB). Increase max_file_size_kb.", error=True)
        try:
            content = p.read_text(encoding="utf-8")
            return ToolResult(content, data={"path": str(p), "lines": content.count("\n") + 1})
        except UnicodeDecodeError:
            return ToolResult(f"Binary file: {p}", error=True)

    def write_file(self, path: str, content: str) -> ToolResult:
        p = self._resolve_path(path)
        if not self._is_allowed_path(p):
            return ToolResult(f"Not allowed to write outside workspace: {p}", error=True)

        # Save old content for rollback
        old_content = None
        if p.exists():
            old_content = p.read_text(encoding="utf-8")

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

        self.edit_stack.append({
            "type": "write",
            "path": str(p),
            "old_content": old_content,
            "new_content": content,
        })

        action = "Updated" if old_content is not None else "Created"
        return ToolResult(f"{action} {p} ({len(content)} chars)", data={"path": str(p)})

    def edit_file(self, path: str, old_text: str, new_text: str) -> ToolResult:
        p = self._resolve_path(path)
        if not p.exists():
            return ToolResult(f"File not found: {p}", error=True)
        if not self._is_allowed_path(p):
            return ToolResult(f"Not allowed to edit outside workspace: {p}", error=True)

        content = p.read_text(encoding="utf-8")
        if old_text not in content:
            # Try fuzzy matching
            lines_old = content.splitlines()
            lines_find = old_text.splitlines()
            best_ratio = 0
            best_pos = -1
            for i in range(len(lines_old) - len(lines_find) + 1):
                chunk = "\n".join(lines_old[i:i + len(lines_find)])
                ratio = difflib.SequenceMatcher(None, chunk, old_text).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_pos = i
            if best_ratio > 0.7 and best_pos >= 0:
                # Fuzzy match found — replace it
                start = sum(len(lines_old[j]) + 1 for j in range(best_pos))
                end = start + len("\n".join(lines_old[best_pos:best_pos + len(lines_find)]))
                new_content = content[:start] + new_text + content[end:]
            else:
                return ToolResult(f"Text not found in {p} (best fuzzy match: {best_ratio:.0%})", error=True)
        else:
            new_content = content.replace(old_text, new_text, 1)

        # Show diff
        old_lines = content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_lines, new_lines, fromfile=str(p), tofile=str(p), n=3))

        p.write_text(new_content, encoding="utf-8")
        self.edit_stack.append({
            "type": "edit",
            "path": str(p),
            "old_content": content,
            "new_content": new_content,
        })

        return ToolResult(f"Edited {p}\n{diff}", data={"path": str(p), "diff": diff})

    def list_files(self, path: str = ".", recursive: bool = False) -> ToolResult:
        p = self._resolve_path(path)
        if not p.is_dir():
            return ToolResult(f"Not a directory: {p}", error=True)

        if recursive:
            entries = []
            for root, dirs, files in os.walk(p):
                # Skip hidden and __pycache__
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and d != "node_modules"]
                for f in sorted(files):
                    fp = Path(root) / f
                    rel = fp.relative_to(p)
                    size = fp.stat().st_size
                    entries.append(f"  {rel}  ({size:,} bytes)")
        else:
            entries = []
            for item in sorted(p.iterdir()):
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    entries.append(f"  📁 {item.name}/")
                else:
                    entries.append(f"  📄 {item.name}  ({item.stat().st_size:,} bytes)")

        return ToolResult(f"{p}:\n" + "\n".join(entries))

    def run_code(self, code: str) -> ToolResult:
        """Execute Python code in a subprocess."""
        result = subprocess.run(
            ["python3", "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(self.config.workspace),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            return ToolResult(output, error=True)
        return ToolResult(output or "(no output)")

    def shell(self, command: str) -> ToolResult:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(self.config.workspace),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        return ToolResult(output, error=result.returncode != 0)

    def self_inspect(self) -> ToolResult:
        """List the agent's own source files."""
        src = self.config.source_dir
        lines = [f"JARVIS Agent Source ({src}):"]
        total_size = 0
        for f in sorted(src.rglob("*.py")):
            if "__pycache__" in str(f):
                continue
            rel = f.relative_to(src)
            size = f.stat().st_size
            total_size += size
            content = f.read_text()
            n_funcs = content.count("def ")
            n_classes = content.count("class ")
            lines.append(f"  📄 {rel}  ({size:,} bytes, {n_funcs} funcs, {n_classes} classes)")
        lines.append(f"\n  Total: {total_size:,} bytes across {len(lines)-1} files")
        return ToolResult("\n".join(lines))

    def git_diff(self) -> ToolResult:
        result = subprocess.run(
            ["git", "diff"],
            capture_output=True, text=True,
            cwd=str(self.config.workspace),
        )
        return ToolResult(result.stdout or "(no changes)")

    def git_commit(self, message: str) -> ToolResult:
        # Stage all changes
        subprocess.run(["git", "add", "-A"], capture_output=True, cwd=str(self.config.workspace))
        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True, text=True,
            cwd=str(self.config.workspace),
        )
        if result.returncode != 0:
            return ToolResult(f"Commit failed: {result.stderr}", error=True)
        return ToolResult(f"Committed: {message}")

    def rollback(self) -> ToolResult:
        if not self.edit_stack:
            return ToolResult("Nothing to rollback", error=True)

        last = self.edit_stack.pop()
        path = Path(last["path"])

        if last["old_content"] is None:
            # File was created — delete it
            if path.exists():
                path.unlink()
            return ToolResult(f"Rolled back: deleted {path}")
        else:
            # Restore old content
            path.write_text(last["old_content"], encoding="utf-8")
            return ToolResult(f"Rolled back: restored {path}")

    def search_code(self, query: str, path: str = ".") -> ToolResult:
        p = self._resolve_path(path)
        matches = []
        for f in p.rglob("*.py"):
            if "__pycache__" in str(f) or ".git" in str(f):
                continue
            try:
                for i, line in enumerate(f.read_text().splitlines(), 1):
                    if query.lower() in line.lower():
                        rel = f.relative_to(p)
                        matches.append(f"  {rel}:{i}: {line.strip()}")
            except Exception:
                continue
        if not matches:
            return ToolResult(f"No matches for '{query}'")
        return ToolResult(f"Found {len(matches)} matches:\n" + "\n".join(matches[:50]))
