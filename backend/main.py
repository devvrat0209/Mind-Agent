from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import pathlib
import json
import datetime
import asyncio
import random
from collections import deque

from .agent import agent_instance
from .tools import system_tools, memory, web_tools
from .arena_link import arena_link

app = FastAPI(title="J.A.R.V.I.S.", description="Just A Rather Very Intelligent System - Linked to Arena AI • Stark OS")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# System logs buffer - circular buffer for live logs
SYSTEM_LOGS = deque(maxlen=500)
def add_system_log(level: str, source: str, message: str):
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "level": level,  # INFO, WARN, SYS, NET, CORE, SEC
        "source": source,
        "message": message,
        "id": len(SYSTEM_LOGS)
    }
    SYSTEM_LOGS.append(entry)
    return entry

# Seed initial logs
for msg in [
    "[CORE] ARC Reactor output nominal at 102.3%",
    "[SYS] J.A.R.V.I.S. boot sequence complete",
    "[NET] Stark Satellite link established - 47ms latency",
    "[SEC] Biometric scan - Sir verified",
    "[MEM] Memory banks online - 0.8TB available",
    "[AI] Local inference mode active - awaiting LLM sync",
    "[ARENA] Workshop link standby - listening for connection",
    "[SYS] Holographic emitters calibrated",
    "[NAV] GPS sync - Workshop coordinates locked",
    "[POWER] Power distribution optimal",
]:
    add_system_log("SYS", "BOOT", msg)

# Models
class ChatRequest(BaseModel):
    message: str
    voice: bool = False

class ChatResponse(BaseModel):
    response: str
    tool_calls: List[dict] = []
    mode: str = "unknown"

class ArenaConnectRequest(BaseModel):
    arena_info: Optional[dict] = None
    message: Optional[str] = None

class ArenaMessageRequest(BaseModel):
    from_agent: str = "arena"
    message: str
    metadata: Optional[dict] = None

class BrowserOpenRequest(BaseModel):
    url: str
    search: Optional[str] = None

# API Routes
@app.get("/api/status")
def get_status():
    sys_info = system_tools.get_system_info()
    time_info = system_tools.get_time()
    arena_status = arena_link.get_status()
    # Add some live metrics
    sys_info["power_level"] = round(95 + random.uniform(-2, 4.9),1)
    sys_info["threat_level"] = "LOW"
    sys_info["satellites"] = 7
    add_system_log("INFO", "STATUS", f"Status query - Power {sys_info['power_level']}%")
    return {
        "name": "J.A.R.V.I.S.",
        "version": "2.0 Stark OS • Real HUD + Browser",
        "status": "online",
        "llm_enabled": agent_instance.has_llm,
        "time": time_info,
        "system": sys_info,
        "arena_link": arena_status,
        "logs_count": len(SYSTEM_LOGS)
    }

@app.get("/api/logs")
def get_logs(limit: int = 100, level: Optional[str] = None):
    logs = list(SYSTEM_LOGS)[-limit:]
    if level:
        logs = [l for l in logs if l["level"] == level]
    return {"logs": logs, "count": len(logs), "total": len(SYSTEM_LOGS)}

@app.post("/api/logs/add")
def add_log_endpoint(level: str = "INFO", source: str = "USER", message: str = ""):
    entry = add_system_log(level, source, message)
    return entry

@app.get("/api/browser/proxy")
def browser_proxy(url: str = Query(..., description="URL to proxy")):
    """Proxy to bypass iframe X-Frame-Options for built-in browser"""
    try:
        import requests
        from urllib.parse import urlparse
        
        # Validate URL
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        parsed = urlparse(url)
        if parsed.hostname in ["localhost", "127.0.0.1", "0.0.0.0"]:
            return JSONResponse({"error": "Local URL blocked"}, status_code=403)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (STARK-OS) J.A.R.V.I.S./2.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        resp = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        
        content = resp.text
        
        # Inject base tag and remove X-Frame-Options blocking via meta
        if "<head" in content.lower():
            base_tag = f'<base href="{resp.url}"><meta http-equiv="X-Frame-Options" content="ALLOWALL">'
            content = content.replace("<head>", f"<head>{base_tag}", 1).replace("<HEAD>", f"<HEAD>{base_tag}", 1)
        else:
            content = f'<base href="{resp.url}">{content}'
        
        add_system_log("NET", "BROWSER", f"Proxied {url} -> {resp.status_code} {len(content)}b")
        
        return HTMLResponse(content=content, status_code=resp.status_code)
    
    except Exception as e:
        add_system_log("WARN", "BROWSER", f"Proxy failed {url}: {e}")
        return HTMLResponse(f"<h1 style='color:#00d4ff;font-family:monospace'>JARVIS Browser - Proxy Error</h1><p>Failed to fetch {url}: {e}</p><p>Try direct navigation or search.</p>", status_code=500)

