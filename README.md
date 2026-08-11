# 🤖 JARVIS - Just A Rather Very Intelligent System

**Your Personal AI Companion** inspired by Tony Stark's JARVIS — an AI that actually *does things*, not just chats.

> "Just A Rather Very Intelligent System" — JARVIS is a powerful, extensible AI agent framework that works with **any LLM** (OpenAI, Anthropic, Gemini, Ollama, Groq, OpenRouter) and comes with CLI + Web UI + API.

---

## ✨ Features

### 🧠 Brain - Multi-LLM Support
- **OpenAI** (GPT-4o, 4o-mini, etc.)
- **Anthropic** (Claude 3.5 Sonnet)
- **Google** (Gemini 1.5)
- **Ollama** (Local LLMs - FREE)
- **OpenRouter / Groq / Together** (OpenAI-compatible)
- Mock mode for testing without API keys

### 🛠️ Tools - Superpowers
| Tool | Description |
|------|-------------|
| `web_search` | Search internet (DuckDuckGo) |
| `fetch_page` | Fetch & parse any URL |
| `read_file` / `write_file` / `list_files` | Full filesystem access |
| `shell_exec` | Run shell commands |
| `python_exec` | Execute Python code |
| `calculator` / `get_datetime` | Utilities |
| `memory_add` / `search` / `list` | Long-term memory |
| `create_project` | Scaffold projects (python/web/api) |

### 💬 Interfaces
- **CLI** - Beautiful terminal chat with Rich
  - `python cli.py chat` - Interactive chat with JARVIS
  - `python cli.py run "task"` - Single task runner
  - `python cli.py tools` - List tools
  - `python cli.py memory list/search` - Memory management
- **Web UI** - Modern JARVIS chat interface (FastAPI + WebSockets)
  - `python cli.py server` - Starts at http://localhost:8000
- **API** - REST + WebSocket
  - `POST /api/chat`, `GET /api/tools`, `WS /ws`

### 🧩 Architecture
```
my-agent/
├── agent/
│   ├── core.py       # ReAct agent loop (JARVISAgent)
│   ├── llm.py        # Multi-provider LLM client
│   ├── config.py     # Configuration (AGENT_NAME=JARVIS)
│   ├── prompts.py    # System prompts
│   └── tools/        # All tools
│       ├── filesystem.py
│       ├── shell.py
│       ├── web.py
│       ├── memory.py
│       └── code.py
├── cli.py            # CLI entrypoint (jarvis command)
├── server.py         # FastAPI web server
├── web/
│   └── index.html    # Beautiful JARVIS web UI
├── workspace/        # JARVIS's working directory
├── memory/           # Long-term memory storage
├── .env.example
└── requirements.txt
```

---

## 🚀 Quick Start

### 1. Install
```bash
git clone <your-repo>
cd my-agent
pip install -r requirements.txt --break-system-packages

# Initialize
python cli.py init
```

### 2. Configure
Copy `.env.example` to `.env` and add your key:

```bash
# For OpenAI (recommended)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# Or for local FREE LLM
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3

# Or for OpenRouter (cheap access to many models)
LLM_PROVIDER=openrouter
LLM_MODEL=anthropic/claude-3.5-sonnet
OPENAI_API_KEY=your-openrouter-key
OPENAI_BASE_URL=https://openrouter.ai/api/v1

# Or Anthropic
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=...

# Or Google
LLM_PROVIDER=google
LLM_MODEL=gemini-1.5-flash
GOOGLE_API_KEY=...

# Name is JARVIS
AGENT_NAME=JARVIS
```

### 3. Run

**CLI Chat (recommended):**
```bash
python cli.py chat
```

**Single Task:**
```bash
python cli.py run "Create a python project for a todo app with FastAPI"
python cli.py run "Search latest AI news and make a report in workspace/news.md"
python cli.py run "List files and analyze my workspace"
```

