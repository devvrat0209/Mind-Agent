# JARVIS — Self-Editing AI Agent

Self-editing AI agent with full device access, controlled via Telegram. Built for VPS.

## Install & Run (that's it)

```bash
pip install jarvis-agent
jarvis
```

First run → setup wizard asks for your tokens and saves them.
Every run after → starts the Telegram bot.

## One-Liner

```bash
curl -fsSL https://raw.githubusercontent.com/devvrat0209/my-agent/main/jarvis-agent/install.sh | bash
jarvis
```

## VPS Deploy

```bash
curl -fsSL https://raw.githubusercontent.com/devvrat0209/my-agent/main/jarvis-agent/deploy-vps.sh | sudo bash
jarvis
```

Or as a systemd service:
```bash
systemctl enable --now jarvis
journalctl -u jarvis -f
```

## What Happens on First Run

```
$ jarvis

   ██╗ █████╗ ██████╗ █████╗ ██████╗ ██████╗ ██████╗
   ...

First run — let's set you up.

────────────────── LLM Provider ──────────────────

Pick your LLM provider:
  [1] OpenAI (GPT-4o)
  [2] Anthropic (Claude)
  [3] Ollama (local)
  [4] Groq
  [5] Other

  Choice [1]: 1
  OpenAI API key: sk-...

────────────────── Telegram Bot ──────────────────

  You need a Telegram bot token.
  1. Open Telegram, search @BotFather
  2. Send /newbot
  3. Copy the token

  Bot token: 123456:ABC-DEF...

────────────────── Access Control ────────────────

  Restrict access? [Y/n]: y
  Your Telegram user ID: 12345678

────────────────── Ready ─────────────────────────

  ✅ Configuration saved!

  Start JARVIS now? [Y/n]:
```

Then talk to your bot on Telegram. That's it.

## Commands (on Telegram)

| Command | What |
|---------|------|
| `/start` | Initialize |
| `/status` | Server status |
| `/shell <cmd>` | Run any shell command |
| `/inspect` | Self-inspect source code |
| `/diff` | See code changes |
| `/rollback` | Undo last edit |
| `/model` | Change LLM |
| `/log` | View logs |
| `/restart` | Restart service |
| `/reset` | Reset conversation |

Send text, photos, files, voice — JARVIS handles everything.

## 23 Tools

**Code & Self-Editing:** read_file, write_file, edit_file, list_files, run_code, shell, self_inspect, git_diff, git_commit, rollback, search_code

**Device Access:** system_info, list_processes, network_info, disk_usage, screenshot, clipboard_read/write, open_app, download_file, notify, media_capture, environment_vars

## Self-Editing

JARVIS can modify its own source code. Tell it:
- *"Add a weather tool to yourself"*
- *"Fix the error handling in tools.py"*
- *"Add unit tests"*

It reads its own files, plans changes, applies them, shows the diff.