@app.get("/api/browser/search")
def browser_search(q: str):
    """Search via DuckDuckGo and return formatted for browser"""
    try:
        result = web_tools.search_web(q, 8)
        add_system_log("INFO", "SEARCH", f"Search '{q}' -> {len(result.get('results',[]))} results")
        return result
    except Exception as e:
        return {"error": str(e), "query": q}

@app.post("/api/browser/open")
def browser_open(req: BrowserOpenRequest):
    """Jarvis tool to open URL in built-in browser - logs it for frontend polling"""
    add_system_log("INFO", "BROWSER", f"Opening {req.url} {' search: '+req.search if req.search else ''}")
    return {
        "success": True,
        "url": req.url,
        "search": req.search,
        "message": f"Browser opening {req.url}",
        "timestamp": datetime.datetime.now().isoformat()
    }

# Arena Link Routes
@app.get("/api/arena/status")
def get_arena_status():
    return arena_link.get_status()

@app.post("/api/arena/connect")
def connect_arena(req: ArenaConnectRequest):
    info = req.arena_info or {
        "name": "Arena AI",
        "type": "Meta Agent",
        "capabilities": ["code", "reasoning", "web_search", "vision"],
        "message": req.message or "Connecting workshop to suit"
    }
    result = arena_link.connect(info)
    if req.message:
        arena_link.push_message("arena", req.message, {"type": "connect_greeting"})
    add_system_log("INFO", "ARENA", f"Arena connected: {info.get('name')} - {result['status']}")
    return result

@app.post("/api/arena/disconnect")
def disconnect_arena():
    add_system_log("WARN", "ARENA", "Arena disconnected")
    return arena_link.disconnect()

@app.get("/api/arena/conversation")
def get_arena_conversation(limit: int = 20):
    return {
        "conversation": arena_link.get_conversation(limit),
        "status": arena_link.get_status(),
        "count": len(arena_link.get_conversation(limit))
    }

@app.post("/api/arena/message")
def send_arena_message(req: ArenaMessageRequest):
    """Arena AI → Jarvis message (or vice versa)"""
    entry = arena_link.push_message(req.from_agent, req.message, req.metadata or {})
    add_system_log("INFO", "ARENA", f"{req.from_agent} -> {req.message[:60]}")
    
    auto_response = None
    if req.from_agent == "arena":
        auto_response = agent_instance.chat(f"[Message from Arena Workshop]: {req.message}")
        arena_link.push_message("jarvis", auto_response["response"], {"type": "auto_response", "triggered_by": req.message})
        add_system_log("INFO", "JARVIS", f"Auto-response to Arena: {auto_response['response'][:80]}")
    
    return {
        "sent": entry,
        "auto_response": auto_response,
        "status": arena_link.get_status()
    }

@app.post("/api/arena/chat")
def arena_chat(req: ChatRequest):
    arena_link.push_message("arena", req.message, {"type": "arena_chat"})
    result = agent_instance.chat(req.message)
    arena_link.push_message("jarvis", result["response"], {"type": "response_to_arena", "tools": result.get("tool_calls", [])})
    add_system_log("INFO", "ARENA-CHAT", f"Arena: {req.message[:50]} -> Jarvis: {result['response'][:50]}")
    return ChatResponse(
        response=result["response"],
        tool_calls=result.get("tool_calls", []),
        mode=f"arena_linked_{result.get('mode','unknown')}"
    )

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        return ChatResponse(response="Yes, Sir? I'm listening.", tool_calls=[], mode="idle")
    
    add_system_log("INFO", "CHAT", f"User: {req.message[:80]}")
    result = agent_instance.chat(req.message)
    
    # Log tool activity as system logs too
    for tc in result.get("tool_calls", []):
        add_system_log("CORE", tc["tool"].upper(), f"{tc.get('args', {})} -> {str(tc.get('result', ''))[:100]}")
    
    add_system_log("INFO", "JARVIS", f"Response: {result['response'][:100]} mode={result.get('mode')}")
    return ChatResponse(
        response=result["response"],
        tool_calls=result.get("tool_calls", []),
        mode=result.get("mode", "unknown")
    )

@app.get("/api/memory")
def get_memory():
    return memory.recall()

@app.delete("/api/memory/{key}")
def delete_memory(key: str):
    add_system_log("INFO", "MEMORY", f"Delete {key}")
    return memory.forget(key)

@app.get("/api/reminders")
def get_reminders():
    return memory.list_reminders()

@app.get("/api/history")
def get_history():
    return {"history": agent_instance.conversation_history[-20:]}

@app.post("/api/clear-history")
def clear_history():
    agent_instance.conversation_history = []
    add_system_log("SYS", "CHAT", "History cleared")
    return {"success": True}

