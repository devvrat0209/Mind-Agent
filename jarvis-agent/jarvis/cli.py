"""CLI — the interactive JARVIS shell."""

import os
import sys
import signal

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.theme import Theme

from .config import Config
from .agent import Agent


# Rich theme
JARVIS_THEME = Theme({
    "jarvis": "cyan bold",
    "user": "white",
    "system": "dim cyan",
    "error": "red bold",
    "tool": "yellow",
    "success": "green",
    "info": "blue",
})

BANNER = """
[bold cyan]╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ██╗ █████╗ ██████╗ █████╗ ██████╗ ██████╗ ██████╗     ║
║   ╚═╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██╔══██╗    ║
║      ██║  ██║██████╔╝███████║██║  ██║██║   ██║██████╔╝    ║
║      ██║  ██║██╔══██╗██╔══██║██║  ██║██║   ██║██╔═══╝     ║
║      ╚█████╔╝██║  ██║██║  ██║██████╔╝╚██████╔╝██║         ║
║       ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝         ║
║                                                          ║
║   [white]Just A Rather Very Intelligent System[/white]              ║
║   [dim]v0.1.0 — Self-Editing AI Agent[/dim]                        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝[/bold cyan]
"""

HELP_TEXT = """[jarvis]Commands:[/jarvis]
  [tool]/help[/tool]     Show this help
  [tool]/inspect[/tool]  Inspect your own source code
  [tool]/reset[/tool]    Reset conversation
  [tool]/diff[/tool]     Show git diff of changes
  [tool]/rollback[/tool] Undo last edit
  [tool]/config[/tool]   Show current config
  [tool]/model[/tool]    Change LLM model
  [tool]/exit[/tool]     Exit JARVIS

[jarvis]Or just talk to me.[/jarvis] I can read code, write code, edit files, run commands — and edit my own source."""


def main():
    console = Console(theme=JARVIS_THEME)
    config = Config()
    agent = Agent(config)

    # Print banner
    console.print(BANNER)
    console.print(f"[system]Model: {config.llm_model}[/system]")
    console.print(f"[system]Workspace: {config.workspace}[/system]")
    console.print(f"[system]Source: {config.source_dir}[/system]")
    console.print()

    # Setup prompt
    history_file = os.path.expanduser("~/.jarvis_history")
    session = PromptSession(
        history=FileHistory(history_file),
        auto_suggest=AutoSuggestFromHistory(),
    )

    # Graceful exit
    def handle_sigint(sig, frame):
        console.print("\n[system]Use /exit to quit[/system]")

    signal.signal(signal.SIGINT, handle_sigint)

    # Main loop
    while True:
        try:
            user_input = session.prompt(
                [("class:jarvis", "jarvis@stark "), ("class:user", "❯ ")],
                style={"jarvis": "bold cyan", "user": "white"},
            ).strip()
        except EOFError:
            break

        if not user_input:
            continue

        # Handle slash commands
        if user_input.startswith("/"):
            cmd = user_input.lower().strip()

            if cmd in ("/exit", "/quit"):
                console.print("[system]Shutting down... All systems offline.[/system]")
                break

            elif cmd == "/help":
                console.print(HELP_TEXT)
                continue

            elif cmd == "/inspect":
                result = agent.tools.self_inspect()
                console.print(Panel(result.output, title="Self Inspection", border_style="cyan"))
                continue

            elif cmd == "/reset":
                agent.reset()
                console.print("[system]Conversation reset.[/system]")
                continue

            elif cmd == "/diff":
                result = agent.tools.git_diff()
                console.print(Panel(result.output or "(no changes)", title="Git Diff", border_style="yellow"))
                continue

            elif cmd == "/rollback":
                result = agent.tools.rollback()
                if result.error:
                    console.print(f"[error]{result.output}[/error]")
                else:
                    console.print(f"[success]{result.output}[/success]")
                continue

            elif cmd == "/config":
                config_lines = [
                    f"  Model: {config.llm_model}",
                    f"  Temperature: {config.llm_temperature}",
                    f"  Max Tokens: {config.llm_max_tokens}",
                    f"  Workspace: {config.workspace}",
                    f"  Source: {config.source_dir}",
                    f"  Auto Approve: {config.auto_approve}",
                    f"  Allow Outside Edits: {config.allow_outside_edits}",
                    f"  Max Context Messages: {config.max_context_messages}",
                    f"  Edit Stack Depth: {len(agent.tools.edit_stack)}",
                ]
                console.print(Panel("\n".join(config_lines), title="Configuration", border_style="cyan"))
                continue

            elif cmd.startswith("/model"):
                parts = cmd.split(maxsplit=1)
                if len(parts) > 1:
                    config.llm_model = parts[1]
                    console.print(f"[success]Model changed to: {config.llm_model}[/success]")
                else:
                    console.print(f"[system]Current model: {config.llm_model}[/system]")
                    console.print("[system]Usage: /model openai/gpt-4o[/system]")
                continue

            else:
                console.print(f"[error]Unknown command: {cmd}[/error]")
                continue

        # Process with agent
        console.print()
        with console.status("[jarvis]Thinking...[/jarvis]", spinner="dots"):
            try:
                response = agent.chat(user_input)
            except KeyboardInterrupt:
                console.print("[error]Interrupted.[/error]")
                continue
            except Exception as e:
                console.print(f"[error]Error: {e}[/error]")
                continue

        # Display response
        if response:
            # Try to render as markdown for nice formatting
            try:
                console.print(Markdown(response))
            except Exception:
                console.print(response)

        console.print()

    # Goodbye
    console.print("[jarvis]Goodbye. All systems offline.[/jarvis]")


if __name__ == "__main__":
    main()
