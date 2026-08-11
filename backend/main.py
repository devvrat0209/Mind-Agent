from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import pathlib
import json

from .agent import agent_instance
from .tools import system_tools, memory, web_tools

app = FastAPI(title="J.A.R.V.I.S.", description="Just A Rather Very Intelligent System")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ChatRequest(BaseModel):
    message: str
    voice: bool = False

class ChatResponse(BaseModel):
    response: str
    tool_calls: List[dict] = []
    mode: str = "unknown"

# API Routes
@app.get("/api/status")
def get_status():
    sys_info = system_tools.get_system_info()
    time_info = system_tools.get_time()
    return {
        "name": "J.A.R.V.I.S.",
        "version": "1.0 Stark Industries",
        "status": "online",
        "llm_enabled": agent_instance.has_llm,
        "time": time_info,
        "system": sys_info
    }

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        return ChatResponse(response="Yes, Sir? I'm listening.", tool_calls=[], mode="idle")
    result = agent_instance.chat(req.message)
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

# WebSocket for real-time
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "greeting",
            "message": "J.A.R.V.I.S. online. Good to see you, Sir.",
            "status": "online"
        }))
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                user_msg = payload.get("message", data)
            except:
                user_msg = data

            result = agent_instance.chat(user_msg)
            await websocket.send_text(json.dumps({
                "type": "response",
                "response": result["response"],
                "tool_calls": result.get("tool_calls", []),
                "mode": result.get("mode", "unknown")
            }))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
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
