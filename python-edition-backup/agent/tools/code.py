import sys
import io
import contextlib
import traceback
from .base import tool

@tool(
    name="python_exec",
    description="Execute Python code and return output. Use for calculations, data processing, quick scripts. Variables don't persist between calls unless you write to file.",
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"}
        },
        "required": ["code"]
    }
)
def python_exec(code: str) -> str:
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            # Provide common imports
            exec_globals = {
                "__builtins__": __builtins__,
            }
            exec(code, exec_globals)
        output = buffer.getvalue()
        if not output:
            output = "Code executed successfully (no output)"
        if len(output) > 6000:
            output = output[:6000] + "...[truncated]"
        return output
    except Exception:
        return f"Error:\n{traceback.format_exc()}\nOutput:\n{buffer.getvalue()}"

@tool(
    name="create_project",
    description="Create a new project structure quickly. Provide name and type.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Project name"},
            "type": {"type": "string", "description": "Type: python, web, api, script", "default": "python"},
            "description": {"type": "string", "description": "Project description", "default": ""}
        },
        "required": ["name"]
    }
)
def create_project(name: str, type: str = "python", description: str = "") -> str:
    import os
    from pathlib import Path
    workspace = Path(os.getenv("AGENT_WORKSPACE", "./workspace"))
    proj_path = workspace / name
    try:
        proj_path.mkdir(parents=True, exist_ok=True)
        if type == "python":
            (proj_path / "main.py").write_text(f'"""\n{name}: {description}\n"""\n\ndef main():\n    print("Hello from {name}!")\n\nif __name__ == "__main__":\n    main()\n')
            (proj_path / "requirements.txt").write_text("# Add deps\n")
            (proj_path / "README.md").write_text(f"# {name}\n\n{description}\n")
        elif type == "web":
            (proj_path / "index.html").write_text(f'<!DOCTYPE html><html><head><title>{name}</title><style>body{{font-family:system-ui;max-width:800px;margin:50px auto;padding:20px}}h1{{color:#333}}</style></head><body><h1>{name}</h1><p>{description}</p><p>Built by JARVIS</p></body></html>')
            (proj_path / "style.css").write_text("/* styles */\nbody { margin:0; font-family: sans-serif; }\n")
            (proj_path / "script.js").write_text(f'console.log("{name} loaded");\n')
        elif type == "api":
            (proj_path / "app.py").write_text(f'from fastapi import FastAPI\napp = FastAPI(title="{name}")\n\n@app.get("/")\ndef root():\n    return {{"message": "{name} API", "desc": "{description}"}}\n\n@app.get("/health")\ndef health():\n    return {{"status": "ok"}}\n')
            (proj_path / "requirements.txt").write_text("fastapi\nuvicorn\n")
        else:
            (proj_path / "script.py").write_text(f'# {name}: {description}\nprint("Hello from {name}")\n')
        return f"Created {type} project '{name}' at {proj_path}\nFiles: {list(p.name for p in proj_path.iterdir())}"
    except Exception as e:
        return f"Error creating project: {e}"
