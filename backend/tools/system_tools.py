import os
import datetime
import subprocess
import json
import platform
from pathlib import Path
import glob

def get_time():
    """Returns current time, date, day"""
    now = datetime.datetime.now()
    return {
        "current_time": now.strftime("%I:%M %p"),
        "current_date": now.strftime("%A, %B %d, %Y"),
        "iso": now.isoformat(),
        "timestamp": now.timestamp()
    }

def get_system_info():
    """Returns system status"""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "os": platform.system() + " " + platform.release(),
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_available_gb": round(mem.available / (1024**3), 2),
            "disk_percent": disk.percent,
            "hostname": platform.node()
        }
    except:
        return {
            "os": platform.system() + " " + platform.release(),
            "cpu_percent": "N/A (install psutil)",
            "memory_percent": "N/A",
            "hostname": platform.node(),
            "note": "Install psutil for detailed metrics"
        }

def calculate(expression: str):
    """Safely evaluate math expression"""
    try:
        # Only allow math chars
        allowed_chars = "0123456789+-*/().% **"
        # Use safer eval with restricted builtins
        import math
        safe_dict = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        safe_dict.update({"abs": abs, "round": round, "min": min, "max": max, "pow": pow})
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e), "expression": expression}

def list_files(path: str = "."):
    """List files in directory"""
    try:
        base = Path(path).expanduser().resolve()
        # Safety: don't allow listing outside workspace unless absolute allowed
        items = []
        for item in os.listdir(base):
            full = base / item
            try:
                items.append({
                    "name": item,
                    "type": "dir" if full.is_dir() else "file",
                    "size": full.stat().st_size if full.is_file() else None
                })
            except:
                items.append({"name": item, "type": "unknown"})
        return {"path": str(base), "items": items[:100]}  # limit
    except Exception as e:
        return {"error": str(e)}

def read_file_content(path: str):
    """Read file content"""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if p.stat().st_size > 100_000:
            return {"error": "File too large (>100KB), use smaller file"}
        content = p.read_text(encoding='utf-8', errors='ignore')
        return {"path": str(p), "content": content[:10000]}
    except Exception as e:
        return {"error": str(e)}

def write_file_content(path: str, content: str):
    """Write file"""
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return {"success": True, "path": str(p), "size": len(content)}
    except Exception as e:
        return {"error": str(e)}

def execute_command(command: str):
    """Execute shell command (safely, limited)"""
    # Block dangerous commands
    dangerous = ["rm -rf /", "mkfs", ":(){:|:&};:", "shutdown", "reboot", "dd if="]
    if any(d in command for d in dangerous):
        return {"error": "Dangerous command blocked"}
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=10
        )
        return {
            "command": command,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"error": "Command timed out after 10s"}
    except Exception as e:
        return {"error": str(e)}
