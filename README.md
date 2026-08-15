# my-agent

A self-editing AI agent — **JARVIS** — that can modify its own source code, run shell commands, and control a device, all from Telegram.

The repo contains the full `jarvis-agent` Python package. Talk to your bot, and it reads its own files, plans changes, applies them, and shows you the diff.

## What's inside

```
my-agent/
├── jarvis-agent/           # The Python package
│   ├── jarvis/
│   │   ├── agent.py        # Core agent loop (think → act → observe)
│   │   ├── cli.py          # CLI + first-run setup wizard
│   │   ├── config.py       # Config / .env loading
│   │   ├── llm.py          # LLM calls via LiteLLM
│   │   ├── memory.py       # Conversation history
│   │   ├── tools.py        # 23 tools (code + device access)
│   │   ├── device.py       # Device control helpers
│   │   └── telegram_bot.py # Telegram bot handler
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

First run launches a setup wizard that asks for your LLM and Telegram tokens and saves them. Every run after that starts the Telegram bot.

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
- An LLM provider: **OpenAI**, **Anthropic**, **Ollama** (local), **Groq**, or any LiteLLM-supported endpoint
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Configuration

Configuration lives in a `.env` file (see [`.env.example`](jarvis-agent/.env.example)) or the environment:

| Variable | Description |
|----------|-------------|
| `JARVIS_LLM` | LLM model, e.g. `openai/gpt-4o` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | Provider API key |
| `JARVIS_TELEGRAM_TOKEN` | Telegram bot token |
| `JARVIS_TELEGRAM_USERS` | Comma-separated allowed user IDs (empty = anyone) |
| `JARVIS_AUTO_APPROVE` | Set to `1` to auto-approve self-edits (**dangerous**) |

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
| `/log` | View logs |
| `/restart` | Restart the service |
| `/reset` | Reset conversation |

Send text, photos, files, or voice — JARVIS handles everything.

## Features

- **Self-editing** — modify its own source code, then `git_commit` and `rollback` as needed
- **Code tools** — `read_file`, `write_file`, `edit_file`, `list_files`, `run_code`, `shell`, `search_code`
- **Device access** — system info, processes, network, disk, screenshot, clipboard, open apps, downloads, notifications
- **Memory** — keeps conversation history across turns
- **Multi-provider** — works with any LiteLLM-supported model

## License

[MIT](LICENSE) © 2026 devvrat0209
