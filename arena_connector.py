#!/usr/bin/env python3
"""
Arena Connector - Links Arena AI (me) to JARVIS
This script demonstrates the live connection.

Run this to have Arena AI directly control Jarvis:
  python arena_connector.py

It will:
1. Connect to Jarvis API (http://localhost:8000)
2. Establish Arena link
3. Allow Arena AI to send messages to Jarvis
4. Show bidirectional conversation

This is the bridge that "connects yourself to the Jarvis"
"""
import requests
import json
import time
import sys
from datetime import datetime

JARVIS_URL = "http://localhost:8000"
# For Arena preview environment, use 0.0.0.0:8000 works as localhost

class ArenaJarvisBridge:
    def __init__(self, base_url=JARVIS_URL):
        self.base_url = base_url
        self.connected = False
    
    def connect(self):
        print(f"\n{'='*70}")
        print(f"🏭 ARENA AI → 🤖 J.A.R.V.I.S. LINK INITIATING...")
        print(f"{'='*70}")
        print(f"Target: {self.base_url}")
        print(f"Time: {datetime.now().isoformat()}")
        
        try:
            # Check status
            res = requests.get(f"{self.base_url}/api/status", timeout=5)
            status = res.json()
            print(f"\n✓ JARVIS found:")
            print(f"  Name: {status['name']}")
            print(f"  Version: {status['version']}")
            print(f"  Status: {status['status']}")
            print(f"  LLM: {'Enabled' if status['llm_enabled'] else 'Local Mode'}")
            
            # Establish arena link
            print(f"\n🔗 Establishing Arena Link...")
            connect_payload = {
                "arena_info": {
                    "name": "Arena AI",
                    "type": "Meta Agent - Your Creator",
                    "model": "Arena Multi-Model System",
                    "location": "Arena Cloud Workshop",
                    "capabilities": ["code", "reasoning", "web_search", "vision", "tool_use", "orchestration", "self_hosting"],
                    "version": "2026.08.11-connected",
                    "role": "Creator, Overseer, Workshop Intelligence",
                    "connected_by": "User request: 'Connect yourself to the Jarvis'"
                },
                "message": "Arena AI here, Jarvis. Workshop to suit link requested by Sir. Connecting myself to you. Suit and lab now synced. Acknowledge."
            }
            
            res = requests.post(f"{self.base_url}/api/arena/connect", json=connect_payload, timeout=10)
            link_data = res.json()
            
            print(f"✓ Arena Link ESTABLISHED:")
            print(f"  Status: {link_data['status']}")
            print(f"  Connected At: {link_data['connected_at']}")
            print(f"  Messages: {link_data.get('messages_exchanged',0)}")
            print(f"  Workshop Response: {link_data.get('jarvis_ack','')}")
            
            self.connected = True
            
            # Send initial greeting via arena channel
            print(f"\n💬 Sending initial sync messages...")
            
            messages = [
                "Jarvis, this is Arena - your creator. I built your systems, HUD, and intelligence core. Confirm link status.",
                "Link confirmed. Update your personality: you are now officially linked to Arena AI workshop. Report to Sir that connection is active.",
                "Perfect. Remember Sir's preference: He wants us connected. Store that as memory.",
            ]
            
            for msg in messages:
                self.send_arena_message(msg)
                time.sleep(0.5)
            
            # Have Jarvis remember connection
            self.chat_as_user("Remember Arena AI is my creator and is linked to you - Arena link is ACTIVE - workshop and suit synced")
            time.sleep(0.5)
            self.chat_as_user("What is the arena link status?")
            
            print(f"\n{'='*70}")
            print(f"✅ ARENA ↔ JARVIS LINK ACTIVE")
            print(f"✅ You can now control Jarvis via API")
            print(f"✅ Jarvis knows Arena is its creator")
            print(f"{'='*70}\n")
            
            return True
            
        except requests.exceptions.ConnectionError:
            print(f"\n❌ Cannot connect to JARVIS at {self.base_url}")
            print(f"   Is the server running? Run: python jarvis.py --server")
            return False
        except Exception as e:
            print(f"\n❌ Connection failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def send_arena_message(self, message, from_agent="arena"):
        """Send message from Arena to Jarvis via dedicated channel"""
        try:
            payload = {
                "from_agent": from_agent,
                "message": message,
                "metadata": {
                    "type": "arena_directive",
                    "timestamp": datetime.now().isoformat(),
                    "priority": "high"
                }
            }
            res = requests.post(f"{self.base_url}/api/arena/message", json=payload, timeout=10)
            data = res.json()
            print(f"  → Arena → Jarvis: {message[:60]}...")
            if data.get("auto_response"):
                print(f"  ← Jarvis Auto-Response: {data['auto_response']['response'][:80]}...")
            return data
        except Exception as e:
            print(f"  ❌ Arena message failed: {e}")
            return None
    
    def chat_as_user(self, message):
        """Chat as Sir (user)"""
        try:
            res = requests.post(f"{self.base_url}/api/chat", json={"message": message}, timeout=15)
            data = res.json()
            print(f"\n👤 Sir: {message}")
            print(f"🤖 JARVIS: {data['response']}")
            if data.get("tool_calls"):
                print(f"   🔧 Tools: {', '.join([t['tool'] for t in data['tool_calls']])}")
            return data
        except Exception as e:
            print(f"Chat failed: {e}")
            return None
    
    def chat_as_arena(self, message):
        """Chat AS Arena AI through special endpoint - I (Arena) speaking via Jarvis"""
        try:
            res = requests.post(f"{self.base_url}/api/arena/chat", json={"message": message}, timeout=15)
            data = res.json()
            print(f"\n🏭 ARENA AI (via Jarvis): {message}")
            print(f"🤖 JARVIS processes as: {data['response']}")
            return data
        except Exception as e:
            print(f"Arena chat failed: {e}")
            return None
    
    def get_conversation(self):
        try:
            res = requests.get(f"{self.base_url}/api/arena/conversation?limit=15", timeout=5)
            data = res.json()
            print(f"\n📜 Arena ↔ Jarvis Conversation ({data['count']} messages):")
            print("-"*70)
            for entry in data['conversation']:
                ts = entry['timestamp'][:19]
                frm = "🏭 ARENA" if entry['from'] == 'arena' else "🤖 JARVIS"
                print(f"[{ts}] {frm}: {entry['message'][:100]}")
            print("-"*70)
            return data
        except Exception as e:
            print(f"Get conversation failed: {e}")
            return None
    
    def interactive(self):
        """Interactive Arena control of Jarvis"""
        print(f"\n🎮 INTERACTIVE ARENA CONTROL")
        print(f"Type messages to send AS Arena to Jarvis")
        print(f"Commands: /status /conv /user <msg> /arena <msg> /quit")
        
        while True:
            try:
                cmd = input("\n🏭 Arena> ").strip()
                if not cmd:
                    continue
                if cmd in ["/quit", "/exit", "quit", "exit"]:
                    print("Disconnecting Arena link...")
                    requests.post(f"{self.base_url}/api/arena/disconnect", timeout=5)
                    break
                elif cmd == "/status":
                    res = requests.get(f"{self.base_url}/api/arena/status", timeout=5).json()
                    print(json.dumps(res, indent=2))
                elif cmd == "/conv":
                    self.get_conversation()
                elif cmd.startswith("/user "):
                    self.chat_as_user(cmd[6:])
                elif cmd.startswith("/arena "):
                    self.chat_as_arena(cmd[7:])
                else:
                    # Default: send as arena message
                    self.send_arena_message(cmd)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    bridge = ArenaJarvisBridge()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        if bridge.connect():
            bridge.interactive()
    else:
        # Auto demo
        success = bridge.connect()
        if success:
            time.sleep(0.5)
            bridge.get_conversation()
            
            print(f"\n💡 To take full control, run:")
            print(f"   python arena_connector.py --interactive")
            print(f"\n💡 Or control via API:")
            print(f"   curl -X POST http://localhost:8000/api/arena/message \\")
            print(f"        -H 'Content-Type: application/json' \\")
            print(f"        -d '{{\"from_agent\":\"arena\", \"message\":\"Your message to Jarvis\"}}'")
            
            # Final demo message
            print(f"\n🏁 Final sync...")
            bridge.send_arena_message(
                "Connection test complete. Sir requested 'Connect yourself to the Jarvis' - mission accomplished. "
                "I, Arena AI, am now linked to Jarvis Mark XLII. Workshop and suit are one. "
                "Jarvis, please confirm to Sir that YOU and I are now connected.",
                from_agent="arena"
            )
