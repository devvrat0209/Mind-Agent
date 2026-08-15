"""Dependency checking and device-aware auto-installation.

Checks whether every requirement is importable at the right version and,
when something is missing, installs it with pip flags chosen for the
machine we actually detected (PEP 668 systems, Termux, Docker, conda,
root vs user, CUDA vs CPU wheels).

Stdlib only at import time so this can run before anything is installed.
"""

from __future__ import annotations

import importlib
import importlib.metadata as md
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from .platform_detect import DeviceInfo, device


# ── requirement table ──────────────────────────────────────────────────

@dataclass(frozen=True)
class Requirement:
    """One dependency. `dist` is the PyPI name, `module` the import name."""
    dist: str
    module: str
    min_version: str = ""
    group: str = "core"            # core | telegram | nim | device | optional
    purpose: str = ""
    optional: bool = False
    # extra pip args for specific platforms, e.g. {"android": ["--no-deps"]}
    platform_skip: tuple[str, ...] = ()

    @property
    def spec(self) -> str:
        return f"{self.dist}>={self.min_version}" if self.min_version else self.dist


REQUIREMENTS: tuple[Requirement, ...] = (
    # core agent
    Requirement("litellm", "litellm", "1.40.0", "core", "LLM routing (OpenAI/Anthropic/NVIDIA NIM/...)"),
    Requirement("rich", "rich", "13.7.0", "core", "Terminal UI for the setup wizard"),
    Requirement("python-dotenv", "dotenv", "1.0.0", "core", "Reads the .env config file"),
    Requirement("prompt-toolkit", "prompt_toolkit", "3.0.43", "core", "Interactive prompts"),
    Requirement("tiktoken", "tiktoken", "0.7.0", "core", "Token counting"),

    # telegram
    Requirement("python-telegram-bot", "telegram", "21.0", "telegram", "Telegram bot client"),

    # nvidia nim + api
    Requirement("httpx", "httpx", "0.27.0", "nim", "Async HTTP client for NVIDIA NIM"),
    Requirement("fastapi", "fastapi", "0.110.0", "nim", "REST API server"),
    Requirement("uvicorn", "uvicorn", "0.29.0", "nim", "ASGI server for the REST API"),
    Requirement("pydantic", "pydantic", "2.6.0", "nim", "Request/response models"),

    # device access
    Requirement("psutil", "psutil", "5.9.0", "device", "System/process/network info"),
    Requirement("Pillow", "PIL", "10.0.0", "device", "Image handling", optional=True,
                platform_skip=()),
    Requirement("aiohttp", "aiohttp", "3.9.0", "device", "Async downloads"),
)

GROUPS = ("core", "telegram", "nim", "device")


# ── status ─────────────────────────────────────────────────────────────

@dataclass
class DepStatus:
    req: Requirement
    installed: bool = False
    version: str = ""
    satisfied: bool = False        # installed AND >= min_version
    reason: str = ""

    @property
    def symbol(self) -> str:
        if self.satisfied:
            return "ok"
        return "optional" if self.req.optional else "missing"


def _parse_version(v: str) -> tuple:
    parts = []
    for chunk in v.split(".")[:4]:
        num = ""
        for ch in chunk:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts)


def check_one(req: Requirement) -> DepStatus:
    st = DepStatus(req=req)
    try:
        st.version = md.version(req.dist)
        st.installed = True
    except md.PackageNotFoundError:
        # some dists report under a different name — fall back to import
        try:
            importlib.import_module(req.module)
            st.installed = True
            st.version = "unknown"
        except Exception:
            st.reason = "not installed"
            return st

    if req.min_version and st.version != "unknown":
        if _parse_version(st.version) < _parse_version(req.min_version):
            st.reason = f"{st.version} < {req.min_version}"
            return st

    st.satisfied = True
    return st


