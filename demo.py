#!/usr/bin/env python3
"""Offline demo - no API key required.

Drives the real agent loop with a scripted fake LLM so you can watch it
remember facts, read its own source, patch itself, verify the change, and
roll it back. Everything except the model is production code.

    python3 demo.py
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from agent import selfedit
from agent.config import CONFIG
from agent.core import Agent
from agent.memory import Memory

BOLD, DIM, CYAN, RESET = "\033[1m", "\033[2m", "\033[36m", "\033[0m"


class ScriptedLLM:
    def __init__(self, script):
        self.script = list(script)

    def chat(self, messages, tools=None, temperature=None):
        return self.script.pop(0)


def call(name, **args):
    return {
        "content": None,
        "tool_calls": [
            {"id": f"c_{name}", "function": {"name": name, "arguments": json.dumps(args)}}
        ],
    }


def event(kind, text):
    prefix = {"thought": f"{DIM}…", "tool": f"{CYAN}→", "result": f"{DIM}←"}[kind]
    print(f"  {prefix} {text}{RESET}")


def turn(agent, label, user, script):
    agent.llm = ScriptedLLM(script)
    print(f"\n{BOLD}── {label}{RESET}\n  {BOLD}you ›{RESET} {user}")
    print(f"  {BOLD}agent ›{RESET} {agent.chat(user, on_event=event)}")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="agent-demo-"))
    CONFIG.state_dir = tmp
    CONFIG.ensure_dirs()
    memory = Memory(CONFIG.db_path)
    agent = Agent(session="demo", memory=memory, llm=ScriptedLLM([]))

    scratch = "demo_scratch.py"
    selfedit.write_source(scratch, "GREETING = 'hello'\n")

    try:
        turn(agent, "1. Persistent memory", "I'm Devvrat and I prefer terse answers.", [
            call("remember", key="user.name", value="Devvrat"),
            call("remember", key="pref.style", value="terse answers", tags="style"),
            {"content": "Noted - stored both to long-term memory."},
        ])

        turn(agent, "2. Reading its own code", "What files are you made of?", [
            call("list_own_code"),
            {"content": "Those are my source files; agent/core.py holds my loop."},
        ])

        turn(agent, "3. Editing itself", f"Change GREETING in {scratch} to 'hi there'.", [
            call("read_own_code", path=scratch),
            call("patch_own_code", path=scratch, find="GREETING = 'hello'",
                 replace="GREETING = 'hi there'"),
            call("self_check"),
            {"content": "Patched and import-checked. Takes effect on restart."},
        ])

        turn(agent, "4. Rejecting a broken edit", "Now write garbage into that file.", [
            call("write_own_code", path=scratch, content="def broken(:\n"),
            {"content": "The edit was rejected by the syntax gate; file is intact."},
        ])

        turn(agent, "5. Undo + audit trail", "Undo your change and show the history.", [
            call("rollback_own_code", path=scratch),
            call("change_history"),
            {"content": "Rolled back. The journal above is the durable audit trail."},
        ])

        print(f"\n{BOLD}── Memory survives a restart{RESET}")
        agent.close()
        reopened = Memory(CONFIG.db_path)
        print(f"  new process → recall('user.name') = {reopened.recall('user.name')!r}")
        print(f"  new process → recall('pref.style') = {reopened.recall('pref.style')!r}")
        reopened.close()
        print(f"\n{DIM}Real usage: export AGENT_API_KEY=... && python3 -m agent{RESET}")
    finally:
        path = selfedit.AGENT_ROOT / scratch
        if path.exists():
            path.unlink()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