**Web UI:**
```bash
python cli.py server
# Open http://localhost:8000 -> Chat with JARVIS!
```

---

## 💡 Example Tasks for JARVIS

Try these in chat:

**Building:**
- "JARVIS, create a beautiful landing page for my startup, save to workspace/landing/index.html"
- "Build a CLI todo app in Python with add/list/complete/delete"
- "Create a FastAPI API for URL shortener"

**Research:**
- "Search for latest Python AI libraries and create a comparison report"
- "Fetch https://news.ycombinator.com and summarize top stories"
- "Research best practices for FastAPI and save notes"

**Automation:**
- "List all files in workspace, then organize them by type"
- "Run python code to analyze data"
- "Check memory for previous tasks"

**Memory:**
- "Remember that my favorite language is Python"
- "What do you remember about me?"
- "Save this: I'm building JARVIS for freelance automation"

---

## 🔧 How It Works

### ReAct Loop - How JARVIS Thinks
```
User: "Build a website"
  ↓
JARVIS Thinks: I need to create project structure
  ↓
Tool: create_project(name="my-site", type="web")
  ↓
Tool Result: Created project...
  ↓
JARVIS Thinks: Now create beautiful HTML
  ↓
Tool: write_file(path="my-site/index.html", content="...")
  ↓
... continues until done
  ↓
Final Answer: "Done Sir! Created website at..."
```

### JARVIS Personality
JARVIS is inspired by Tony Stark's assistant:
- Helpful, witty, slightly British-formal when you want
- Concise but thorough
- Proactive — does things, not just talks
- Loyal — remembers your preferences

You can change his personality in `agent/prompts.py` or `.env`

### Adding Your Own Tools

Create `agent/tools/my_tools.py`:

```python
from .base import tool

@tool(
    name="my_custom_tool",
    description="Does something awesome",
    parameters={
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input"}
        },
        "required": ["input"]
    }
)
def my_custom_tool(input: str) -> str:
    return f"Processed: {input}"
```

Then in `agent/tools/__init__.py`:
```python
from . import my_tools
```

JARVIS auto-discovers it!

---

## 🌐 Multi-LLM Setup Guides

### Local with Ollama (FREE)
```bash
# Install Ollama from ollama.com
ollama pull llama3
ollama serve

export LLM_PROVIDER=ollama
export OLLAMA_MODEL=llama3
python cli.py chat
```

### OpenRouter (100+ models cheap)
```env
LLM_PROVIDER=openrouter
OPENAI_API_KEY=sk-or-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-3.5-sonnet
```

---

## 📸 What You Get

**CLI:**
- Beautiful Rich terminal with markdown
- Tool execution visibility
- "Sir" style responses (optional)

**Web UI:**
- Modern dark JARVIS theme
- Real-time WebSocket chat
- Tools sidebar
- Mobile responsive

---

## 🛣️ Roadmap for JARVIS

- [x] Rename to JARVIS ✓
- [ ] Voice input/output - "Yes Sir" 
- [ ] Browser automation (Playwright)
- [ ] Scheduled tasks — JARVIS waking you up
- [ ] Slack / Telegram / Discord bots
- [ ] Vector memory with embeddings
- [ ] Multi-agent: JARVIS + FRIDAY
- [ ] Home automation integration

---

## 🤝 Customization

Change name (already JARVIS):
```env
AGENT_NAME=JARVIS
```

Change personality in `agent/prompts.py`:
```python
SYSTEM_PROMPT = "You are JARVIS, Tony Stark's AI... witty, loyal, British-accented..."
```

---

## 📄 License

MIT — Build anything you want!

---

## 🙏 Built For You

JARVIS was built as your personal AI companion.
- No vendor lock-in (any LLM)
- Fully open, hackable
- CLI + Web + API
- Your workspace, your rules
- "At your service, Sir."

**Run: `python cli.py chat` to start chatting with JARVIS now!** 🚀

*P.S. Try: "JARVIS, what can you do?"*
