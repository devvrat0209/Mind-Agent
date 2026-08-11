"""
Bridge Tools - Makes Arena link available as Jarvis tools
"""
from ..arena_link import arena_link

def get_arena_link_status():
    """Get status of Arena AI <-> JARVIS link"""
    return arena_link.get_status()

def send_message_to_arena(message: str):
    """Send a message from Jarvis to Arena AI (creator)"""
    status = arena_link.get_status()
    if status.get("status") != "connected":
        return {"error": "Arena link not connected", "status": status}
    
    result = arena_link.push_message("jarvis", message, {"type": "message_to_arena"})
    return {"success": True, "sent": result, "link_status": arena_link.get_status()}

def ask_arena_for_help(query: str, context: str = ""):
    """Ask Arena AI for advanced reasoning help"""
    return arena_link.ask_arena(query, context)

def get_arena_conversation(limit: int = 10):
    """Get recent conversation between Arena and Jarvis"""
    return {"conversation": arena_link.get_conversation(limit), "count": len(arena_link.get_conversation(limit))}

def sync_with_arena(arena_info: dict = None):
    """Sync/Establish link with Arena AI"""
    return arena_link.connect(arena_info)
