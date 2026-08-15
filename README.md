# my-agent

A self-editing AI agent — **JARVIS** — that can modify its own source code, run shell commands, and control a device, all from Telegram.

The repo contains the full `jarvis-agent` Python package. Talk to your bot, and it reads its own files, plans changes, applies them, and shows you the diff.

## What's inside

```
my-agent/
├── jarvis-agent/           # The Python package
│   ├── jarvis/
│   │   ├── agent.py            # Core agent loop (think → act → observe)
│   │   ├── cli.py              # CLI (setup / doctor / install / api / bot / nim)
│   │   ├── wizard.py           # Interactive setup wizard
│   │   ├── platform_detect.py  # OS / arch / GPU / CUDA detection
│   │   ├── deps.py             # Dependency check + device-aware auto-install
│   │   ├── nim.py              # NVIDIA NIM client (hosted + self-hosted)
│   │   ├── api.py              # FastAPI REST API
│   │   ├── config.py           # Config / .env loading
│   │   ├── llm.py              # LLM calls via LiteLLM
│   │   ├── memory.py           # Conversation history
│   │   ├── heartbeat.py        # Heartbeat daemon (scheduled background tasks)
│   │   ├── autonomy.py         # Autonomous work cycles (mission + journal)
│   │   ├── tools.py            # 23 tools (code + device access)
│   │   ├── device.py           # Device control helpers
│   │   └── telegram_bot.py     # Telegram bot handler
│   ├── pyproject.toml
│   ├── install.sh          # One-liner installer
│   └── deploy-vps.sh       # VPS deployment script
└── LICENSE                 # MIT
```

## Quick start

```bash
pip install jarvis-agent
jarvis
```

First run launches a setup wizard that detects your hardware, installs any
missing dependencies, and asks for your NVIDIA NIM / Telegram credentials.
Every run after that starts the Telegram bot.

## Commands

| Command | What it does |
|---------|--------------|
| `jarvis` | Setup wizard on first run, then starts the bot |
| `jarvis setup [section]` | Re-run the wizard (`device`, `deps`, `llm`, `nim`, `telegram`, `api`) |
| `jarvis doctor` | Check device, dependencies and configuration |
| `jarvis install [groups]` | Install missing dependencies for this device |
| `jarvis device [--json]` | Show detected OS / CPU / GPU / CUDA |
| `jarvis api` | Start the REST API server |
| `jarvis bot` | Start the Telegram bot |
| `jarvis nim status\|models\|test` | NVIDIA NIM helpers |
| `jarvis heartbeat [run <task>]` | Heartbeat daemon status, or fire a task now |

## NVIDIA NIM

JARVIS talks to NVIDIA NIM in two shapes:

