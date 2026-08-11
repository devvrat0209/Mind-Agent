# JARVIS — Self-Editing AI Agent

A CLI + Telegram AI agent that can read, understand, and **edit its own source code**, with **full device access**.

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/devvrat0209/my-agent/main/jarvis-agent/install.sh | bash
```

## Configure

```bash
# LLM
export JARVIS_LLM=openai/gpt-4o
export OPENAI_API_KEY=sk-...

# Telegram (get token from @BotFather)
export JARVIS_TELEGRAM_TOKEN=123456:ABC-DEF...

# Restrict to your Telegram account (get ID from @userinfobot)
export JARVIS_TELEGRAM_USERS=12345678
```

## Run

```bash
# CLI mode
jarvis

# Telegram bot mode
jarvis-telegram
```

## What It Can Do

### Code & Self-Editing
| Tool | Description |
|------|-------------|
| `read_file` | Read any file (including its own source) |
| `write_file` | Create or overwrite any file |
| `edit_file` | Search & replace in a file (surgical edits) |
| `list_files` | List directory contents |
| `run_code` | Execute Python code and see output |
| `shell` | Run shell commands |
| `self_inspect` | List its own source files + sizes |
| `git_diff` | See what it changed |
| `git_commit` | Commit its changes |
| `rollback` | Undo the last edit |
| `search_code` | Search across files |

### Device Access (Full Control)
| Tool | Description |
|------|-------------|
| `system_info` | OS, CPU, RAM, uptime, battery, hostname |
| `list_processes` | List/kill running processes |
| `network_info` | Interfaces, IPs, connections, bandwidth |
| `disk_usage` | All mounted partitions |
| `screenshot` | Capture screen |
| `clipboard_read/write` | Read/write clipboard |
| `open_app` | Open apps, files, URLs |
| `download_file` | Download from URL |
| `notify` | Desktop notifications |
| `media_capture` | Webcam photo, mic audio |
| `environment_vars` | Read/set environment variables |

## Self-Editing

The agent knows its own codebase. You can say:

- *"Add a weather tool to yourself"*
- *"Your error handling in tools.py is weak, fix it"*
- *"Add unit tests for the LLM module"*
- *"Refactor your memory system to use SQLite"*

It reads its own files, plans the changes, shows a diff, and applies them.

## Telegram

Talk to JARVIS from your phone. Full device control from anywhere:

- Send text → JARVIS responds with AI
- Send photos → JARVIS analyzes them
- Send files → JARVIS saves and processes them
- Send voice → JARVIS handles audio
- `/shell <cmd>` → Run shell commands remotely
- `/status` → Device status
- `/inspect` → Self-inspect source code
- `/diff` → See changes
- `/rollback` → Undo last edit

## Safety

- Every self-edit shows a **diff** before applying
- **Rollback** undoes the last change
- **Git commits** after each approved edit
- Telegram access can be **restricted to specific user IDs**
- The agent **cannot** edit files outside its directory unless you allow it
