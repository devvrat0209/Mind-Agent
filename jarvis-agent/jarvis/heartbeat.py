"""Heartbeat daemon — scheduled background tasks that keep JARVIS alive & healthy.

Inspired by Conway Automaton's heartbeat system: a lightweight cron-style
daemon that runs alongside the agent, executing periodic tasks (health
checks, LLM connectivity, update checks, log pruning) even while the
agent loop itself is idle.

Default schedule
    status_ping      every 15 min   write ~/.jarvis/status.json + log a pulse
    health_check     every 30 min   CPU / memory / disk — alerts on thresholds
    llm_check        every 6 h      LLM / NIM endpoint reachability
    telegram_check   every 1 h      bot token still valid (getMe)
    check_updates    every 4 h      git upstream — alerts when behind
    prune_logs       every 24 h     rotate any jarvis log file > 10 MB

Tasks that fail back off exponentially (interval × 2^failures, capped at 6 h)
so a broken check can't spam alerts. All state is persisted to
``~/.jarvis/heartbeat.json`` so status survives restarts and can be read
from other processes (CLI, API).

Env knobs
    JARVIS_HEARTBEAT_ENABLED   1/0 (default 1)
    JARVIS_HEARTBEAT_TICK      scheduler resolution in seconds (default 15)
    JARVIS_HB_<TASK>           per-task interval override in seconds,
                               0 disables the task
                               e.g. JARVIS_HB_HEALTH_CHECK=600
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("jarvis.heartbeat")

MAX_BACKOFF = 6 * 3600           # never back off more than 6 hours
STATE_DIR = Path.home() / ".jarvis"
STATE_FILE = STATE_DIR / "heartbeat.json"
STATUS_FILE = STATE_DIR / "status.json"

AlertHandler = Callable[[str, str], None]     # (task_name, message)


# ── task plumbing ──────────────────────────────────────────────────────

@dataclass
class TaskResult:
    ok: bool = True
    summary: str = ""
    alert: str = ""              # non-empty → dispatched to alert handlers


@dataclass
class Task:
    name: str
    interval: float              # seconds between runs
    fn: Callable[[], TaskResult]
    enabled: bool = True
    run_on_start: bool = False
    # runtime state
    last_run: float = 0.0
    last_ok: Optional[bool] = None
    last_summary: str = ""
    runs: int = 0
    failures: int = 0
    consecutive_failures: int = 0

    @property
    def effective_interval(self) -> float:
        """Interval with exponential backoff applied after failures."""
        if self.consecutive_failures == 0:
            return self.interval
        return min(self.interval * (2 ** self.consecutive_failures), MAX_BACKOFF)

    @property
    def next_run(self) -> float:
        if self.last_run == 0.0:
            return 0.0 if self.run_on_start else time.time() + self.interval
        return self.last_run + self.effective_interval

    def due(self, now: float) -> bool:
        return self.enabled and now >= self.next_run

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "interval_s": int(self.interval),
            "effective_interval_s": int(self.effective_interval),
            "last_run": self.last_run,
            "last_ok": self.last_ok,
            "last_summary": self.last_summary,
            "next_run": self.next_run,
            "runs": self.runs,
            "failures": self.failures,
            "consecutive_failures": self.consecutive_failures,
        }


# ── the daemon ─────────────────────────────────────────────────────────

class Heartbeat:
    """Cron-style background daemon. Runs tasks on schedule in one thread."""

    def __init__(self, config=None, tick: Optional[float] = None):
        self.config = config
        self.tick = tick or float(os.getenv("JARVIS_HEARTBEAT_TICK", "15"))
        self.tasks: dict[str, Task] = {}
        self.started_at: Optional[float] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._alert_handlers: list[AlertHandler] = []

    # ── registration ───────────────────────────────────────

    def register(self, name: str, interval: float, fn: Callable[[], TaskResult],
                 run_on_start: bool = False) -> None:
        """Register a task. JARVIS_HB_<NAME> env overrides interval (0 = off)."""
        env_key = f"JARVIS_HB_{name.upper()}"
        raw = os.getenv(env_key, "").strip()
        enabled = True
        if raw:
            try:
                override = float(raw)
                if override <= 0:
                    enabled = False
                else:
                    interval = override
            except ValueError:
                logger.warning("Ignoring bad %s=%r", env_key, raw)
        self.tasks[name] = Task(name=name, interval=interval, fn=fn,
                                enabled=enabled, run_on_start=run_on_start)

    def on_alert(self, handler: AlertHandler) -> None:
        self._alert_handlers.append(handler)

    # ── lifecycle ──────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self.started_at = time.time()
        self._stop.clear()
        self._load_state()
        self._thread = threading.Thread(target=self._loop, name="jarvis-heartbeat",
                                        daemon=True)
        self._thread.start()
        active = [t.name for t in self.tasks.values() if t.enabled]
        logger.info("Heartbeat started — %d tasks: %s (tick %.0fs)",
                    len(active), ", ".join(active), self.tick)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.tick + 5)
        logger.info("Heartbeat stopped")

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = time.time()
            for task in list(self.tasks.values()):
                if task.due(now):
                    self.run_task(task.name)
            self._stop.wait(self.tick)

    # ── execution ──────────────────────────────────────────

    def run_task(self, name: str) -> TaskResult:
        """Run a single task now (also callable manually / via API / CLI)."""
        task = self.tasks.get(name)
        if task is None:
            return TaskResult(ok=False, summary=f"unknown task: {name}")

        started = time.time()
        try:
            result = task.fn() or TaskResult()
        except Exception as e:                                    # noqa: BLE001
            result = TaskResult(ok=False, summary=f"{type(e).__name__}: {e}")

        task.last_run = started
        task.last_ok = result.ok
        task.last_summary = result.summary[:300]
        task.runs += 1
        if result.ok:
            task.consecutive_failures = 0
        else:
            task.failures += 1
            task.consecutive_failures += 1
            logger.warning("heartbeat task %s failed (%d in a row): %s",
                           name, task.consecutive_failures, result.summary)

        if result.alert:
            self._dispatch_alert(name, result.alert)

        self._save_state()
        return result

    def _dispatch_alert(self, task_name: str, message: str) -> None:
        logger.warning("heartbeat alert [%s]: %s", task_name, message)
        for handler in self._alert_handlers:
            try:
                handler(task_name, message)
            except Exception as e:                                # noqa: BLE001
                logger.error("alert handler failed: %s", e)

    # ── state / status ─────────────────────────────────────

    def status(self) -> dict:
        return {
            "running": self.running,
            "started_at": self.started_at,
            "uptime_s": int(time.time() - self.started_at) if self.started_at else 0,
            "tick_s": self.tick,
            "tasks": [t.to_dict() for t in self.tasks.values()],
        }

    def _save_state(self) -> None:
        with self._lock:
            try:
                STATE_DIR.mkdir(parents=True, exist_ok=True)
                payload = {"saved_at": time.time(), **self.status()}
                tmp = STATE_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(payload, indent=2))
                tmp.replace(STATE_FILE)
            except OSError as e:
                logger.debug("could not persist heartbeat state: %s", e)

    def _load_state(self) -> None:
        """Restore last-run timestamps so restarts don't re-fire everything."""
        try:
            saved = json.loads(STATE_FILE.read_text())
        except (OSError, ValueError):
            return
        for entry in saved.get("tasks", []):
            task = self.tasks.get(entry.get("name", ""))
            if task:
                task.last_run = float(entry.get("last_run", 0.0))
                task.runs = int(entry.get("runs", 0))
                task.failures = int(entry.get("failures", 0))


