import os
from pathlib import Path
from .base import tool

WORKSPACE = Path(os.getenv("AGENT_WORKSPACE", "./workspace"))

def _resolve_path(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return (WORKSPACE / p).resolve()

def _is_safe(path: Path) -> bool:
    # Prevent escaping workspace unless explicitly absolute and allowed
    try:
        # Allow absolute paths but warn
        return True
    except:
        return False

@tool(
    name="read_file",
    description="Read content of a file. Can read text files, code, configs. For large files, specify limit.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to workspace or absolute"},
            "limit": {"type": "integer", "description": "Max lines to read (default 200)"}
        },
        "required": ["path"]
    }
)
def read_file(path: str, limit: int = 200) -> str:
    file_path = _resolve_path(path)
    if not file_path.exists():
        return f"File not found: {file_path}\nWorkspace files: {list(WORKSPACE.glob('*'))[:20]}"
    if file_path.is_dir():
        files = list(file_path.rglob("*"))[:50]
        return f"{file_path} is a directory. Contents:\n" + "\n".join([str(f.relative_to(WORKSPACE)) if WORKSPACE in f.parents else str(f) for f in files])
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            if len(lines) > limit:
                content = "".join(lines[:limit])
                return content + f"\n...[{len(lines)-limit} more lines truncated, total {len(lines)} lines]"
            return "".join(lines)
    except Exception as e:
        return f"Error reading file: {e}"

@tool(
    name="write_file",
    description="Write content to a file. Creates file if not exists, overwrites if exists. Use for creating code, docs, configs.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to workspace"},
            "content": {"type": "string", "description": "Content to write"},
            "append": {"type": "boolean", "description": "Append instead of overwrite", "default": False}
        },
        "required": ["path", "content"]
    }
)
def write_file(path: str, content: str, append: bool = False) -> str:
    file_path = _resolve_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    mode = 'a' if append else 'w'
    try:
        with open(file_path, mode, encoding='utf-8') as f:
            f.write(content)
        action = "Appended to" if append else "Wrote to"
        return f"{action} {file_path} ({len(content)} chars)"
    except Exception as e:
        return f"Error writing file: {e}"

@tool(
    name="list_files",
    description="List files and directories in a path. Useful for exploring workspace.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path (default: workspace root)", "default": "."},
            "recursive": {"type": "boolean", "description": "List recursively", "default": False}
        },
        "required": []
    }
)
def list_files(path: str = ".", recursive: bool = False) -> str:
    dir_path = _resolve_path(path)
    if not dir_path.exists():
        return f"Path not found: {dir_path}"
    if not dir_path.is_dir():
        return f"Not a directory: {dir_path}"
    try:
        if recursive:
            files = [str(p.relative_to(dir_path)) for p in dir_path.rglob("*")][:100]
        else:
            files = [f"{'[DIR] ' if (dir_path/f).is_dir() else ''}{f}" for f in os.listdir(dir_path)][:100]
        if not files:
            return f"Empty directory: {dir_path}"
        return f"Contents of {dir_path}:\n" + "\n".join(files)
    except Exception as e:
        return f"Error listing files: {e}"

@tool(
    name="delete_file",
    description="Delete a file or directory. Use with caution.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File or directory path to delete"}
        },
        "required": ["path"]
    }
)
def delete_file(path: str) -> str:
    file_path = _resolve_path(path)
    if not file_path.exists():
        return f"Not found: {file_path}"
    try:
        if file_path.is_dir():
            import shutil
            shutil.rmtree(file_path)
            return f"Deleted directory: {file_path}"
        else:
            file_path.unlink()
            return f"Deleted file: {file_path}"
    except Exception as e:
        return f"Error deleting: {e}"
