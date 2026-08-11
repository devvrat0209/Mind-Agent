import json
import os
from datetime import datetime
from pathlib import Path

MEMORY_DIR = Path(__file__).parent.parent.parent / "memory"
MEMORY_DIR.mkdir(exist_ok=True)
MEMORY_FILE = MEMORY_DIR / "memory.json"
REMINDERS_FILE = MEMORY_DIR / "reminders.json"

def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except:
        return default

def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

def remember(key: str, value: str):
    """Store a memory"""
    memories = _load_json(MEMORY_FILE, {})
    memories[key] = {
        "value": value,
        "timestamp": datetime.now().isoformat()
    }
    _save_json(MEMORY_FILE, memories)
    return {"success": True, "key": key, "value": value}

def recall(key: str = None):
    """Recall memories - if key provided, get specific, else list all"""
    memories = _load_json(MEMORY_FILE, {})
    if key:
        if key in memories:
            return {"key": key, "memory": memories[key]}
        # fuzzy search
        matches = {k: v for k, v in memories.items() if key.lower() in k.lower() or key.lower() in v["value"].lower()}
        if matches:
            return {"matches": matches}
        return {"error": f"No memory found for '{key}'"}
    else:
        return {"memories": memories, "count": len(memories)}

def forget(key: str):
    """Delete a memory"""
    memories = _load_json(MEMORY_FILE, {})
    if key in memories:
        del memories[key]
        _save_json(MEMORY_FILE, memories)
        return {"success": True, "deleted": key}
    return {"error": f"Memory '{key}' not found"}

def set_reminder(text: str, time_str: str = None):
    """Set a reminder"""
    reminders = _load_json(REMINDERS_FILE, [])
    reminder = {
        "id": len(reminders) + 1,
        "text": text,
        "time": time_str or "asap",
        "created": datetime.now().isoformat(),
        "completed": False
    }
    reminders.append(reminder)
    _save_json(REMINDERS_FILE, reminders)
    return {"success": True, "reminder": reminder}

def list_reminders():
    """List all reminders"""
    reminders = _load_json(REMINDERS_FILE, [])
    return {"reminders": reminders, "count": len(reminders), "pending": [r for r in reminders if not r["completed"]]}

def complete_reminder(reminder_id: int):
    """Mark reminder done"""
    reminders = _load_json(REMINDERS_FILE, [])
    for r in reminders:
        if r["id"] == reminder_id:
            r["completed"] = True
            r["completed_at"] = datetime.now().isoformat()
            _save_json(REMINDERS_FILE, reminders)
            return {"success": True, "reminder": r}
    return {"error": f"Reminder {reminder_id} not found"}
