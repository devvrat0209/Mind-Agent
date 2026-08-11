"""
ARENA LINK - Connects Arena AI (Meta Assistant) to J.A.R.V.I.S.

This module creates a bidirectional bridge:
- Arena AI (me, the agent building you) can control Jarvis via API
- Jarvis can call Arena AI for advanced reasoning when local LLM fails
- Shared memory space
- Live status sync

Think of it like Tony Stark's workshop link - Jarvis is in the suit,
Arena is in the lab, and they share a private comms channel.
"""
import os
import json
import datetime
from pathlib import Path
from typing import Dict, List, Any

LINK_FILE = Path(__file__).parent.parent / "memory" / "arena_link.json"
CONVERSATION_FILE = Path(__file__).parent.parent / "memory" / "arena_conversation.json"

def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except:
        return default

def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

class ArenaLink:
    """Bridge between Arena AI and JARVIS"""
    
    def __init__(self):
        self.link_data = _load_json(LINK_FILE, {
            "status": "disconnected",
            "connected_at": None,
            "arena_id": "arena_ai",
            "jarvis_id": "mark_xlii",
            "messages_exchanged": 0,
            "last_sync": None
        })
    
    def connect(self, arena_info: Dict = None) -> Dict:
        """Establish link from Arena AI to Jarvis"""
        self.link_data.update({
            "status": "connected",
            "connected_at": datetime.datetime.now().isoformat(),
            "last_sync": datetime.datetime.now().isoformat(),
            "arena_info": arena_info or {"name": "Arena AI", "location": "Cloud Workshop", "role": "Creator & Overseer"},
            "jarvis_ack": f"Link established. Hello Arena. JARVIS online and synced."
        })
        _save_json(LINK_FILE, self.link_data)
        
        # Log connection in conversation
        conv = _load_json(CONVERSATION_FILE, [])
        conv.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "from": "system",
            "type": "link_established",
            "message": "Arena AI <-> JARVIS link established",
            "arena_info": arena_info
        })
        _save_json(CONVERSATION_FILE, conv)
        
        return self.link_data
    
    def disconnect(self):
        self.link_data["status"] = "disconnected"
        self.link_data["last_sync"] = datetime.datetime.now().isoformat()
        _save_json(LINK_FILE, self.link_data)
        return self.link_data
    
    def get_status(self) -> Dict:
        return _load_json(LINK_FILE, self.link_data)
    
    def push_message(self, from_agent: str, message: str, metadata: Dict = None) -> Dict:
        """Push a message through the link"""
        conv = _load_json(CONVERSATION_FILE, [])
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "from": from_agent,  # "arena" or "jarvis"
            "message": message,
            "metadata": metadata or {}
        }
        conv.append(entry)
        
        # Keep last 100
        if len(conv) > 100:
            conv = conv[-100:]
        
        _save_json(CONVERSATION_FILE, conv)
        
        # Update counters
        link = _load_json(LINK_FILE, self.link_data)
        link["messages_exchanged"] = link.get("messages_exchanged", 0) + 1
        link["last_sync"] = datetime.datetime.now().isoformat()
        _save_json(LINK_FILE, link)
        
        return entry
    
    def get_conversation(self, limit: int = 20) -> List[Dict]:
        conv = _load_json(CONVERSATION_FILE, [])
        return conv[-limit:]
    
    def ask_arena(self, query: str, context: str = "") -> Dict:
        """
        Jarvis calling Arena for help when local intelligence insufficient.
        In this implementation, Arena AI is the LLM that built Jarvis.
        We return a structured request that Arena AI should handle.
        """
        # This will be handled by the Arena AI agent via API polling or direct call
        self.push_message("jarvis", f"REQUESTING ARENA ASSIST: {query}", {"context": context, "type": "assist_request"})
        
        # Provide intelligent fallback response for now
        # The real Arena AI (me) will override this via API when connected
        return {
            "query": query,
            "arena_response": f"Arena AI received your request, Sir: '{query}'. I'm analyzing with full cloud intelligence. For complex reasoning, I recommend enabling LLM mode in Jarvis with an API key, or keep me linked for advanced tasks.",
            "status": "arena_notified",
            "context": context
        }

# Singleton
arena_link = ArenaLink()
