"""Interactive REPL for the agent.

    python -m agent                 # chat in the 'default' session
    python -m agent --session work  # a separate persistent session
    python -m agent --once "hi"     # single turn, then exit

Slash commands: /help /tools /memory /history /files /read <f> /journal /reset /quit
"""
from __future__ import annotations

import argparse
import sys

from . import tools
from .config import CONFIG
from .core import Agent
from .selfedit import list_source_files, read_source

DIM, BOLD, CYAN, YELLOW, GREEN, RED, RESET = (
    "\033[2m", "\033[1m", "\033[36m", "\033[33m", "\033[32m", "\033[31m", "\033[0m",
)


def _event(kind: str, text: str) -> None:
    colour = {"thought": DIM, "tool": CYAN, "result": DIM}.get(kind, "")
    prefix = {"thought": "…", "tool": "→", "result": "←"}.get(kind, "·")
    print(f"{colour}{prefix} {text}{RESET}")


def _slash(cmd: str, agent: Agent) -> bool:
    """Handle a slash command. Returns False to exit the REPL."""
    name, _, arg = cmd.partition(" ")
    arg = arg.strip()

    if name in {"/quit", "/exit"}:
        return False
    if name == "/help":
        print(__doc__)
    elif name == "/tools":
        for t in tools.REGISTRY.values():
            print(f"{BOLD}{t.name}{RESET}: {t.description}")
    elif name == "/memory":
        print(agent.memory.summary_block(100))
    elif name == "/history":
        for m in agent.memory.history(agent.session, 30):
            print(f"{BOLD}{m['role']}{RESET}: {m['content'][:300]}")
    elif name == "/journal":
        for e in agent.memory.recent_journal(30):
            print(f"[{e['kind']}] {e['summary']}")
    elif name == "/files":
        print("\n".join(list_source_files()))
    elif name == "/read":
        print(read_source(arg) if arg else "usage: /read <file>")
    elif name == "/reset":
        agent.memory.conn.execute("DELETE FROM episodes WHERE session = ?", (agent.session,))
        agent.memory.conn.commit()
        print(f"{YELLOW}conversation history cleared (long-term facts kept){RESET}")
    else:
        print(f"{RED}unknown command {name}{RESET} - try /help")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent", description="Self-editing agent with memory")
    parser.add_argument("--session", default="default", help="named persistent session")
    parser.add_argument("--once", metavar="TEXT", help="run a single turn and exit")
    parser.add_argument("--model", help="override the model name")
    parser.add_argument("--quiet", action="store_true", help="hide tool-call traces")
    args = parser.parse_args(argv)

    if args.model:
        CONFIG.model = args.model

    agent = Agent(session=args.session)
    hook = None if args.quiet else _event

    if not CONFIG.api_key:
        print(
            f"{YELLOW}warning: no API key set. Export AGENT_API_KEY (and AGENT_BASE_URL "
            f"/ AGENT_MODEL for non-OpenAI providers).{RESET}",
            file=sys.stderr,
        )

    if args.once:
        print(agent.chat(args.once, on_event=hook))
        agent.close()
        return 0

    print(f"{BOLD}self-editing agent{RESET} · model={CONFIG.model} · session={args.session}")
    print(f"{DIM}memory: {CONFIG.db_path}  ·  /help for commands{RESET}")
    try:
        while True:
            try:
                line = input(f"\n{GREEN}you ›{RESET} ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line.startswith("/"):
                if not _slash(line, agent):
                    break
                continue
            answer = agent.chat(line, on_event=hook)
            print(f"\n{BOLD}agent ›{RESET} {answer}")
    except KeyboardInterrupt:
        pass
    finally:
        agent.close()
    print("\nbye - memory saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