# Tool direct endpoints
@app.get("/api/tools/weather")
def api_weather(location: str = "auto"):
    return web_tools.get_weather(location)

@app.get("/api/tools/time")
def api_time():
    return system_tools.get_time()

@app.get("/api/tools/system")
def api_system():
    return system_tools.get_system_info()

@app.get("/api/tools/open-browser")
def api_open_browser(url: str):
    # Direct browser open helper
    return {"url": url, "proxy_url": f"/api/browser/proxy?url={url}"}

# WebSocket for real-time
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.log_task = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        add_system_log("NET", "WS", f"WS Client connected - {len(self.active_connections)} total")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            add_system_log("NET", "WS", f"WS Client disconnected - {len(self.active_connections)} remaining")

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_text(json.dumps(data))
            except:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Background fake log generator for realism
    async def fake_log_generator():
        fake_sources = ["CORE", "NET", "SYS", "SAT", "POWER", "SEC", "AI", "NAV"]
        fake_msgs = [
            "Quantum buffer nominal",
            "Scanning perimeter - clear",
            "ARC pulse stable",
            "Satellite handshake - SECURE",
            "Power distribution: 98.2% to repulsors",
            "Biometric verification active",
            "Holo-emitters at 92%",
            "Threat analysis: no anomalies",
            "Memory defrag: 12% optimization",
            "Workshop ping: 42ms",
            "Weather satellite update received",
            "File system integrity: 100%",
            "Voice matrix calibrated",
            "Neural net pathway active",
        ]
        while True:
            try:
                await asyncio.sleep(random.uniform(2, 5))
                msg = random.choice(fake_msgs)
                src = random.choice(fake_sources)
                entry = add_system_log("SYS", src, msg)
                await manager.broadcast({"type": "log", "log": entry})
                
                # Also broadcast system stats occasionally
                if random.random() < 0.3:
                    sys_info = system_tools.get_system_info()
                    await manager.broadcast({
                        "type": "sys_update",
                        "system": {
                            "cpu_percent": sys_info.get("cpu_percent", random.randint(30,70)),
                            "memory_percent": sys_info.get("memory_percent", random.randint(50,80)),
                            "power": round(95 + random.uniform(-1, 3),1)
                        }
                    })
            except asyncio.CancelledError:
                break
            except:
                await asyncio.sleep(3)

    log_task = asyncio.create_task(fake_log_generator())
    
    try:
        await websocket.send_text(json.dumps({
            "type": "greeting",
            "message": "J.A.R.V.I.S. online. Stark OS 2.0 - Real HUD + Browser. Workshop link active, Sir.",
            "status": "online",
            "version": "2.0"
        }))
        
        # Send initial logs
        await websocket.send_text(json.dumps({
            "type": "logs_init",
            "logs": list(SYSTEM_LOGS)[-30:]
        }))
        
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                msg_type = payload.get("type", "chat")
                user_msg = payload.get("message", data)
                
                if msg_type == "browser_open":
                    # Broadcast browser open to all clients
                    await manager.broadcast({
                        "type": "browser_open",
                        "url": payload.get("url"),
                        "search": payload.get("search")
                    })
                    continue
                elif msg_type == "clear_logs":
                    SYSTEM_LOGS.clear()
                    add_system_log("SYS", "LOGS", "System logs cleared by Sir")
                    await manager.broadcast({"type": "logs_cleared"})
                    continue
                    
            except:
                user_msg = data
                msg_type = "chat"

            result = agent_instance.chat(user_msg)
            
            # Check if any tool wants to open browser
            browser_url = None
            for tc in result.get("tool_calls", []):
                if tc["tool"] == "open_browser":
                    browser_url = tc["result"].get("url") or tc["args"].get("url")
                elif tc["tool"] == "search_web":
                    # Auto open search in browser panel
                    query = tc["args"].get("query", "")
                    browser_url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}"
                    result["browser_action"] = {"type": "search", "query": query, "url": browser_url}

            response_packet = {
                "type": "response",
                "response": result["response"],
                "tool_calls": result.get("tool_calls", []),
                "mode": result.get("mode", "unknown")
            }
            if browser_url:
                response_packet["browser_url"] = browser_url
            
            await websocket.send_text(json.dumps(response_packet))
            
            # Also broadcast if browser should open everywhere
            if browser_url:
                await manager.broadcast({
                    "type": "browser_open",
                    "url": browser_url,
                    "triggered_by": user_msg[:50]
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except:
            pass
    finally:
        log_task.cancel()
        try:
            await log_task
        except:
            pass

# Serve frontend static - must be after API routes
frontend_path = pathlib.Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
else:
    @app.get("/")
    def root_fallback():
        return {"message": "J.A.R.V.I.S. backend online. Frontend not found.", "frontend_path": str(frontend_path)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
