# 🤖 AURA - Autonomous Universal Reasoning Agent

**Your All-Rounder AI Agent** that actually *does things* — not just chat.

AURA is a powerful, extensible AI agent framework that works with **any LLM** (OpenAI, Anthropic, Gemini, Ollama, Groq, OpenRouter) and comes with CLI + Web UI + API.

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
  - `python cli.py chat` - Interactive chat
  - `python cli.py run "task"` - Single task runner
  - `python cli.py tools` - List tools
  - `python cli.py memory list/search` - Memory management
- **Web UI** - Modern chat interface (FastAPI + WebSockets)
  - `python cli.py server` - Starts at http://localhost:8000
- **API** - REST + WebSocket
  - `POST /api/chat`, `GET /api/tools`, `WS /ws`

### 🧩 Architecture
```
my-agent/
├── agent/
│   ├── core.py       # ReAct agent loop
│   ├── llm.py        # Multi-provider LLM client
│   ├── config.py     # Configuration
│   ├── prompts.py    # System prompts
│   └── tools/        # All tools
│       ├── filesystem.py
│       ├── shell.py
│       ├── web.py
│       ├── memory.py
│       └── code.py
├── cli.py            # CLI entrypoint (Typer + Rich)
├── server.py         # FastAPI web server
├── web/
│   └── index.html    # Beautiful web UI
├── workspace/        # Agent's working directory
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
pip install -r requirements.txt

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
```

### 3. Run

**CLI Chat (recommended for dev):**
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
# Open http://localhost:8000
```

---

## 💡 Example Tasks for AURA

Try these in chat:

**Building:**
- "Create a beautiful landing page for my startup, save to workspace/landing/index.html"
- "Build a CLI todo app in Python with add/list/complete/delete features"
- "Create a FastAPI API for URL shortener with in-memory storage"

**Research:**
- "Search for latest Python AI libraries and create a comparison report in workspace/report.md"
- "Fetch https://news.ycombinator.com and summarize top stories"
- "Research best practices for FastAPI and save notes"

**Automation:**
- "List all files in workspace, then organize them by type"
- "Run python code to analyze CSV file if exists, else create sample data project"
- "Check memory for previous tasks and continue where we left off"

**Memory:**
- "Remember that my favorite language is Python and I prefer FastAPI"
- "What do you remember about my preferences?"
- "Save this: I'm building an AI agent for freelance automation"

---

## 🔧 How It Works

### ReAct Loop
```
User: "Build a website"
  ↓
AURA Thinks: I need to create project structure
  ↓
Tool: create_project(name="my-site", type="web")
  ↓
Tool Result: Created project...
  ↓
AURA Thinks: Now create beautiful HTML
  ↓
Tool: write_file(path="my-site/index.html", content="...")
  ↓
... continues until done
  ↓
Final Answer: "Done! Created website at..."
```

### Adding Your Own Tools

Create a new file `agent/tools/my_tools.py`:

```python
from .base import tool

@tool(
    name="my_custom_tool",
    description="Does something awesome",
    parameters={
        "type": "object",
        "properties": {
            "input": {"type": "string", "description": "Input text"}
        },
        "required": ["input"]
    }
)
def my_custom_tool(input: str) -> str:
    # Your logic here
    return f"Processed: {input}"
```

Then import it in `agent/tools/__init__.py`:
```python
from . import my_tools
```

AURA will auto-discover it!

---

## 🌐 Multi-LLM Setup Guides

### Local with Ollama (FREE)
```bash
# Install Ollama from ollama.com
ollama pull llama3
ollama serve

# In another terminal, set env:
export LLM_PROVIDER=ollama
export OLLAMA_MODEL=llama3
python cli.py chat
```

### OpenRouter (Access to 100+ models cheap)
```bash
# Get key from openrouter.ai
LLM_PROVIDER=openrouter
OPENAI_API_KEY=sk-or-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-3.5-sonnet  # or google/gemini-flash-1.5, etc.
```

---

## 📸 Screenshots

**CLI:**
- Beautiful Rich terminal UI with markdown rendering
- Streaming responses
- Tool execution visibility

**Web UI:**
- Modern dark theme
- Real-time WebSocket chat
- Tools sidebar
- Mobile responsive

---

## 🛣️ Roadmap

- [ ] Voice input/output
- [ ] Browser automation (Playwright)
- [ ] Scheduled tasks / Cron
- [ ] Slack / Telegram / Discord bots
- [ ] Vector memory with embeddings
- [ ] Multi-agent collaboration
- [ ] Plugin marketplace

---

## 🤝 Customization

AURA is named **AURA** but you can change it:

In `.env`:
```
AGENT_NAME=YourAgentName
```

Modify `agent/prompts.py` to change personality:
```python
SYSTEM_PROMPT = "You are Friday, a super helpful assistant..."
```

Add constraints, tone, etc.

---

## 📄 License

MIT — Build anything you want!

---

## 🙏 Built For You

AURA was built as your personal AI agent framework.
- No vendor lock-in (any LLM)
- Fully open, hackable
- CLI + Web + API
- Extensible tools
- Your workspace, your rules

**Your idea for customization?** Tell me and I'll tailor it!

Examples:
- "Make it a freelance helper that finds clients"
- "Make it monitor Twitter and summarize"
- "Make it auto-build websites from prompts"
- "Make it a personal assistant that manages my calendar"

Just say the word, and I'll customize AURA for that!

---

**Run: `python cli.py chat` to start chatting with AURA now!** 🚀