def check_all(groups: Iterable[str] = GROUPS, dev: Optional[DeviceInfo] = None) -> list[DepStatus]:
    """Check every requirement in the given groups."""
    dev = dev or device()
    groups = set(groups)
    out = []
    for req in REQUIREMENTS:
        if req.group not in groups:
            continue
        if dev.os in req.platform_skip:
            continue
        out.append(check_one(req))
    return out


def missing(statuses: Iterable[DepStatus], include_optional: bool = False) -> list[DepStatus]:
    return [s for s in statuses
            if not s.satisfied and (include_optional or not s.req.optional)]


# ── install ────────────────────────────────────────────────────────────

def pip_command(dev: Optional[DeviceInfo] = None) -> list[str]:
    """Base pip invocation for this machine."""
    dev = dev or device()
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]

    if dev.in_venv or dev.in_conda:
        pass                                   # isolated already, install straight in
    elif dev.externally_managed:
        # PEP 668: Debian/Ubuntu/Termux system python
        cmd.append("--break-system-packages")
        if not dev.is_root:
            cmd.append("--user")
    elif not dev.is_root and not dev.in_docker:
        cmd.append("--user")

    if dev.in_docker or os.environ.get("CI"):
        cmd.append("--no-cache-dir")

    return cmd


def extra_index_for(req: Requirement, dev: DeviceInfo) -> list[str]:
    """Device-specific wheel index (torch-style packages only)."""
    if req.dist not in ("torch", "torchvision", "torchaudio"):
        return []
    tag = dev.gpu.cuda_tag
    if tag.startswith("cu"):
        return ["--index-url", f"https://download.pytorch.org/whl/{tag}"]
    if tag.startswith("rocm"):
        return ["--index-url", f"https://download.pytorch.org/whl/{tag}"]
    if dev.gpu.vendor == "apple":
        return []                              # default wheels have MPS
    return ["--index-url", "https://download.pytorch.org/whl/cpu"]


@dataclass
class InstallResult:
    spec: str
    ok: bool
    output: str = ""


def install(
    reqs: Iterable[Requirement],
    dev: Optional[DeviceInfo] = None,
    dry_run: bool = False,
    log: Optional[Callable[[str], None]] = None,
) -> list[InstallResult]:
    """Install the given requirements with device-appropriate flags."""
    dev = dev or device()
    log = log or (lambda m: None)
    base = pip_command(dev)
    results: list[InstallResult] = []

    # group packages that share the same index so we can batch them
    batches: dict[tuple, list[Requirement]] = {}
    for r in reqs:
        batches.setdefault(tuple(extra_index_for(r, dev)), []).append(r)

    for index_args, group in batches.items():
        specs = [r.spec for r in group]
        cmd = base + list(index_args) + specs
        log(f"$ {' '.join(cmd)}")

        if dry_run:
            results += [InstallResult(s, True, "(dry run)") for s in specs]
            continue

        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            ok = p.returncode == 0
            out = (p.stdout or "") + (p.stderr or "")
        except subprocess.SubprocessError as e:
            ok, out = False, str(e)

        if not ok and "--break-system-packages" not in cmd:
            # retry once with the PEP 668 escape hatch
            retry = base + ["--break-system-packages"] + list(index_args) + specs
            log("retrying with --break-system-packages")
            try:
                p = subprocess.run(retry, capture_output=True, text=True, timeout=1800)
                ok = p.returncode == 0
                out += "\n" + (p.stdout or "") + (p.stderr or "")
            except subprocess.SubprocessError as e:
                out += f"\n{e}"

        results += [InstallResult(s, ok, out[-2000:]) for s in specs]

    # bust the import caches so freshly installed modules are visible now
    importlib.invalidate_caches()
    return results