# ── built-in tasks ─────────────────────────────────────────────────────

def _task_status_ping(config, hb: "Heartbeat") -> Callable[[], TaskResult]:
    def run() -> TaskResult:
        payload = {
            "ts": time.time(),
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "model": getattr(config, "llm_model", "?"),
            "uptime_s": int(time.time() - hb.started_at) if hb.started_at else 0,
            "tasks_ok": sum(1 for t in hb.tasks.values() if t.last_ok),
            "tasks_failing": sum(1 for t in hb.tasks.values()
                                 if t.last_ok is False),
        }
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            STATUS_FILE.write_text(json.dumps(payload, indent=2))
        except OSError as e:
            return TaskResult(ok=False, summary=f"cannot write status file: {e}")
        logger.info("pulse — up %ss, model %s", payload["uptime_s"], payload["model"])
        return TaskResult(summary=f"pulse written (up {payload['uptime_s']}s)")
    return run


def _task_health_check() -> Callable[[], TaskResult]:
    def run() -> TaskResult:
        try:
            import psutil
        except ImportError:
            return TaskResult(ok=False, summary="psutil not installed")

        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.home()))
        summary = (f"cpu {cpu:.0f}% · mem {mem.percent:.0f}% · "
                   f"disk {disk.percent:.0f}% ({disk.free // 2**30} GiB free)")

        problems = []
        if disk.percent >= 90:
            problems.append(f"disk {disk.percent:.0f}% full "
                            f"({disk.free // 2**30} GiB left)")
        if mem.percent >= 95:
            problems.append(f"memory at {mem.percent:.0f}%")
        if problems:
            return TaskResult(ok=True, summary=summary,
                              alert="⚠️ Health check: " + "; ".join(problems))
        return TaskResult(summary=summary)
    return run


