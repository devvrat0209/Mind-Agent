"""
JARVIS Web Server - FastAPI + WebSocket chat
Provides both API and beautiful web UI
"""

import os
import sys
from pathlib import Path
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from agent.config import AgentConfig
from agent.core import JARVISAgent

app = FastAPI(
    title="JARVIS Agent API",
    description="Just A Rather Very Intelligent System - API & Web UI",
    version="0.2.0"
)

# Store agents per session (simple in-memory)
agents: Dict[str, JARVISAgent] = {}

def get_agent(session_id: str = "default") -> JARVISAgent:
    if session_id not in agents:
        config = AgentConfig()
        agents[session_id] = JARVISAgent(config)
    return agents[session_id]

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    stream: bool = False

class ChatResponse(BaseModel):
    response: str
    steps: int
    tools_used: List[str] = []

@app.get("/", response_class=HTMLResponse)
async def web_ui():
    html_path = Path(__file__).parent / "web" / "index.html"
    if html_path.exists():
        return html_path.read_text()
    else:
        # Fallback inline UI
        return """
<!DOCTYPE html>
<html>
<head>
    <title>JARVIS - AI Agent</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#0f0f0f; color:#fff; height:100vh; display:flex; flex-direction:column; }
        .header { padding:20px; background:#1a1a1a; border-bottom:1px solid #2a2a2a; text-align:center; }
        .header h1 { font-size:24px; background: linear-gradient(90deg, #00d4ff, #7b68ee); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
        .header p { color:#888; font-size:14px; margin-top:5px; }
        .chat { flex:1; overflow-y:auto; padding:20px; max-width:800px; width:100%; margin:0 auto; }
        .msg { margin-bottom:20px; display:flex; gap:12px; }
        .msg.user { flex-direction:row-reverse; }
        .avatar { width:36px; height:36px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:bold; flex-shrink:0; }
        .user .avatar { background:#7b68ee; }
        .assistant .avatar { background:#00d4ff; color:#000; }
        .bubble { max-width:75%; padding:12px 16px; border-radius:18px; line-height:1.5; }
        .user .bubble { background:#7b68ee; border-bottom-right-radius:4px; }
        .assistant .bubble { background:#1e1e1e; border:1px solid #2a2a2a; border-bottom-left-radius:4px; }
        .bubble pre { background:#111; padding:10px; border-radius:8px; overflow-x:auto; margin:8px 0; }
        .input-area { padding:20px; background:#1a1a1a; border-top:1px solid #2a2a2a; max-width:800px; width:100%; margin:0 auto; display:flex; gap:10px; }
        .input-area input { flex:1; padding:14px 18px; border-radius:24px; border:1px solid #333; background:#0f0f0f; color:#fff; font-size:16px; outline:none; }
        .input-area input:focus { border-color:#7b68ee; }
        .input-area button { padding:12px 24px; border-radius:24px; border:none; background:linear-gradient(90deg, #00d4ff, #7b68ee); color:#000; font-weight:bold; cursor:pointer; }
        .input-area button:hover { opacity:0.9; }
        .tools-info { text-align:center; padding:10px; color:#666; font-size:12px; }
        .status { padding:10px; text-align:center; color:#888; font-style:italic; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 JARVIS</h1>
        <p>Just A Rather Very Intelligent System — Your All-Rounder AI</p>
    </div>
    <div class="chat" id="chat">
        <div class="msg assistant">
            <div class="avatar">A</div>
            <div class="bubble">👋 Hi! I'm <b>JARVIS</b>, your autonomous AI agent.<br><br>I can:<br>• 🌐 Search the web & fetch pages<br>• 📁 Read/write files & manage your workspace<br>• 💻 Run shell commands & Python code<br>• 🧠 Remember things long-term<br>• 🛠️ Create projects & automate tasks<br><br>What should we build today?</div>
        </div>
    </div>
    <div class="tools-info" id="status"></div>
    <div class="input-area">
        <input type="text" id="input" placeholder="Ask JARVIS to do something..." autofocus>
        <button onclick="send()">Send</button>
    </div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const statusEl = document.getElementById('status');

function addMsg(role, text) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.innerHTML = `<div class="avatar">${role==='user'?'U':'A'}</div><div class="bubble">${formatText(text)}</div>`;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}
function formatText(t) {
    // Basic markdown-ish
    t = t.replace(/\\n/g, '<br>');
    t = t.replace(/```([^`]+)```/g, '<pre>$1</pre>');
    t = t.replace(/\\*\\*([^*]+)\\*\\*/g, '<b>$1</b>');
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    // linkify
    return t;
}
let ws = null;
function connectWS() {
    const prot = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(prot + '//' + location.host + '/ws?session_id=default');
    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === 'status') {
            statusEl.textContent = data.text;
        } else if (data.type === 'token') {
            // streaming token - append to last assistant bubble
            let last = chat.querySelector('.msg.assistant:last-child .bubble');
            if (!last || last.dataset.final) {
                let d = addMsg('assistant', '');
                last = d.querySelector('.bubble');
                last.dataset.streaming = '1';
            }
            if (last.dataset.streaming) {
                last.innerHTML += formatText(data.text);
                chat.scrollTop = chat.scrollHeight;
            }
        } else if (data.type === 'final') {
            let last = chat.querySelector('.msg.assistant:last-child .bubble');
            if (last) {
                last.innerHTML = formatText(data.text);
                last.dataset.final = '1';
                delete last.dataset.streaming;
            } else {
                addMsg('assistant', data.text);
            }
            statusEl.textContent = `✅ Done in ${data.steps} steps`;
        } else if (data.type === 'error') {
            addMsg('assistant', '❌ Error: ' + data.text);
            statusEl.textContent = '';
        }
    };
}
connectWS();

async function send() {
    const msg = input.value.trim();
    if (!msg) return;
    addMsg('user', msg);
    input.value = '';
    statusEl.textContent = '🤖 JARVIS is thinking...';
    
    if (ws && ws.readyState === 1) {
        ws.send(JSON.stringify({message: msg}));
    } else {
        // fallback HTTP
        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({message: msg, session_id: 'default'})
            });
            const data = await res.json();
            addMsg('assistant', data.response);
            statusEl.textContent = `✅ Done in ${data.steps} steps`;
        } catch(e) {
            addMsg('assistant', '❌ ' + e.message);
        }
    }
}
input.addEventListener('keydown', (e) => { if (e.key==='Enter') send(); });
</script>
</body>
</html>
        """