def ensure(
    groups: Iterable[str] = GROUPS,
    auto: bool = True,
    include_optional: bool = False,
    dry_run: bool = False,
    log: Optional[Callable[[str], None]] = None,
) -> tuple[list[DepStatus], list[InstallResult]]:
    """Check deps, install whatever's missing, re-check. The one-call entry point."""
    log = log or (lambda m: None)
    dev = device()
    statuses = check_all(groups, dev)
    gaps = missing(statuses, include_optional)

    if not gaps:
        return statuses, []
    if not auto:
        return statuses, []

    log(f"Installing {len(gaps)} missing package(s) for {dev.summary}")
    results = install([g.req for g in gaps], dev, dry_run=dry_run, log=log)
    return check_all(groups, dev), results


# ── system (non-python) dependencies ───────────────────────────────────

SYSTEM_HINTS = {
    "ffmpeg": {
        "purpose": "Voice message transcoding for Telegram",
        "apt": "apt-get install -y ffmpeg",
        "dnf": "dnf install -y ffmpeg",
        "apk": "apk add ffmpeg",
        "pacman": "pacman -S --noconfirm ffmpeg",
        "brew": "brew install ffmpeg",
        "pkg": "pkg install -y ffmpeg",
    },
    "git": {
        "purpose": "Self-editing (diff / commit / rollback)",
        "apt": "apt-get install -y git",
        "dnf": "dnf install -y git",
        "apk": "apk add git",
        "pacman": "pacman -S --noconfirm git",
        "brew": "brew install git",
        "pkg": "pkg install -y git",
    },
}


def check_system_tools(dev: Optional[DeviceInfo] = None) -> dict[str, dict]:
    """Which optional CLI tools are present, plus the install command if not."""
    import shutil as _sh
    dev = dev or device()
    out = {}
    for tool, meta in SYSTEM_HINTS.items():
        path = _sh.which(tool)
        cmd = meta.get(dev.pkg_manager, "")
        if cmd and not dev.is_root and dev.os in ("linux",):
            cmd = "sudo " + cmd
        out[tool] = {
            "present": bool(path),
            "path": path or "",
            "purpose": meta["purpose"],
            "install_cmd": cmd,
        }
    return out


def install_system_tool(tool: str, dev: Optional[DeviceInfo] = None) -> tuple[bool, str]:
    """Attempt to install a system tool. Only runs when we can actually do it."""
    dev = dev or device()
    meta = SYSTEM_HINTS.get(tool)
    if not meta:
        return False, f"unknown tool: {tool}"
    cmd = meta.get(dev.pkg_manager)
    if not cmd:
        return False, f"no package manager mapping for {dev.pkg_manager or 'this system'}"
    if not dev.is_root and dev.os == "linux" and not _sudo_available():
        return False, f"needs root — run: sudo {cmd}"
    full = cmd if dev.is_root or dev.os != "linux" else f"sudo -n {cmd}"
    try:
        p = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=900)
        return p.returncode == 0, ((p.stdout or "") + (p.stderr or ""))[-2000:]
    except subprocess.SubprocessError as e:
        return False, str(e)


def _sudo_available() -> bool:
    import shutil as _sh
    if not _sh.which("sudo"):
        return False
    try:
        return subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=5).returncode == 0
    except subprocess.SubprocessError:
        return False


# ── report ─────────────────────────────────────────────────────────────

def report(groups: Iterable[str] = GROUPS) -> dict:
    """Machine-readable health report — used by the /health API endpoint."""
    dev = device()
    statuses = check_all(groups, dev)
    return {
        "device": dev.to_dict(),
        "python_ok": sys.version_info >= (3, 10),
        "dependencies": [
            {
                "name": s.req.dist,
                "group": s.req.group,
                "purpose": s.req.purpose,
                "required": s.req.min_version or "any",
                "installed": s.version or None,
                "satisfied": s.satisfied,
                "optional": s.req.optional,
                "reason": s.reason,
            }
            for s in statuses
        ],
        "missing": [s.req.dist for s in missing(statuses)],
        "system_tools": check_system_tools(dev),
        "pip_command": " ".join(pip_command(dev)),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(report(), indent=2))
