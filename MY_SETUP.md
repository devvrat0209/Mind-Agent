# 🤖 My JARVIS Setup - Hybrid Edition

This repo contains **TWO JARVIS implementations**:

## 1. Advanced JARVIS (Main - TypeScript/Bun) - The Beast Mode
Cloned from **[vierisid/jarvis](https://github.com/vierisid/jarvis)** (629⭐ stars, production-grade)

This is the **full Iron Man JARVIS experience**:
- **Always-on daemon** - runs 24/7, persistent
- **Desktop awareness** - sees your screen every 5-10s via Go sidecar
- **Multi-machine** - one daemon, unlimited sidecars (laptop, desktop, server)
- **Voice** - "Hey Jarvis" wake word + streaming TTS/STT
- **Multi-agent hierarchy** - 12 specialist roles (software-engineer, research-analyst, data-analyst, etc.)
- **Visual workflows** - 50+ nodes, n8n-style builder
- **Goal pursuit** - OKRs, drill sergeant accountability
- **Authority gating** - runtime enforcement + audit trail
- **Multi-LLM** - Anthropic, OpenAI, Gemini, Ollama, Groq, OpenRouter, OmniRoute
- **Pebble ambient UI** - cursor-following disc, native windows
- **Site builder** - 100 webapp templates

### Running Advanced JARVIS

```bash
# Bun is required (installed via npm install -g bun)
bun --version  # 1.3.14

# Install deps
bun install --ignore-scripts

# Doctor check
bun run bin/jarvis.ts doctor

# Start daemon (port 3142)
bun run bin/jarvis.ts start --port 3142 --no-open

# Check status
bun run bin/jarvis.ts status
# ● JARVIS is running (PID 2152)
# Dashboard: http://localhost:3142

# In sandbox preview, it's at:
# https://3142-{sandboxId}.e2b.app

# Stop
bun run bin/jarvis.ts stop
```

**Config:** `~/.jarvis/config.yaml`
```yaml
auth:
  insecure_open_access: true  # for sandbox preview
daemon:
  port: 3142
  host: 0.0.0.0
```

**Dashboard:** Open http://localhost:3142 - first-run walks you through LLM provider, voice, profile interview.

**Architecture:**
```
src/
├── daemon/          # Main daemon process
├── agents/          # Voice intent, delegation
├── llm/             # Multi-provider LLM with tier system
├── vault/           # Knowledge vault (entities, facts, relationships)
├── personality/     # Adaptive learning per channel
├── roles/           # 12 specialist roles YAML
├── observers/       # File watcher, clipboard, process monitor
├── comms/           # WebSocket server, voice, channels
├── workflows/       # Visual workflow engine
├── goals/           # OKR tracking
├── authority/       # Gating, approvals, audit
├── sites/           # Site builder + proxy
└── sidecar/         # Go sidecar for desktop control (Win32/X11/macOS)
```

---

## 2. Python JARVIS (Backup - python-edition-backup/) - Simple & Hackable

Our **original Python implementation** - lightweight, easy to hack, great for learning and quick tasks.

**Preserved in:** `python-edition-backup/`

### Features (Python Edition)
- **14 tools**: web_search, fetch_page, filesystem, shell, python_exec, memory, etc.
- **Multi-LLM**: OpenAI, Anthropic, Gemini, Ollama, OpenRouter (openai-compatible)
- **ReAct loop**: Think → Act → Observe → Repeat
- **CLI**: `python cli.py chat` with Rich UI
- **Web UI**: FastAPI + WebSocket
- **Memory**: JSONL long-term storage
- **Mock mode**: Works without API keys for testing

### Running Python JARVIS

```bash
cd python-edition-backup/
pip install -r requirements.txt --break-system-packages

# Create .env from example
cp ../config.example.yaml .env  # or create .env manually
# Edit .env:
# OPENAI_API_KEY=sk-...
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o-mini
# AGENT_NAME=JARVIS

python cli.py tools   # List 14 tools
python cli.py chat    # Interactive chat
python cli.py run "Build a website"  # Single task
python cli.py server  # Web UI at :8000
```

**Structure:**
```
python-edition-backup/
├── agent/
│   ├── core.py       # JARVISAgent with ReAct loop
│   ├── llm.py        # Multi-provider client
│   ├── config.py     # AGENT_NAME=JARVIS
│   └── tools/        # filesystem, shell, web, memory, code
├── cli.py            # Typer CLI
├── server.py         # FastAPI server
└── web/index.html    # Dark theme chat UI
```

---

## 🎯 Which to Use?

| Feature | Advanced (TS) | Python Edition |
|---------|--------------|----------------|
| **Always-on daemon** | ✅ Yes, 24/7 | ❌ No, on-demand |
| **Desktop eyes** | ✅ Go sidecar | ❌ No |
| **Voice wake-word** | ✅ "Hey Jarvis" | ❌ No (could add) |
| **Multi-agent** | ✅ 12 roles | ❌ Single agent |
| **Workflows** | ✅ Visual 50+ nodes | ❌ No |
| **Goals/OKRs** | ✅ Yes | ❌ No |
| **Easy to hack** | ❌ Complex TS | ✅ Simple Python |
| **Setup time** | 5-10 min | 1 min |
| **Learning** | Production | Educational |

**Recommendation:**
- Want the **real JARVIS** from movies? → **Advanced**
- Want to **learn/build custom tools quickly**? → **Python**
- Want **both**? → Run Advanced on 3142, Python on 8000 (hybrid!)

---

## 🚀 Hybrid Mode - Running Both

We have setup that lets you run **both JARVISes simultaneously**:

```bash
# Terminal 1: Advanced JARVIS (3142)
bun run bin/jarvis.ts start --port 3142

# Terminal 2: Python JARVIS (8000)
cd python-edition-backup/
python cli.py server --port 8000
# Or: python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Then you have:
- Advanced dashboard: https://3142-{id}.e2b.app
- Python chat: https://8000-{id}.e2b.app

**JARVIS²** - Two JARVISes working together!

---

## 📦 Current Status

✅ Advanced JARVIS daemon running on port 3142 (0.0.0.0)
✅ Bun 1.3.14 installed
✅ Dependencies installed (bun install --ignore-scripts)
✅ Config set to insecure_open_access for preview
✅ Python backup preserved in python-edition-backup/

**Next steps:**
1. Open dashboard at https://3142-{sandboxId}.e2b.app
2. Setup LLM provider (OpenAI key, or Ollama, etc.)
3. Setup voice (optional)
4. Enroll sidecar if you want desktop eyes
5. Start building!

**To update advanced JARVIS:**
```bash
git remote add upstream https://github.com/vierisid/jarvis.git
git fetch upstream
git merge upstream/main  # careful, resolve conflicts
```

**To work on Python edition:**
```bash
cd python-edition-backup/
python cli.py chat
```

---

## 🙏 Credits

- **Advanced JARVIS**: [vierisid/jarvis](https://github.com/vierisid/jarvis) - MIT? RSAL licensed
- **Python JARVIS**: Built from scratch for devvrat0209/my-agent

Both are **JARVIS** - Just A Rather Very Intelligent System.

*At your service, Sir.* 🤖

---

## 🔧 Quick Commands

```bash
# Advanced
bun run bin/jarvis.ts start -d          # background
bun run bin/jarvis.ts logs -f           # follow logs
bun run bin/jarvis.ts doctor            # check system
bun run bin/jarvis.ts enroll "my-laptop" # add device
bun run bin/jarvis.ts status            # status

# Python
cd python-edition-backup/
python cli.py chat
python cli.py run "Create todo app"
python cli.py memory list
```

Enjoy your JARVIS, Sir! 🚀
