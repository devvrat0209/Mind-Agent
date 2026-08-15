# JARVIS — Self-Editing AI Agent

Self-editing AI agent with full device access, controlled via Telegram.
NVIDIA NIM integration, a device-aware setup wizard and a REST API. Built for VPS.

## Install & Run (that's it)

```bash
pip install jarvis-agent
jarvis
```

First run → wizard detects your hardware, installs missing dependencies,
and asks for your NVIDIA NIM + Telegram credentials.
Every run after → starts the Telegram bot.

## CLI

| Command | What |
|---------|------|
| `jarvis` | Wizard on first run, then the bot |
| `jarvis setup [section]` | Re-run the wizard (`device`/`deps`/`llm`/`nim`/`telegram`/`api`) |
| `jarvis doctor` | Check device, deps and config |
| `jarvis install [groups]` | Install missing deps for this device |
| `jarvis device [--json]` | Detected OS / CPU / GPU / CUDA |
| `jarvis api` | Start the REST API |
| `jarvis bot` | Start the Telegram bot |
| `jarvis nim status\|models\|test` | NVIDIA NIM helpers |

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

──────────────── Device Detection ────────────────

  System      Ubuntu 22.04.4 LTS (x86_64)
  Python      3.11.2 — /usr/bin/python3
  CPU / RAM   16 cores · 62.7 GB
  Disk free   412.8 GB
  GPU         NVIDIA RTX 4090 · 24564 MB · CUDA 12.4
  Accelerator cuda
  Install to  venv

────────────────── Dependencies ──────────────────

  ✓ litellm                1.96.2   LLM routing
  ✘ fastapi                missing  REST API server
  ✘ uvicorn                missing  ASGI server

  2 package(s) missing.
  Installing automatically…
  ✓ Installed 2 package(s)

────────────────── LLM Provider ──────────────────

  [1] NVIDIA NIM  — build.nvidia.com, generous free tier
  [2] OpenAI      — GPT-4o
  [3] Anthropic   — Claude
  [4] Ollama      — local, free
  [5] Groq        — fast free tier
  [6] Other

  Choice [1]: 1

─────────────────── NVIDIA NIM ───────────────────

  ✓ NVIDIA GPU detected: NVIDIA RTX 4090

  [1] Hosted  — integrate.api.nvidia.com, just needs an API key
  [2] Local   — self-hosted NIM container (available)

  Choice [1]: 1
  NVIDIA API key: nvapi-...

  Validating endpoint…
  ✓ Connected — 87 models available (412 ms)

  Pick a model:
  — General —
   [1] meta/llama-3.3-70b-instruct
   ...
  Model [1]: 1
  ✓ Model: meta/llama-3.3-70b-instruct
  ✓ Model replied: OK (734 ms)

────────────────── Telegram Bot ──────────────────

  Bot token: 123456:ABC-DEF...
  ✓ Connected to @my_jarvis_bot
  Restrict access? [Y/n]: y
  Your Telegram user ID(s): 12345678

─────────────────── REST API ─────────────────────

  Enable the REST API? [Y/n]: y
  Bind host [127.0.0.1]:
  Port [8088]:
  ✓ API will listen on http://127.0.0.1:8088

──────────────────── Ready ───────────────────────

  ✓ Configuration saved
```

Then talk to your bot on Telegram. That's it.

## NVIDIA NIM

Hosted (no GPU needed) or self-hosted on your own NVIDIA GPU:

```bash
jarvis setup nim     # configure
jarvis nim status    # endpoint, key, latency
jarvis nim models    # list what the endpoint serves
jarvis nim test      # end-to-end completion test
```

The wizard validates your key against `/models` before saving. For self-hosting
it checks GPU vendor, VRAM and Docker first, and prints the `docker run` line
for the NIM container if one isn't already running.

## Device-Aware Install

Dependencies are checked at startup and installed with flags matched to the
machine: `--break-system-packages` + `--user` on PEP 668 systems, nothing extra
in a venv/conda, `--no-cache-dir` in Docker/CI, and CUDA-matched
(`cu124`/`cu121`/`cu118`) or ROCm/CPU wheel indexes for torch-style packages.
Linux, macOS, Windows, WSL, Docker and Android/Termux are all detected.

```bash
jarvis doctor           # what's installed, what's missing, what's configured
jarvis install          # fix everything
jarvis install --system # also apt/dnf/brew install git + ffmpeg
```

## REST API

```bash
jarvis api --host 0.0.0.0 --port 8088
```

Docs at `/docs`. Set `JARVIS_API_KEY` to require a bearer token everywhere
except `/` and `/health`.

`GET /health` · `GET /device` · `GET /deps` · `POST /deps/install` ·
`GET /nim/status` · `GET /nim/models` · `POST /nim/chat` · `POST /nim/test` ·
`GET /telegram/status` · `POST /telegram/send` · `POST /chat` · `POST /reset` ·
`GET /config`

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
