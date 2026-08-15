"""Setup wizard — dependencies, device, NVIDIA NIM, Telegram, API.

Runs on first launch (or `jarvis setup`). Every step is idempotent and
re-runnable, so it doubles as a repair tool.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from . import deps as depmod
from . import nim as nimmod
from .platform_detect import device

ENV_FILE = Path(__file__).parent.parent / ".env"

BANNER = r"""
   ██╗ █████╗ ██████╗ █████╗ ██████╗ ██████╗ ██████╗
   ╚═╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██╔══██╗
      ██║  ██║██████╔╝███████║██║  ██║██║   ██║██████╔╝
      ██║  ██║██╔══██╗██╔══██║██║  ██║██║   ██║██╔═══╝
      ╚█████╔╝██║  ██║██║  ██║██████╔╝╚██████╔╝██║
       ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝
"""


# ── .env I/O ───────────────────────────────────────────────────────────

def read_env(key: str, default: str = "") -> str:
    val = os.getenv(key, "")
    if val:
        return val
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip()
    return default


def write_env(values: dict[str, str]) -> None:
    """Merge values into .env, preserving comments and ordering."""
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    remaining = dict(values)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        k = stripped.split("=", 1)[0].strip()
        if k in remaining:
            lines[i] = f"{k}={remaining.pop(k)}"

    if remaining:
        if lines and lines[-1].strip():
            lines.append("")
        for k, v in remaining.items():
            lines.append(f"{k}={v}")

    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(lines).rstrip() + "\n")
    try:
        ENV_FILE.chmod(0o600)          # it holds API keys
    except OSError:
        pass


def load_env_into_process() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def is_configured() -> bool:
    """Minimum viable config: a Telegram token and some LLM credential."""
    token = read_env("JARVIS_TELEGRAM_TOKEN") or read_env("TELEGRAM_BOT_TOKEN")
    llm = (read_env("NVIDIA_NIM_API_KEY") or read_env("OPENAI_API_KEY")
           or read_env("ANTHROPIC_API_KEY") or read_env("GROQ_API_KEY")
           or read_env("JARVIS_NIM_MODE") == "local"
           or read_env("JARVIS_LLM", "").startswith("ollama/"))
    return bool(token and llm)


# ── console (degrades gracefully if rich is missing) ───────────────────

class UI:
    """Thin wrapper so step 1 can run before `rich` is installed."""

    def __init__(self):
        self.rich = None
        try:
            from rich.console import Console
            from rich.theme import Theme
            self.rich = Console(theme=Theme({
                "jarvis": "cyan bold", "dim": "dim", "good": "green bold",
                "bad": "red bold", "warn": "yellow bold", "info": "blue",
            }))
        except ImportError:
            pass

    # -- output ---------------------------------------------------------
    def print(self, msg: str = "") -> None:
        if self.rich:
            self.rich.print(msg)
        else:
            import re
            print(re.sub(r"\[/?[a-z ]+\]", "", msg))

    def rule(self, title: str) -> None:
        if self.rich:
            self.rich.rule(f"[jarvis]{title}[/jarvis]")
        else:
            print(f"\n──── {title} " + "─" * max(0, 50 - len(title)))

    def ok(self, msg: str) -> None:
        self.print(f"  [good]✓[/good] {msg}")

    def bad(self, msg: str) -> None:
        self.print(f"  [bad]✘[/bad] {msg}")

    def warn(self, msg: str) -> None:
        self.print(f"  [warn]⚠[/warn] {msg}")

    def info(self, msg: str) -> None:
        self.print(f"  [dim]{msg}[/dim]")

    # -- input ----------------------------------------------------------
    def ask(self, prompt: str, default: str = "", password: bool = False,
            choices: Optional[list[str]] = None) -> str:
        if self.rich:
            from rich.prompt import Prompt
            kw = {"console": self.rich, "password": password}
            if choices:
                kw["choices"] = choices
            if default:
                kw["default"] = default
            return Prompt.ask(f"  {prompt}", **kw)
        # plain fallback
        suffix = f" [{default}]" if default else ""
        if password:
            import getpass
            val = getpass.getpass(f"  {prompt}{suffix}: ")
        else:
            val = input(f"  {prompt}{suffix}: ")
        return val.strip() or default

    def confirm(self, prompt: str, default: bool = True) -> bool:
        if self.rich:
            from rich.prompt import Confirm
            return Confirm.ask(f"  {prompt}", default=default, console=self.rich)
        d = "Y/n" if default else "y/N"
        val = input(f"  {prompt} [{d}]: ").strip().lower()
        return default if not val else val.startswith("y")


# ── steps ──────────────────────────────────────────────────────────────

def step_device(ui: UI) -> None:
    ui.rule("Device Detection")
    dev = device(refresh=True)
    ui.print()
    ui.print(f"  System      [dim]{dev.os_name} ({dev.arch})[/dim]")
    ui.print(f"  Python      [dim]{dev.python_version} — {dev.python_exe}[/dim]")
    ui.print(f"  CPU / RAM   [dim]{dev.cpu_count} cores · {dev.memory_gb} GB[/dim]")
    ui.print(f"  Disk free   [dim]{dev.disk_free_gb} GB[/dim]")

    if dev.gpu.available:
        g = dev.gpu
        detail = f"{g.name}"
        if g.count > 1:
            detail += f" ×{g.count}"
        if g.memory_mb:
            detail += f" · {g.memory_mb} MB"
        if g.cuda_version:
            detail += f" · CUDA {g.cuda_version}"
        ui.print(f"  GPU         [good]{detail}[/good]")
    else:
        ui.print("  GPU         [dim]none detected — CPU only[/dim]")

    ui.print(f"  Accelerator [dim]{dev.accelerator}[/dim]")
    ui.print(f"  Install to  [dim]{dev.pip_target}[/dim]")

    flags = [n for n, v in (("Docker", dev.in_docker), ("WSL", dev.in_wsl),
                            ("Termux", dev.in_termux), ("venv", dev.in_venv),
                            ("conda", dev.in_conda), ("root", dev.is_root),
                            ("PEP 668", dev.externally_managed)) if v]
    if flags:
        ui.print(f"  Environment [dim]{', '.join(flags)}[/dim]")
    ui.print()

    if sys.version_info < (3, 10):
        ui.bad(f"Python {dev.python_version} is too old — JARVIS needs ≥ 3.10")
        sys.exit(1)


def step_dependencies(ui: UI, auto: bool = True) -> bool:
    ui.rule("Dependencies")
    dev = device()
    statuses = depmod.check_all()
    gaps = depmod.missing(statuses)

    ui.print()
    for s in statuses:
        name = s.req.dist
        if s.satisfied:
            ui.print(f"  [good]✓[/good] {name:<22} [dim]{s.version:<12} {s.req.purpose}[/dim]")
        elif s.req.optional:
            ui.print(f"  [warn]○[/warn] {name:<22} [dim]{'optional':<12} {s.req.purpose}[/dim]")
        else:
            ui.print(f"  [bad]✘[/bad] {name:<22} [dim]{s.reason:<12} {s.req.purpose}[/dim]")
    ui.print()

    if gaps:
        ui.print(f"  [warn]{len(gaps)} package(s) missing.[/warn]")
        ui.info(f"pip target: {dev.pip_target}")
        ui.info(f"command: {' '.join(depmod.pip_command(dev))} ...")
        ui.print()

        do_it = auto or ui.confirm("Install them now?", default=True)
        if not do_it:
            ui.warn("Skipped — JARVIS may not start until these are installed.")
            return False

        ui.print()
        results = depmod.install([g.req for g in gaps], dev, log=lambda m: ui.info(m))
        ui.print()
        failed = [r for r in results if not r.ok]
        if failed:
            for r in failed:
                ui.bad(f"{r.spec} failed")
            ui.info(failed[0].output[-500:])
            ui.print()
            ui.warn("Fix the errors above, then re-run: jarvis setup")
            return False
        ui.ok(f"Installed {len(results)} package(s)")
    else:
        ui.ok("All Python dependencies satisfied")

    # system tools
    tools = depmod.check_system_tools(dev)
    absent = {t: m for t, m in tools.items() if not m["present"]}
    if absent:
        ui.print()
        for tool, meta in absent.items():
            ui.warn(f"{tool} not found — {meta['purpose']}")
            if meta["install_cmd"]:
                ui.info(f"install: {meta['install_cmd']}")
        if auto is False and ui.confirm("Try to install these now?", default=False):
            for tool in absent:
                ok, out = depmod.install_system_tool(tool, dev)
                (ui.ok if ok else ui.warn)(f"{tool}: {out.strip()[-160:] or ('installed' if ok else 'failed')}")
    return True


def step_llm(ui: UI) -> dict[str, str]:
    """Pick the LLM provider. NVIDIA NIM is option 1."""
    ui.rule("LLM Provider")
    ui.print()
    ui.print("  [1] NVIDIA NIM  [dim]— build.nvidia.com, generous free tier[/dim]")
    ui.print("  [2] OpenAI      [dim]— GPT-4o[/dim]")
    ui.print("  [3] Anthropic   [dim]— Claude[/dim]")
    ui.print("  [4] Ollama      [dim]— local, free[/dim]")
    ui.print("  [5] Groq        [dim]— fast free tier[/dim]")
    ui.print("  [6] Other       [dim]— any LiteLLM model string[/dim]")
    ui.print()

    choice = ui.ask("Choice", default="1", choices=["1", "2", "3", "4", "5", "6"])
    ui.print()

    if choice == "1":
        return step_nim(ui)

    if choice == "2":
        key = ui.ask("OpenAI API key", password=True)
        return {"JARVIS_LLM": "openai/gpt-4o", "OPENAI_API_KEY": key}

    if choice == "3":
        key = ui.ask("Anthropic API key", password=True)
        return {"JARVIS_LLM": "anthropic/claude-sonnet-4-20250514", "ANTHROPIC_API_KEY": key}

    if choice == "4":
        model = ui.ask("Ollama model", default="llama3")
        return {"JARVIS_LLM": f"ollama/{model.removeprefix('ollama/')}"}

    if choice == "5":
        key = ui.ask("Groq API key", password=True)
        return {"JARVIS_LLM": "groq/llama-3.3-70b-versatile", "GROQ_API_KEY": key}

    model = ui.ask("Model string (e.g. openai/gpt-4o)")
    return {"JARVIS_LLM": model}


def step_nim(ui: UI) -> dict[str, str]:
    """Configure NVIDIA NIM — hosted endpoint or a local container."""
    ui.rule("NVIDIA NIM")
    dev = device()

    can_local, local_msg = nimmod.gpu_ready_for_local()
    ui.print()
    if dev.gpu.vendor == "nvidia":
        ui.ok(f"NVIDIA GPU detected: {dev.gpu.name}")
    else:
        ui.info("No NVIDIA GPU here — the hosted endpoint is the way to go.")
    ui.print()
    ui.print("  [1] Hosted  [dim]— integrate.api.nvidia.com, just needs an API key[/dim]")
    ui.print(f"  [2] Local   [dim]— self-hosted NIM container ({'available' if can_local else 'not available'})[/dim]")
    ui.print()

    mode_choice = ui.ask("Choice", default="1" if not can_local else "1", choices=["1", "2"])
    cfg = nimmod.NIMConfig()

    if mode_choice == "2":
        if not can_local:
            ui.warn(local_msg)
            if not ui.confirm("Continue with local anyway?", default=False):
                mode_choice = "1"
        if mode_choice == "2":
            cfg.mode = "local"
            cfg.api_base = ui.ask("NIM base URL", default=nimmod.LOCAL_BASE).rstrip("/")
            ui.print()
            ready = nimmod.local_readiness(cfg.api_base)
            if ready.ok:
                ui.ok(ready.message)
            else:
                ui.warn(f"{ready.message}")
                ui.info("Start one with:")
                for line in nimmod.local_container_command().splitlines():
                    ui.info("  " + line)
            key = ui.ask("API key (blank if the container needs none)", default="", password=True)
            cfg.api_key = key

    if cfg.mode == "hosted":
        ui.print()
        ui.info("Get a free API key:")
        ui.info("  1. Open https://build.nvidia.com")
        ui.info("  2. Sign in, pick any model, click 'Get API Key'")
        ui.info("  3. Copy the nvapi-... key")
        ui.print()
        existing = nimmod.NIMConfig.from_env().api_key
        prompt = "NVIDIA API key" + (" (blank = keep existing)" if existing else "")
        key = ui.ask(prompt, password=True)
        cfg.api_key = key or existing
        cfg.api_base = nimmod.HOSTED_BASE

    # validate
    ui.print()
    ui.info("Validating endpoint…")
    check = nimmod.validate_key(cfg)
    if check.ok:
        ui.ok(f"{check.message} ({check.latency_ms} ms)")
    else:
        ui.bad(check.message)
        if not ui.confirm("Save anyway and continue?", default=True):
            return step_nim(ui)

    # model picker
    ui.print()
    ui.print("  Pick a model:")
    flat = nimmod.flat_catalog()
    n = 0
    last_group = ""
    for group, mid, desc in flat:
        if group != last_group:
            ui.print(f"  [dim]— {group} —[/dim]")
            last_group = group
        n += 1
        ui.print(f"   [{n:>2}] {mid}")
        ui.print(f"        [dim]{desc}[/dim]")
    ui.print(f"   [{n + 1:>2}] Enter a model ID manually")
    ui.print()

    default_idx = str(next((i + 1 for i, (_, m, _) in enumerate(flat) if m == nimmod.DEFAULT_MODEL), 1))
    pick = ui.ask("Model", default=default_idx)
    try:
        idx = int(pick)
        cfg.model = flat[idx - 1][1] if 1 <= idx <= n else ui.ask("Model ID")
    except (ValueError, IndexError):
        cfg.model = pick if "/" in pick else nimmod.DEFAULT_MODEL

    ui.ok(f"Model: {cfg.model}")

    # smoke test
    if check.ok and ui.confirm("Run a quick test completion?", default=True):
        ui.info("Testing…")
        t = nimmod.test_completion(cfg)
        if t.ok:
            ui.ok(f"{t.message} ({t.latency_ms} ms)")
        else:
            ui.warn(t.message)

    return {
        "JARVIS_LLM": cfg.litellm_model,
        nimmod.ENV_KEY: cfg.api_key,
        nimmod.ENV_BASE: cfg.api_base,
        nimmod.ENV_MODEL: cfg.model,
        nimmod.ENV_MODE: cfg.mode,
    }


def step_telegram(ui: UI) -> dict[str, str]:
    ui.rule("Telegram Bot")
    ui.print()
    ui.info("Create a bot:")
    ui.info("  1. Open Telegram, message @BotFather")
    ui.info("  2. Send /newbot and pick a name + username")
    ui.info("  3. Copy the token it gives you")
    ui.print()

    existing = read_env("JARVIS_TELEGRAM_TOKEN")
    prompt = "Bot token" + (" (blank = keep existing)" if existing else "")
    token = ui.ask(prompt, password=bool(existing)) or existing

    out = {"JARVIS_TELEGRAM_TOKEN": token}

    if token:
        ui.print()
        ui.info("Verifying token…")
        ok, info = verify_telegram_token(token)
        if ok:
            ui.ok(f"Connected to @{info}")
        else:
            ui.warn(f"Could not verify: {info}")

    # access control
    ui.print()
    ui.print("  [dim]Restrict who can talk to the bot? Find your ID via @userinfobot.[/dim]")
    if ui.confirm("Restrict access?", default=True):
        uid = ui.ask("Your Telegram user ID(s), comma-separated", default=read_env("JARVIS_TELEGRAM_USERS"))
        out["JARVIS_TELEGRAM_USERS"] = uid
        if uid:
            ui.ok(f"Locked to: {uid}")
    else:
        out["JARVIS_TELEGRAM_USERS"] = ""
        ui.warn("Anyone who finds your bot will be able to use it")

    return out


def verify_telegram_token(token: str) -> tuple[bool, str]:
    """getMe against the Bot API — stdlib only."""
    import json
    import urllib.request
    import urllib.error

    try:
        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/getMe", timeout=15
        ) as r:
            body = json.loads(r.read().decode())
        if body.get("ok"):
            return True, body["result"].get("username", "unknown")
        return False, body.get("description", "rejected")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "401 Unauthorized — token is invalid"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def step_api(ui: UI) -> dict[str, str]:
    ui.rule("REST API")
    ui.print()
    ui.info("JARVIS can expose a local HTTP API for chat, health and device info.")
    ui.print()

    if not ui.confirm("Enable the REST API?", default=True):
        return {"JARVIS_API_ENABLED": "0"}

    host = ui.ask("Bind host", default=read_env("JARVIS_API_HOST", "127.0.0.1"))
    port = ui.ask("Port", default=read_env("JARVIS_API_PORT", "8088"))

    out = {"JARVIS_API_ENABLED": "1", "JARVIS_API_HOST": host, "JARVIS_API_PORT": port}

    if host not in ("127.0.0.1", "localhost"):
        ui.warn("Binding to a public interface — an API key is strongly recommended.")

    existing = read_env("JARVIS_API_KEY")
    if ui.confirm("Protect the API with a key?", default=host not in ("127.0.0.1", "localhost")):
        if existing and ui.confirm("Keep the existing key?", default=True):
            out["JARVIS_API_KEY"] = existing
        else:
            import secrets
            key = secrets.token_urlsafe(32)
            out["JARVIS_API_KEY"] = key
            ui.ok("Generated API key:")
            ui.print(f"     [good]{key}[/good]")
            ui.info("Send it as: Authorization: Bearer <key>")
    else:
        out["JARVIS_API_KEY"] = ""

    ui.print()
    ui.ok(f"API will listen on http://{host}:{port}")
    ui.info(f"docs: http://{host}:{port}/docs")
    return out


# ── orchestration ──────────────────────────────────────────────────────

def run_wizard(auto_deps: bool = True, only: Optional[str] = None) -> bool:
    """Full setup flow. `only` runs a single section: deps|nim|telegram|api|device."""
    ui = UI()
    values: dict[str, str] = {}

    if only in (None, "banner"):
        ui.print(f"[jarvis]{BANNER}[/jarvis]")
        ui.print("  [dim]Just A Rather Very Intelligent System — Setup[/dim]")
        ui.print()

    if only in (None, "device"):
        step_device(ui)
    if only == "device":
        return True

    if only in (None, "deps"):
        # rich may have just been installed — rebuild the UI so later steps are pretty
        step_dependencies(ui, auto=auto_deps)
        if ui.rich is None:
            ui = UI()
    if only == "deps":
        return True

    if only in (None, "llm", "nim"):
        values.update(step_nim(ui) if only == "nim" else step_llm(ui))
        ui.print()
    if only in ("llm", "nim"):
        write_env(values)
        ui.ok(f"Saved to {ENV_FILE}")
        return True

    if only in (None, "telegram"):
        values.update(step_telegram(ui))
        ui.print()
    if only == "telegram":
        write_env(values)
        ui.ok(f"Saved to {ENV_FILE}")
        return True

    if only in (None, "api"):
        values.update(step_api(ui))
        ui.print()
    if only == "api":
        write_env(values)
        ui.ok(f"Saved to {ENV_FILE}")
        return True

    # finish
    write_env(values)
    load_env_into_process()

    ui.rule("Ready")
    ui.print()
    ui.ok("Configuration saved")
    ui.info(f"config: {ENV_FILE}")
    ui.print()
    ui.print("  [dim]Commands:[/dim]")
    ui.print("    [jarvis]jarvis[/jarvis]           [dim]start the Telegram bot[/dim]")
    ui.print("    [jarvis]jarvis api[/jarvis]       [dim]start the REST API[/dim]")
    ui.print("    [jarvis]jarvis doctor[/jarvis]    [dim]re-check deps + device[/dim]")
    ui.print("    [jarvis]jarvis setup[/jarvis]     [dim]re-run this wizard[/dim]")
    ui.print()
    return True


def run_doctor() -> int:
    """Non-interactive health check. Returns a process exit code."""
    ui = UI()
    ui.print(f"[jarvis]{BANNER}[/jarvis]")
    step_device(ui)

    ui.rule("Dependencies")
    ui.print()
    statuses = depmod.check_all()
    for s in statuses:
        if s.satisfied:
            ui.print(f"  [good]✓[/good] {s.req.dist:<22} [dim]{s.version}[/dim]")
        elif s.req.optional:
            ui.print(f"  [warn]○[/warn] {s.req.dist:<22} [dim]optional, {s.reason}[/dim]")
        else:
            ui.print(f"  [bad]✘[/bad] {s.req.dist:<22} [dim]{s.reason}[/dim]")
    gaps = depmod.missing(statuses)
    ui.print()

    ui.rule("System Tools")
    ui.print()
    for tool, meta in depmod.check_system_tools().items():
        if meta["present"]:
            ui.print(f"  [good]✓[/good] {tool:<22} [dim]{meta['path']}[/dim]")
        else:
            ui.print(f"  [warn]○[/warn] {tool:<22} [dim]{meta['install_cmd']}[/dim]")
    ui.print()

    ui.rule("Configuration")
    ui.print()
    load_env_into_process()
    tg = read_env("JARVIS_TELEGRAM_TOKEN")
    ui.print(f"  Telegram token   {'[good]set[/good]' if tg else '[bad]missing[/bad]'}")
    users = read_env("JARVIS_TELEGRAM_USERS")
    ui.print(f"  Allowed users    [dim]{users or 'anyone (!)'}[/dim]")
    ui.print(f"  LLM model        [dim]{read_env('JARVIS_LLM', '(unset)')}[/dim]")

    cfg = nimmod.NIMConfig.from_env()
    if cfg.api_key or cfg.mode == "local":
        ui.print(f"  NIM mode         [dim]{cfg.mode} · {cfg.api_base}[/dim]")
        ui.print(f"  NIM key          [dim]{cfg.masked_key()}[/dim]")
        check = nimmod.validate_key(cfg)
        (ui.ok if check.ok else ui.bad)(f"NIM: {check.message}")
    api_on = read_env("JARVIS_API_ENABLED", "0") == "1"
    ui.print(f"  REST API         [dim]{'enabled on ' + read_env('JARVIS_API_HOST','127.0.0.1') + ':' + read_env('JARVIS_API_PORT','8088') if api_on else 'disabled'}[/dim]")
    ui.print()

    if gaps:
        ui.warn(f"{len(gaps)} missing dependency(ies) — run: jarvis install")
        return 1
    if not tg:
        ui.warn("Telegram not configured — run: jarvis setup")
        return 1
    ui.ok("Everything looks good.")
    return 0