def _task_llm_check(config) -> Callable[[], TaskResult]:
    def run() -> TaskResult:
        if getattr(config, "uses_nim", False):
            from . import nim as nimmod
            check = nimmod.validate_key(nimmod.NIMConfig.from_env())
            if not check.ok:
                return TaskResult(ok=False, summary=check.message,
                                  alert=f"🔌 LLM check failed: {check.message}")
            return TaskResult(summary=f"NIM ok ({check.latency_ms} ms)")

        # non-NIM providers: verify a key is configured for the model prefix
        model = getattr(config, "llm_model", "")
        needed = {"openai/": "OPENAI_API_KEY", "anthropic/": "ANTHROPIC_API_KEY",
                  "groq/": "GROQ_API_KEY"}
        for prefix, env in needed.items():
            if model.startswith(prefix) and not os.getenv(env):
                return TaskResult(ok=False, summary=f"{env} not set",
                                  alert=f"🔌 LLM check: {env} is not set for {model}")
        return TaskResult(summary=f"{model or 'llm'}: config looks ok")
    return run


def _task_telegram_check() -> Callable[[], TaskResult]:
    def run() -> TaskResult:
        token = os.getenv("JARVIS_TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            return TaskResult(summary="no token configured — skipped")
        try:
            import httpx
            r = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
            data = r.json()
        except Exception as e:                                    # noqa: BLE001
            return TaskResult(ok=False, summary=f"unreachable: {e}")
        if not data.get("ok"):
            return TaskResult(ok=False, summary="token rejected by Telegram",
                              alert="🤖 Telegram bot token is no longer valid!")
        return TaskResult(summary=f"@{data['result'].get('username', '?')} ok")
    return run


def _task_check_updates(config) -> Callable[[], TaskResult]:
    def run() -> TaskResult:
        repo = getattr(config, "home_dir", None) or Path(__file__).parent.parent
        git = shutil.which("git")
        if not git:
            return TaskResult(summary="git not installed — skipped")

        def _git(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([git, "-C", str(repo), *args],
                                  capture_output=True, text=True, timeout=60)

        if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
            return TaskResult(summary="not a git checkout — skipped")
        if _git("rev-parse", "--abbrev-ref", "@{upstream}").returncode != 0:
            return TaskResult(summary="no upstream configured — skipped")
        if _git("fetch", "--quiet").returncode != 0:
            return TaskResult(ok=False, summary="git fetch failed")

        behind = _git("rev-list", "--count", "HEAD..@{upstream}").stdout.strip()
        if behind.isdigit() and int(behind) > 0:
            return TaskResult(
                summary=f"{behind} commit(s) behind upstream",
                alert=f"⬆️ Update available: {behind} new commit(s) on upstream. "
                      f"Run git pull + /restart to update.")
        return TaskResult(summary="up to date")
    return run


def _task_prune_logs(max_mb: int = 10) -> Callable[[], TaskResult]:
    def run() -> TaskResult:
        candidates = [os.getenv("JARVIS_LOG_DIR"), "/var/log/jarvis",
                      str(Path.home() / ".jarvis" / "logs"), "/tmp/jarvis"]
        rotated = []
        for cand in candidates:
            if not cand or not Path(cand).is_dir():
                continue
            for logfile in Path(cand).glob("*.log"):
                try:
                    if logfile.stat().st_size > max_mb * 2**20:
                        backup = logfile.with_suffix(".log.1")
                        backup.unlink(missing_ok=True)
                        logfile.rename(backup)
                        logfile.touch()
                        rotated.append(str(logfile))
                except OSError:
                    continue
        if rotated:
            return TaskResult(summary=f"rotated: {', '.join(rotated)}")
        return TaskResult(summary="nothing to rotate")
    return run


# ── factory / singleton ────────────────────────────────────────────────

_instance: Optional[Heartbeat] = None


def heartbeat_enabled() -> bool:
    return os.getenv("JARVIS_HEARTBEAT_ENABLED", "1") == "1"


def create_default_heartbeat(config=None) -> Heartbeat:
    """Build a Heartbeat with the default JARVIS task schedule."""
    if config is None:
        from .config import Config
        config = Config()

    hb = Heartbeat(config)
    hb.register("status_ping",    15 * 60,  _task_status_ping(config, hb),
                run_on_start=True)
    hb.register("health_check",   30 * 60,  _task_health_check(),
                run_on_start=True)
    hb.register("llm_check",      6 * 3600, _task_llm_check(config))
    hb.register("telegram_check", 3600,     _task_telegram_check())
    hb.register("check_updates",  4 * 3600, _task_check_updates(config))
    hb.register("prune_logs",     24 * 3600, _task_prune_logs())
    return hb


def get_heartbeat(config=None) -> Heartbeat:
    """Process-wide singleton so the bot and API share one daemon."""
    global _instance
    if _instance is None:
        _instance = create_default_heartbeat(config)
    return _instance


def read_persisted_state() -> Optional[dict]:
    """Read heartbeat state written by another process (for CLI/API views)."""
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return None


def format_status(state: dict) -> str:
    """Human-readable status block (used by CLI and /heartbeat command)."""
    lines = []
    running = state.get("running", False)
    up = state.get("uptime_s", 0)
    lines.append(f"{'🫀 running' if running else '💤 not running'} · "
                 f"uptime {up // 3600}h {(up % 3600) // 60}m · "
                 f"tick {int(state.get('tick_s', 0))}s")
    now = time.time()
    for t in state.get("tasks", []):
        if t.get("last_ok") is None:
            mark = "·"
        else:
            mark = "✓" if t["last_ok"] else "✗"
        if t.get("last_run"):
            ago = int(now - t["last_run"])
            when = f"{ago // 60}m ago" if ago >= 60 else f"{ago}s ago"
        else:
            when = "never"
        nxt = t.get("next_run", 0) - now
        nxt_s = f"in {int(nxt) // 60}m" if nxt > 0 else "due"
        flag = "" if t.get("enabled", True) else " (disabled)"
        summary = t.get("last_summary") or ""
        lines.append(f" {mark} {t['name']:<15} every {t['interval_s'] // 60}m · "
                     f"last {when} · next {nxt_s}{flag}")
        if summary:
            lines.append(f"      {summary}")
    return "\n".join(lines)