@app.get("/api/tools")
async def list_tools():
    agent = get_agent()
    tools = agent.registry.list_tools()
    return {"tools": [{"name": t.name, "description": t.description, "params": t.parameters} for t in tools]}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_api(req: ChatRequest):
    try:
        agent = get_agent(req.session_id)
        response = agent.run(req.message, verbose=False)
        return ChatResponse(response=response, steps=agent.step_count)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/memory")
async def memory_api(limit: int = 20):
    try:
        from agent.tools.memory import memory_list
        result = memory_list(limit)
        return {"memory": result}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/memory/clear")
async def clear_memory_api():
    try:
        config = AgentConfig()
        if config.memory_file.exists():
            config.memory_file.write_text("")
        return {"status": "cleared"}
    except Exception as e:
        return {"error": str(e)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str = "default"):
    await websocket.accept()
    agent = get_agent(session_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            user_msg = data.get("message", "")
            
            if not user_msg.strip():
                continue
            
            await websocket.send_json({"type": "status", "text": f"🤖 JARVIS thinking (step 1/{agent.config.max_steps})..."})
            
            # For streaming, we need to capture
            # Since our LLM may not stream tool calls perfectly, we simulate
            try:
                # We will run with verbose callback that sends status updates
                # Simple version: run and send final
                # TODO: improve true streaming
                response = agent.run(user_msg, verbose=False)
                
                await websocket.send_json({
                    "type": "final",
                    "text": response,
                    "steps": agent.step_count
                })
            except Exception as e:
                await websocket.send_json({"type": "error", "text": str(e)})
                
    except WebSocketDisconnect:
        print(f"Client {session_id} disconnected")
    except Exception as e:
        print(f"WS error: {e}")
        try:
            await websocket.send_json({"type": "error", "text": str(e)})
        except:
            pass

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "JARVIS", "version": "0.2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
