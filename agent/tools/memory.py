import json
import os
from pathlib import Path
from datetime import datetime
from .base import tool

MEMORY_FILE = Path(os.getenv("AGENT_MEMORY_FILE", "./memory/memory.jsonl"))

def _ensure_memory():
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not MEMORY_FILE.exists():
        MEMORY_FILE.touch()

@tool(
    name="memory_add",
    description="Save important information to long-term memory. Use for facts, preferences, learnings, todo, etc.",
    parameters={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Information to remember"},
            "category": {"type": "string", "description": "Category: fact, preference, task, learning, etc.", "default": "general"},
            "importance": {"type": "integer", "description": "1-10 importance", "default": 5}
        },
        "required": ["content"]
    }
)
def memory_add(content: str, category: str = "general", importance: int = 5) -> str:
    _ensure_memory()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "importance": importance,
        "content": content
    }
    try:
        with open(MEMORY_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")
        return f"Saved to memory [{category}]: {content[:100]}..."
    except Exception as e:
        return f"Memory save error: {e}"

@tool(
    name="memory_search",
    description="Search long-term memory for relevant information.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for memory"},
            "limit": {"type": "integer", "description": "Max results", "default": 10}
        },
        "required": ["query"]
    }
)
def memory_search(query: str, limit: int = 10) -> str:
    _ensure_memory()
    if not MEMORY_FILE.exists() or MEMORY_FILE.stat().st_size == 0:
        return "Memory is empty."
    results = []
    q_lower = query.lower()
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if q_lower in entry.get('content', '').lower() or q_lower in entry.get('category', '').lower():
                        results.append(entry)
                except:
                    continue
        # If no keyword match, return recent
        if not results:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                all_entries = [json.loads(l) for l in f if l.strip()]
                results = all_entries[-limit:]
        results = sorted(results, key=lambda x: x.get('importance', 0), reverse=True)[:limit]
        if not results:
            return f"No memory found for '{query}'"
        formatted = []
        for r in results:
            formatted.append(f"[{r['timestamp'][:19]}] ({r['category']} ⭐{r['importance']}): {r['content']}")
        return "\n".join(formatted)
    except Exception as e:
        return f"Memory search error: {e}"

@tool(
    name="memory_list",
    description="List recent memories.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Number of recent memories", "default": 20}
        },
        "required": []
    }
)
def memory_list(limit: int = 20) -> str:
    _ensure_memory()
    try:
        if not MEMORY_FILE.exists() or MEMORY_FILE.stat().st_size == 0:
            return "Memory empty"
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            entries = [json.loads(l) for l in lines[-limit:] if l.strip()]
        if not entries:
            return "Memory empty"
        formatted = []
        for r in reversed(entries):
            formatted.append(f"[{r['timestamp'][:19]}] ({r['category']}): {r['content']}")
        return "\n".join(formatted)
    except Exception as e:
        return f"Error listing memory: {e}"
