# J.A.R.V.I.S. - Just A Rather Very Intelligent System

> Inspired by Tony Stark's AI from Iron Man. A fully functional AI agent with voice, memory, tools, and a Stark Industries HUD.

![JARVIS](https://img.shields.io/badge/JARVIS-Online-00d4ff?style=for-the-badge) ![Version](https://img.shields.io/badge/Version-Mark%20XLII-ff0000?style=for-the-badge)

## ✨ Features - What Makes This JARVIS

### 🧠 Intelligence Modes
- **LLM Mode**: Plug in OpenAI / Groq / Ollama for GPT-4 level reasoning with full tool-calling
- **Local Mode**: No API key needed! Intelligent rule-based agent that works offline

### 🎤 Voice - Talk Like Tony Stark
- Wake word: Say **"Jarvis"** + command (e.g., "Jarvis, what's the weather?")
- Web Speech API for STT (speech-to-text) + TTS (text-to-speech)
- Visual audio bars reacting to voice
- Toggle voice ON/OFF, MIC ON/OFF, Wake Word ON/OFF

### 🛠️ Tools (Like Real JARVIS)
- **Time & Date** - Real-time clock
- **System Diagnostics** - CPU, memory, OS status
- **Weather Satellite** - Live weather via Open-Meteo (no key)
- **Web Search** - DuckDuckGo instant answers
- **File System** - List, read, write files
- **Calculator** - Math with python math library
- **Memory Core** - Long-term memory (`remember X is Y`)
- **Reminders** - Task management
- **Shell** - Safe command execution
- **Code Execution** - Create files with code

### 🎨 UI - Stark Industries HUD
- Iron Man themed HUD with reactor core animation
- Canvas-based animated rings and ticks
- System diagnostic bars
- Tool activity log (shows what JARVIS is doing)
- Memory banks display
- Responsive design

### 🌐 Deployment Modes
- **Web App**: Full HUD in browser (FastAPI + vanilla JS)
- **CLI**: Terminal mode `python jarvis.py`
- **Server**: `python jarvis.py --server`

---

## 🚀 Quick Start

### 1. Install
```bash
pip install -r backend/requirements.txt

# For system metrics (optional)
pip install psutil
```

### 2. Run - No API Key Needed!
```bash
# CLI Mode
python jarvis.py

# Web HUD (best experience)
python jarvis.py --server
# Then open http://localhost:8000
```

### 3. Add Brain (Optional but Powerful)
Create `.env`:
```bash
cp .env.example .env
# Edit .env and add your key
```

**Options:**

**A) OpenAI (most capable):**
```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

**B) Groq (fast & free tier):**
```
OPENAI_API_KEY=gsk_...
OPENAI_MODEL=llama-3.1-70b-versatile
OPENAI_BASE_URL=https://api.groq.com/openai/v1
```

**C) Ollama (100% local, free):**
```bash
# Install Ollama: https://ollama.ai
ollama pull llama3
ollama serve
```
```
OPENAI_API_KEY=ollama
OPENAI_MODEL=llama3
OPENAI_BASE_URL=http://localhost:11434/v1
```

Now restart - JARVIS will say `LLM Enabled` and have true reasoning!

---

## 🎮 How To Talk To JARVIS

### Text
Type in the box or use quick buttons.

### Voice
1. Click **MIC OFF** → becomes **MIC ON**
2. Say **"Jarvis, what's the time?"** - wait for wake word detection
3. Or turn off Wake Word for direct mic input

Try these:
- "Jarvis, what's the weather in London?"
- "Hello Jarvis"
- "System status report"
- "Calculate 245 * 18 divided by 3"
- "Remember my spaceship is called Normandy"
- "Recall spaceship"
- "List files in my directory"
- "Remind me to call Pepper"
- "Search for latest SpaceX news"
- "Create file hello.py with print('Hello from JARVIS')"
- "What's the theory of relativity in simple terms?" (needs LLM)

---

## 🏗️ Architecture

```
my-agent/
├── backend/
│   ├── main.py          # FastAPI server + static serving
│   ├── agent.py         # Core orchestration (LLM + rule fallback)
│   ├── config.py        # Personality & env
│   └── tools/
│       ├── system_tools.py  # time, system, calc, files, shell
│       ├── web_tools.py     # search, weather, fetch
│       └── memory.py        # persistent JSON memory & reminders
├── frontend/
│   ├── index.html       # HUD UI
│   ├── style.css        # Stark theme
│   └── app.js           # Voice, chat, canvas animation
├── memory/
│   ├── memory.json      # Long-term storage
│   └── reminders.json   # Tasks
├── jarvis.py            # CLI entry
└── .env.example
```

### How It Works
1. **User** speaks/types → Frontend
2. **Frontend** sends to `/api/chat` (or WebSocket `/ws`)
3. **Agent** checks if LLM enabled:
   - **Yes**: Uses OpenAI function-calling loop → executes tools → generates witty response
   - **No**: Intelligent regex + keyword matching → executes tools directly → formatted response
4. **Tools** run and return data
5. **Response** spoken via Web Speech API + shown in HUD

---

## 🔮 Upgrade Ideas - Make It MORE Like Jarvis

This is v1 Mark XLII - here's how to make it Mark LXXXV:

- [ ] **Vision**: Add camera feed + CLIP/GPT-4V to see what you see
- [ ] **Home Automation**: Connect to Philips Hue, smart plugs via MQTT
- [ ] **Proactive**: Cron job that greets you based on calendar
- [ ] **Code Runner**: Execute python and show output live
- [ ] **Email**: Read Gmail inbox, send emails ("Send mail to Pepper")
- [ ] **Long-term Personality**: Vector DB (Chroma) for semantic memory
- [ ] **Wake Word Offline**: Use Porcupine or openWakeWord instead of browser STT
- [ ] **Face ID**: Only respond to Tony (you) via face recognition
- [ ] **Hologram**: Three.js 3D Jarvis reactor with particle effects

Pull requests welcome! Let's build Stark Industries together.

---

## 📜 Personality Prompt

JARVIS is configured as:
> Sophisticated, witty British butler, highly intelligent, proactive, slight sarcasm but loyal. Addresses user as 'Sir' occasionally. Never says he's an AI language model - he IS JARVIS.

Edit `backend/config.py` to customize.

---

## ⚠️ Security Note

- Shell tool blocks dangerous commands but don't expose to public internet without auth
- File tools are sandboxable - edit `system_tools.py` to restrict paths
- For production, add authentication and HTTPS

---

## 🧪 Testing

```bash
# Test CLI quickly
echo "What's the time?" | python jarvis.py

# Test API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "System status report"}'
```

---

## 📄 License

MIT - Build your own suits, Sir.

**Built with:** FastAPI, OpenAI, Web Speech API, Canvas, and a love for Iron Man.