- **Hosted** — `https://integrate.api.nvidia.com/v1`, free key from
  [build.nvidia.com](https://build.nvidia.com). No GPU needed.
- **Self-hosted** — a NIM container on your own NVIDIA GPU, usually
  `http://localhost:8000/v1`. The wizard checks your GPU, VRAM and Docker
  before offering this and prints the `docker run` line if it's not up yet.

```bash
jarvis setup nim     # configure interactively
jarvis nim status    # endpoint + key + latency
jarvis nim models    # what the endpoint actually serves
jarvis nim test      # end-to-end completion smoke test
```

The wizard validates the key against `/models` before saving, then offers a
test completion so you know it works before you leave setup.

## Dependency & device handling

`jarvis doctor` and `jarvis install` check every requirement and install what's
missing using pip flags picked for the machine you're on:

- **PEP 668** system Python (Debian/Ubuntu/Termux) → `--break-system-packages`, plus `--user` when not root
- **venv / conda** → installs straight in, no extra flags
- **Docker / CI** → `--no-cache-dir`
- **NVIDIA GPU** → torch-style wheels from the matching CUDA index (`cu124`, `cu121`, `cu118`)
- **AMD** → ROCm index · **Apple Silicon** → default wheels (MPS) · otherwise the CPU index

Detection covers Linux (with distro + package manager), macOS, Windows,
Android/Termux, WSL and Docker, and reports GPU vendor, name, VRAM, driver and
CUDA version via `nvidia-smi` / `rocm-smi`.

## REST API

```bash
jarvis api --host 0.0.0.0 --port 8088
```

Interactive docs at `/docs`. Set `JARVIS_API_KEY` to require
`Authorization: Bearer <key>` on every route except `/` and `/health`.

| Method | Route | Purpose |
|--------|-------|---------|
| `GET` | `/health` | Liveness + dependency/integration status |
| `GET` | `/device` | Full hardware detection |
| `GET` | `/deps` | Dependency report |
| `POST` | `/deps/install` | Install missing dependencies |
| `GET` | `/nim/status` | NIM connectivity + latency |
| `GET` | `/nim/models` | Models on the endpoint |
| `POST` | `/nim/chat` | Direct NIM completion |
| `POST` | `/nim/test` | NIM smoke test |
| `GET` | `/telegram/status` | Bot token validity |
| `POST` | `/telegram/send` | Send a message via the bot |
| `POST` | `/chat` | Talk to the agent |
| `POST` | `/reset` | Clear agent memory |
| `GET` | `/config` | Non-secret config view |
| `GET` | `/heartbeat` | Heartbeat daemon status + task schedule |
| `POST` | `/heartbeat/start` | Start the heartbeat daemon |
| `POST` | `/heartbeat/stop` | Stop the heartbeat daemon |
| `POST` | `/heartbeat/run/{task}` | Fire a heartbeat task immediately |
| `GET` | `/mission` | Current autonomous-work mission + journal tail |
| `POST` | `/mission` | Set the standing mission |
| `DELETE` | `/mission` | Clear the mission (pause autonomous work) |
| `POST` | `/work` | Run an autonomous work cycle now |

### One-liner install

```bash
curl -fsSL https://raw.githubusercontent.com/devvrat0209/my-agent/main/jarvis-agent/install.sh | bash
jarvis
```

### VPS deploy

```bash
curl -fsSL https://raw.githubusercontent.com/devvrat0209/my-agent/main/jarvis-agent/deploy-vps.sh | sudo bash
jarvis
```

Or run it as a systemd service:

```bash
systemctl enable --now jarvis
journalctl -u jarvis -f
```

## Requirements

- Python 3.10+
- An LLM provider: **NVIDIA NIM**, **OpenAI**, **Anthropic**, **Ollama** (local), **Groq**, or any LiteLLM-supported endpoint
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

Everything else is installed for you on first run.

## Configuration

Configuration lives in a `.env` file (see [`.env.example`](jarvis-agent/.env.example)) or the environment:

| Variable | Description |
|----------|-------------|
| `JARVIS_LLM` | LLM model, e.g. `nvidia_nim/meta/llama-3.3-70b-instruct` |
| `NVIDIA_NIM_API_KEY` | NVIDIA NIM key (`nvapi-...`) |
| `NVIDIA_NIM_API_BASE` | NIM endpoint (default `https://integrate.api.nvidia.com/v1`) |
| `JARVIS_NIM_MODE` | `hosted` or `local` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Provider API key |
| `JARVIS_TELEGRAM_TOKEN` | Telegram bot token |
| `JARVIS_TELEGRAM_USERS` | Comma-separated allowed user IDs (empty = anyone) |
| `JARVIS_API_ENABLED` | `1` to run the REST API alongside the bot |
| `JARVIS_API_HOST` / `JARVIS_API_PORT` | API bind address (default `127.0.0.1:8088`) |
| `JARVIS_API_KEY` | Bearer token for the API (blank = no auth) |
| `JARVIS_AUTO_APPROVE` | Set to `1` to auto-approve self-edits (**dangerous**) |
| `JARVIS_HEARTBEAT_ENABLED` | `0` to disable the heartbeat daemon (default `1`) |
| `JARVIS_HEARTBEAT_TICK` | Scheduler resolution in seconds (default `15`) |
| `JARVIS_HB_<TASK>` | Per-task interval override in seconds, `0` disables (e.g. `JARVIS_HB_HEALTH_CHECK=600`) |
| `JARVIS_HB_AGENT_WORK` | Seconds between autonomous work cycles (default `3600`, `0` disables) |
| `JARVIS_WORK_MAX_CALLS` | Max tool calls per work cycle (default `15`) |
| `JARVIS_WORK_REPORT` | `0` to journal silently instead of Telegram-reporting each cycle |

## Telegram commands

| Command | What it does |
|---------|--------------|
| `/start` | Initialize |
| `/status` | Server status |
| `/shell <cmd>` | Run a shell command |
| `/inspect` | Self-inspect the source code |
| `/diff` | See code changes |
| `/rollback` | Undo the last edit |
| `/model` | Change LLM |
| `/device` | Hardware & GPU info |
| `/nim` | NVIDIA NIM status, or `/nim <model>` to switch |
| `/deps` | Dependency health, `/deps install` to fix |
| `/log` | View logs |
| `/restart` | Restart the service |
| `/reset` | Reset conversation |
| `/heartbeat` | Heartbeat daemon status, `/heartbeat run <task>` to fire one now |
| `/mission` | Show the standing mission; `/mission <text>` sets it, `/mission clear` stops it |
| `/work` | Run an autonomous work cycle right now |
| `/journal` | Recent entries from the autonomous work journal |

Send text, photos, files, or voice — JARVIS handles everything.

## Features

- **Self-editing** — modify its own source code, then `git_commit` and `rollback` as needed
- **Code tools** — `read_file`, `write_file`, `edit_file`, `list_files`, `run_code`, `shell`, `search_code`
- **Device access** — system info, processes, network, disk, screenshot, clipboard, open apps, downloads, notifications
- **Heartbeat daemon** — cron-style background tasks (status pings, health checks, LLM/Telegram connectivity, update checks, log rotation) with failure backoff and Telegram alerts, running even while the agent is idle
- **Autonomous work** — give JARVIS a standing mission (`/mission`) and the heartbeat wakes the agent every hour to make real progress on it with its tools, journaling each cycle and reporting back on Telegram
- **Memory** — keeps conversation history across turns
- **Multi-provider** — NVIDIA NIM, OpenAI, Anthropic, Ollama, Groq, or any LiteLLM model
- **Device-aware setup** — detects OS, arch, GPU and CUDA, then installs deps to match
- **REST API** — FastAPI server for chat, health, device and NIM control

## License

[MIT](LICENSE) © 2026 devvrat0209
