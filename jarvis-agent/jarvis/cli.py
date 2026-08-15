"""CLI entry point.

    jarvis                 first run = setup wizard, then start the Telegram bot
    jarvis setup [section] re-run the wizard (device|deps|llm|nim|telegram|api)
    jarvis doctor          check device, dependencies and configuration
    jarvis install         install missing dependencies for this device
    jarvis device          print detected hardware as JSON
    jarvis api             start the REST API server
    jarvis bot             start the Telegram bot
    jarvis nim <sub>       NIM helpers: status | models | test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import deps as depmod
from .wizard import (
    BANNER,
    ENV_FILE,
    UI,
    is_configured,
    load_env_into_process,
    read_env,
    run_doctor,
    run_wizard,
)

SETUP_SECTIONS = ("device", "deps", "llm", "nim", "telegram", "api")


# ── bootstrap ──────────────────────────────────────────────────────────

def ensure_runtime(groups: tuple[str, ...], quiet: bool = False) -> bool:
    """Make sure the packages a command needs are present; install if not."""
    statuses = depmod.check_all(groups)
    gaps = depmod.missing(statuses)
    if not gaps:
        return True

    ui = UI()
    ui.print()
    ui.warn(f"Missing: {', '.join(g.req.dist for g in gaps)}")
    ui.info(f"Device: {depmod.device().summary}")
    ui.info("Installing automatically…")
    ui.print()

    results = depmod.install([g.req for g in gaps], log=(lambda m: None) if quiet else ui.info)
    failed = [r for r in results if not r.ok]
    if failed:
        ui.print()
        for r in failed:
            ui.bad(f"{r.spec} failed to install")
        ui.info(failed[0].output[-600:])
        ui.print()
        ui.warn("Install them manually, then retry.")
        return False

    ui.ok("Dependencies ready")
    ui.print()
    return True


# ── commands ───────────────────────────────────────────────────────────

def cmd_setup(args) -> int:
    section = args.section
    if section and section not in SETUP_SECTIONS:
        print(f"Unknown section '{section}'. Choose from: {', '.join(SETUP_SECTIONS)}")
        return 2
    run_wizard(auto_deps=not args.no_auto_install, only=section)
    return 0


def cmd_doctor(args) -> int:
    return run_doctor()


def cmd_install(args) -> int:
    ui = UI()
    ui.print(f"[jarvis]{BANNER}[/jarvis]")
    dev = depmod.device()
    ui.print(f"  [dim]{dev.summary}[/dim]")
    ui.print(f"  [dim]pip target: {dev.pip_target}[/dim]")
    ui.print()

    groups = tuple(args.groups) if args.groups else depmod.GROUPS
    statuses, results = depmod.ensure(
        groups=groups,
        auto=True,
        include_optional=args.optional,
        dry_run=args.dry_run,
        log=ui.info,
    )
    ui.print()
    if not results:
        ui.ok("Nothing to install — all dependencies satisfied")
        return 0

    failed = [r for r in results if not r.ok]
    for r in results:
        (ui.ok if r.ok else ui.bad)(r.spec)
    if failed:
        ui.print()
        ui.info(failed[0].output[-800:])
        return 1

    # system tools
    if args.system:
        ui.print()
        for tool, meta in depmod.check_system_tools(dev).items():
            if meta["present"]:
                continue
            ok, out = depmod.install_system_tool(tool, dev)
            (ui.ok if ok else ui.warn)(f"{tool}: {'installed' if ok else out.strip()[-160:]}")

    ui.print()
    ui.ok("Done")
    return 0


def cmd_device(args) -> int:
    from .platform_detect import device as _device

    dev = _device(refresh=True)
    if args.json:
        print(json.dumps(dev.to_dict(), indent=2))
        return 0

    ui = UI()
    ui.print(f"[jarvis]{BANNER}[/jarvis]")
    from .wizard import step_device
    step_device(ui)
    return 0


def cmd_api(args) -> int:
    load_env_into_process()
    if not ensure_runtime(("core", "nim")):
        return 1

    host = args.host or os.getenv("JARVIS_API_HOST", "127.0.0.1")
    port = int(args.port or os.getenv("JARVIS_API_PORT", "8088"))

    ui = UI()
    ui.print(f"[jarvis]{BANNER}[/jarvis]")
    ui.print(f"  [jarvis]REST API[/jarvis]  http://{host}:{port}")
    ui.info(f"docs: http://{host}:{port}/docs")
    ui.info(f"auth: {'Bearer token required' if os.getenv('JARVIS_API_KEY') else 'open (no key set)'}")
    ui.print()

    from .api import serve
    serve(host=host, port=port)
    return 0


def cmd_bot(args) -> int:
    load_env_into_process()
    if not ensure_runtime(("core", "telegram", "device")):
        return 1
    return start_bot()


def cmd_nim(args) -> int:
    load_env_into_process()
    from . import nim as nimmod

    ui = UI()
    cfg = nimmod.NIMConfig.from_env()

    if args.nim_command == "status":
        ui.rule("NVIDIA NIM")
        ui.print()
        ui.print(f"  Mode      [dim]{cfg.mode}[/dim]")
        ui.print(f"  Endpoint  [dim]{cfg.api_base}[/dim]")
        ui.print(f"  Model     [dim]{cfg.model}[/dim]")
        ui.print(f"  API key   [dim]{cfg.masked_key()}[/dim]")
        ui.print()
        check = nimmod.validate_key(cfg)
        (ui.ok if check.ok else ui.bad)(f"{check.message} ({check.latency_ms} ms)")
        return 0 if check.ok else 1

    if args.nim_command == "models":
        models = nimmod.list_models(cfg)
        if not models:
            ui.bad("Could not list models — check `jarvis nim status`")
            return 1
        for m in models:
            marker = " [good]← current[/good]" if m == cfg.model else ""
            ui.print(f"  {m}{marker}")
        ui.print()
        ui.info(f"{len(models)} models")
        return 0

    if args.nim_command == "test":
        ui.info("Checking endpoint…")
        check = nimmod.validate_key(cfg)
        (ui.ok if check.ok else ui.bad)(check.message)
        if not check.ok:
            return 1
        ui.info(f"Testing {cfg.model}…")
        t = nimmod.test_completion(cfg)
        (ui.ok if t.ok else ui.bad)(f"{t.message} ({t.latency_ms} ms)")
        return 0 if t.ok else 1

    return 2


# ── bot start ──────────────────────────────────────────────────────────

def start_bot() -> int:
    ui = UI()
    ui.print(f"[jarvis]{BANNER}[/jarvis]")
    load_env_into_process()

    from .platform_detect import device as _device
    dev = _device()

    model = os.getenv("JARVIS_LLM", "openai/gpt-4o")
    ui.print(f"  Model     [dim]{model}[/dim]")
    ui.print(f"  Device    [dim]{dev.summary}[/dim]")
    ui.print(f"  Config    [dim]{ENV_FILE}[/dim]")

    # optionally run the API alongside the bot
    if os.getenv("JARVIS_API_ENABLED", "0") == "1":
        host = os.getenv("JARVIS_API_HOST", "127.0.0.1")
        port = int(os.getenv("JARVIS_API_PORT", "8088"))
        try:
            import threading
            import uvicorn
            from .api import create_app

            def _run():
                uvicorn.run(create_app(), host=host, port=port, log_level="warning")

            threading.Thread(target=_run, daemon=True).start()
            ui.print(f"  API       [dim]http://{host}:{port}[/dim]")
        except Exception as e:
            ui.warn(f"API failed to start: {e}")

    ui.print()
    ui.print("  [jarvis]Connecting to Telegram…[/jarvis]")
    ui.info("Talk to your bot. Ctrl+C to stop.")
    ui.print()

    from .telegram_bot import main as bot_main
    bot_main()
    return 0


# ── parser ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS — self-editing AI agent with NVIDIA NIM + Telegram",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("setup", help="run the setup wizard")
    s.add_argument("section", nargs="?", help=f"one of: {', '.join(SETUP_SECTIONS)}")
    s.add_argument("--no-auto-install", action="store_true",
                   help="ask before installing missing dependencies")
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("doctor", help="check device, dependencies and config")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("install", help="install missing dependencies for this device")
    s.add_argument("groups", nargs="*", help=f"limit to groups: {', '.join(depmod.GROUPS)}")
    s.add_argument("--optional", action="store_true", help="include optional packages")
    s.add_argument("--system", action="store_true", help="also install system tools (git, ffmpeg)")
    s.add_argument("--dry-run", action="store_true", help="show commands without running them")
    s.set_defaults(func=cmd_install)

    s = sub.add_parser("device", help="show detected hardware")
    s.add_argument("--json", action="store_true", help="machine-readable output")
    s.set_defaults(func=cmd_device)

    s = sub.add_parser("api", help="start the REST API server")
    s.add_argument("--host", help="bind address (default 127.0.0.1)")
    s.add_argument("--port", type=int, help="port (default 8088)")
    s.set_defaults(func=cmd_api)

    s = sub.add_parser("bot", help="start the Telegram bot")
    s.set_defaults(func=cmd_bot)

    s = sub.add_parser("nim", help="NVIDIA NIM helpers")
    s.add_argument("nim_command", choices=["status", "models", "test"])
    s.set_defaults(func=cmd_nim)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        # bare `jarvis` — wizard on first run, otherwise start the bot
        load_env_into_process()
        if not is_configured():
            run_wizard(auto_deps=True)
            load_env_into_process()
            ui = UI()
            if is_configured() and ui.confirm("Start JARVIS now?", default=True):
                sys.exit(cmd_bot(args) if hasattr(args, "func") else start_bot())
            ui.print()
            ui.print("  [jarvis]Run 'jarvis' anytime to start.[/jarvis]")
            sys.exit(0)
        if not ensure_runtime(("core", "telegram", "device")):
            sys.exit(1)
        sys.exit(start_bot())

    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
