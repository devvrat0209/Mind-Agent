# JARVIS — Self-Editing AI Agent

A CLI + Telegram AI agent that can read, understand, and **edit its own source code**, with **full device access**. Built for VPS.

## Deploy on VPS (one command)

```bash
curl -fsSL https://raw.githubusercontent.com/devvrat0209/my-agent/main/jarvis-agent/deploy-vps.sh | sudo bash
```

Then:
```bash
nano /opt/jarvis/.env        # set your tokens
systemctl enable --now jarvis  # start
journalctl -u jarvis -f      # watch logs
```

## Configure (`/opt/jarvis/.env`)

```env
# LLM
JARVIS_LLM=openai/gpt-4o
OPENAI_API_KEY=sk-...

# Telegram (get token from @BotFather)
JARVIS_TELEGRAM_TOKEN=123456:ABC-DEF...

# Your Telegram user ID (get from @userinfobot)
JARVIS_TELEGRAM_USERS=12345678
```

## Talk to JARVIS

Open Telegram, message your bot. That's it. Full server control from your phone.

### Commands
| Command | What |
|---------|------|
| `/start` | Initialize |
| `/status` | Server status (CPU, RAM, disk, uptime) |
| `/shell <cmd>` | Run any shell command |
| `/inspect` | Self-inspect its own source code |
| `/diff` | See code changes |
| `/rollback` | Undo last edit |
| `/model` | Change LLM model |
| `/log` | View recent logs |
| `/restart` | Restart service |
| `/reset` | Reset conversation |

### Send it things
- **Text** → AI response with full tool access
- **Photos** → JARVIS analyzes
- **Files** → JARVIS saves & processes
- **Voice** → JARVIS handles audio

## What It Can Do (23 tools)

### Code & Self-Editing
| Tool | Description |
|------|-------------|
| `read_file` | Read any file (including its own source) |
| `write_file` | Create or overwrite any file |
| `edit_file` | Search & replace (surgical edits) |
| `list_files` | List directory contents |
| `run_code` | Execute Python code |
| `shell` | Run shell commands |
| `self_inspect` | List its own source files |
| `git_diff` / `git_commit` | Version control |
| `rollback` | Undo last edit |
| `search_code` | Search across files |

### Device Access
| Tool | Description |
|------|-------------|
| `system_info` | OS, CPU, RAM, uptime, battery |
| `list_processes` | List/kill processes |
| `network_info` | Interfaces, IPs, connections |
| `disk_usage` | All mounted partitions |
| `screenshot` | Capture screen |
| `clipboard_read/write` | Clipboard |
| `open_app` | Open apps/URLs |
| `download_file` | Download from URL |
| `notify` | Notifications |
| `media_capture` | Webcam/mic |
| `environment_vars` | Env vars |

## Self-Editing

JARVIS knows its own codebase. Tell it:
- *"Add a weather tool to yourself"*
- *"Fix the error handling in tools.py"*
- *"Add unit tests"*
- *"Refactor memory to use SQLite"*

It reads its own files, plans changes, applies them, and shows the diff.

## Run Locally (CLI)

```bash
pip install -e .
jarvis
```

## Safety

- Telegram access restricted by user ID
- Every self-edit shows a diff
- Rollback undoes last change
- Git commits after each edit
- Runs as its own systemd user
