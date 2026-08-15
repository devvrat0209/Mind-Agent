"""CLI — one entry point. First run = setup wizard, then = start bot."""

import os
import sys
import subprocess
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

from .config import Config

THEME = Theme({
    "jarvis": "cyan bold",
    "dim": "dim",
    "good": "green bold",
    "bad": "red bold",
    "warn": "yellow",
})

BANNER = """
[bold cyan]   ██╗ █████╗ ██████╗ █████╗ ██████╗ ██████╗ ██████╗
   ╚═╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██╔══██╗
      ██║  ██║██████╔╝███████║██║  ██║██║   ██║██████╔╝
      ██║  ██║██╔══██╗██╔══██║██║  ██║██║   ██║██╔═══╝
      ╚█████╔╝██║  ██║██║  ██║██████╔╝╚██████╔╝██║
       ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝[/bold cyan]
"""

ENV_FILE = Path(__file__).parent.parent / ".env"


def get_env(key: str) -> str:
    """Get value from .env or environment."""
    val = os.getenv(key, "")
    if not val and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith(f"{key}="):
                val = line.split("=", 1)[1].strip()
                break
    return val


def set_env(key: str, value: str):
    """Write a key=value to .env."""
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()
    else:
        lines = []

    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}=") or line == key:
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(lines) + "\n")


def is_configured() -> bool:
    """Check if we have the minimum config to run."""
    token = get_env("JARVIS_TELEGRAM_TOKEN") or get_env("TELEGRAM_BOT_TOKEN")
    return bool(token)


def run_setup(console: Console):
    """Interactive setup wizard — first run experience."""
    console.print(BANNER)
    console.print("[jarvis]First run — let's set you up.[/jarvis]\n")

    # ── LLM ──────────────────────────────────────────────
    console.rule("[jarvis]LLM Provider[/jarvis]")

    console.print("\nPick your LLM provider:")
    console.print("  [1] OpenAI (GPT-4o) — best quality, needs API key")
    console.print("  [2] Anthropic (Claude) — great quality, needs API key")
    console.print("  [3] Ollama (local) — free, runs on your machine, needs GPU")
    console.print("  [4] Groq — fast, free tier available")
    console.print("  [5] Other (enter model string directly)")

    choice = Prompt.ask("\n  Choice", choices=["1", "2", "3", "4", "5"], default="1", console=console)

    if choice == "1":
        model = "openai/gpt-4o"
        key_name = "OPENAI_API_KEY"
        key_label = "OpenAI API key"
    elif choice == "2":
        model = "anthropic/claude-sonnet-4-20250514"
        key_name = "ANTHROPIC_API_KEY"
        key_label = "Anthropic API key"
    elif choice == "3":
        model = Prompt.ask("  Ollama model name", default="ollama/llama3", console=console)
        key_name = None
        key_label = None
    elif choice == "4":
        model = "groq/llama-3.3-70b-versatile"
        key_name = "GROQ_API_KEY"
        key_label = "Groq API key"
    else:
        model = Prompt.ask("  Model string (e.g. openai/gpt-4o)", console=console)
        key_name = None
        key_label = None

    set_env("JARVIS_LLM", model)
    console.print(f"  [good]✓ Model: {model}[/good]")

    if key_name and key_label:
        key = Prompt.ask(f"\n  {key_label}", console=console, password=True)
        if key:
            set_env(key_name, key)
            console.print(f"  [good]✓ Key saved[/good]")

    # ── Telegram ─────────────────────────────────────────
    console.print()
    console.rule("[jarvis]Telegram Bot[/jarvis]")

    console.print("\n  You need a Telegram bot token.")
    console.print("  [dim]1. Open Telegram, search @BotFather[/dim]")
    console.print("  [dim]2. Send /newbot[/dim]")
    console.print("  [dim]3. Pick a name and username[/dim]")
    console.print("  [dim]4. Copy the token it gives you[/dim]")

    token = Prompt.ask("\n  Bot token", console=console)
    if token:
        set_env("JARVIS_TELEGRAM_TOKEN", token)
        console.print("  [good]✓ Token saved[/good]")

    # ── User ID ──────────────────────────────────────────
    console.print()
    console.rule("[jarvis]Access Control[/jarvis]")

    console.print("\n  Lock JARVIS to your Telegram account?")
    console.print("  [dim]Find your ID: message @userinfobot on Telegram[/dim]")

    lock = Confirm.ask("  Restrict access?", default=True, console=console)
    if lock:
        uid = Prompt.ask("  Your Telegram user ID", console=console)
        if uid:
            set_env("JARVIS_TELEGRAM_USERS", uid)
            console.print("  [good]✓ Locked to your account[/good]")
    else:
        set_env("JARVIS_TELEGRAM_USERS", "")
        console.print("  [warn]⚠ Anyone who finds your bot can use it[/warn]")

    # ── Done ─────────────────────────────────────────────
    console.print()
    console.rule("[jarvis]Ready[/jarvis]")
    console.print("\n  [good]Configuration saved![/good]")
    console.print(f"  Config file: [dim]{ENV_FILE}[/dim]\n")

    return True


def start_bot(console: Console):
    """Start the Telegram bot."""
    console.print(BANNER)
    console.print("[jarvis]Starting JARVIS...[/jarvis]\n")

    # Load .env into process environment
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

    model = os.getenv("JARVIS_LLM", "openai/gpt-4o")
    workspace = os.getenv("JARVIS_WORKSPACE", str(Path.cwd()))

    console.print(f"  Model:     [dim]{model}[/dim]")
    console.print(f"  Workspace: [dim]{workspace}[/dim]")
    console.print(f"  Config:    [dim]{ENV_FILE}[/dim]")
    console.print()
    console.print("[jarvis]Connecting to Telegram...[/jarvis]")
    console.print("[dim]Talk to your bot on Telegram. Press Ctrl+C to stop.[/dim]\n")

    # Import and run the telegram bot
    from .telegram_bot import main as bot_main
    bot_main()


def main():
    """Entry point: jarvis"""
    console = Console(theme=THEME)

    # If not configured, run setup
    if not is_configured():
        run_setup(console)
        # After setup, ask if they want to start now
        if Confirm.ask("\n  Start JARVIS now?", default=True, console=console):
            start_bot(console)
        else:
            console.print("\n  [jarvis]Run 'jarvis' anytime to start.[/jarvis]")
        return

    # Already configured — just start
    start_bot(console)


if __name__ == "__main__":
    main()
