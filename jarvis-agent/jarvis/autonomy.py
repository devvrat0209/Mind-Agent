"""Autonomous work loop — JARVIS works on a mission between conversations.

Modeled on Conway Automaton's genesis-prompt-driven agent loop: the creator
gives the automaton a standing purpose, and the heartbeat wakes it up on a
schedule to make real progress toward it — using its actual tools (shell,
file I/O, code execution) — even when nobody is talking to it.

Pieces
    ~/.jarvis/MISSION.md    the standing mission (genesis prompt). No file,
                            no autonomous work — the work task idles.
    ~/.jarvis/journal.md    append-only work journal. Each cycle reads the
                            recent journal so work continues across cycles
                            (and restarts) instead of starting over.
    run_work_cycle()        one wake-up: build context, let the agent work,
                            journal the result, return a summary.

Env knobs
    JARVIS_HB_AGENT_WORK      seconds between work cycles (default 3600,
                              0 disables)
    JARVIS_WORK_MAX_CALLS     max tool calls per cycle (default 15)
    JARVIS_WORK_REPORT        1 = Telegram-report every cycle (default),
                              0 = only journal, stay quiet
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.autonomy")

STATE_DIR = Path.home() / ".jarvis"
MISSION_FILE = STATE_DIR / "MISSION.md"
JOURNAL_FILE = STATE_DIR / "journal.md"

JOURNAL_CONTEXT_CHARS = 4000       # how much recent journal the agent sees
JOURNAL_MAX_BYTES = 512 * 1024     # trim the journal file beyond this

WORK_PROMPT = """[AUTONOMOUS WORK CYCLE — no human is present; do not ask questions]

You are JARVIS running an unattended work cycle. Your creator gave you this
standing mission:

--- MISSION ---
{mission}
--- END MISSION ---

Recent entries from your work journal (your memory across cycles):

--- JOURNAL ---
{journal}
--- END JOURNAL ---

Instructions:
1. Review the journal and decide the single most useful next step toward
   the mission. Continue unfinished work before starting anything new.
2. Do real work NOW using your tools (shell, read/write files, run code).
   Prefer small, completed steps over big, half-finished ones.
3. Never do anything destructive or irreversible. Do not touch credentials.
   Stay inside your workspace unless the mission explicitly says otherwise.
4. End your reply with exactly this block:

WORK REPORT
Did: <what you actually accomplished this cycle>
Next: <the concrete next step for the following cycle>
Blockers: <anything preventing progress, or "none">
"""


# ── mission ────────────────────────────────────────────────────────────

def get_mission() -> str:
    try:
        return MISSION_FILE.read_text().strip()
    except OSError:
        return ""


def set_mission(text: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MISSION_FILE.write_text(text.strip() + "\n")
    append_journal("MISSION UPDATED", text.strip())


def clear_mission() -> bool:
    try:
        MISSION_FILE.unlink()
        append_journal("MISSION CLEARED", "Autonomous work paused by creator.")
        return True
    except OSError:
        return False


# ── journal ────────────────────────────────────────────────────────────

def append_journal(title: str, body: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {stamp} — {title}\n{body.strip()}\n"
    try:
        with JOURNAL_FILE.open("a") as f:
            f.write(entry)
    except OSError as e:
        logger.error("could not write journal: %s", e)
        return
    # keep the journal from growing forever — drop the oldest half
    try:
        if JOURNAL_FILE.stat().st_size > JOURNAL_MAX_BYTES:
            text = JOURNAL_FILE.read_text()
            JOURNAL_FILE.write_text("(older entries trimmed)\n"
                                    + text[len(text) // 2:])
    except OSError:
        pass


def read_journal(max_chars: int = JOURNAL_CONTEXT_CHARS) -> str:
    try:
        text = JOURNAL_FILE.read_text().strip()
    except OSError:
        return "(journal is empty — this is your first work cycle)"
    if not text:
        return "(journal is empty — this is your first work cycle)"
    return text[-max_chars:]


# ── the work cycle ─────────────────────────────────────────────────────

def extract_report(response: str) -> str:
    """Pull the WORK REPORT block out of the agent's response, if present."""
    marker = "WORK REPORT"
    idx = response.rfind(marker)
    if idx == -1:
        return response[-500:].strip()
    return response[idx:].strip()[:800]


def run_work_cycle(config=None) -> tuple[bool, str]:
    """One autonomous wake-up. Returns (ok, summary)."""
    mission = get_mission()
    if not mission:
        return True, "no mission set — idle (set one with /mission <text>)"

    if config is None:
        from .config import Config
        config = Config()

    try:
        config.max_tool_calls_per_turn = int(
            os.getenv("JARVIS_WORK_MAX_CALLS", "15"))
    except (ValueError, AttributeError):
        pass

    # fresh agent per cycle: the journal is the memory, not the chat history
    from .agent import Agent
    agent = Agent(config)

    prompt = WORK_PROMPT.format(mission=mission, journal=read_journal())

    t0 = time.time()
    logger.info("work cycle starting (mission: %s…)", mission[:60])
    try:
        response = agent.chat(prompt)
    except Exception as e:                                        # noqa: BLE001
        summary = f"work cycle crashed: {type(e).__name__}: {e}"
        append_journal("WORK CYCLE FAILED", summary)
        return False, summary

    elapsed = int(time.time() - t0)
    report = extract_report(response)
    append_journal(f"WORK CYCLE ({elapsed}s)", report)
    logger.info("work cycle done in %ss", elapsed)
    return True, report


def work_report_enabled() -> bool:
    return os.getenv("JARVIS_WORK_REPORT", "1") == "1"


def status() -> dict:
    mission = get_mission()
    try:
        journal_size = JOURNAL_FILE.stat().st_size
    except OSError:
        journal_size = 0
    return {
        "mission_set": bool(mission),
        "mission": mission or None,
        "journal_bytes": journal_size,
        "journal_tail": read_journal(1200) if journal_size else None,
    }
