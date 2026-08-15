"""Device / platform detection.

Figures out exactly what machine JARVIS is running on so the installer can
pick the right package set, the right pip flags and the right torch/CUDA
wheel index. Pure stdlib — this module must import on a bare Python 3.10
with zero third-party packages installed.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ── helpers ────────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 8) -> tuple[int, str]:
    """Run a command, never raise. Returns (returncode, stdout+stderr)."""
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def _read(path: str) -> str:
    try:
        return Path(path).read_text(errors="ignore")
    except OSError:
        return ""


# ── GPU ────────────────────────────────────────────────────────────────

@dataclass
class GPUInfo:
    vendor: str = "none"           # nvidia | amd | apple | intel | none
    name: str = ""
    count: int = 0
    memory_mb: int = 0
    driver_version: str = ""
    cuda_version: str = ""         # CUDA runtime/driver version, e.g. "12.4"
    compute_capability: str = ""

    @property
    def available(self) -> bool:
        return self.vendor != "none"

    @property
    def cuda_tag(self) -> str:
        """pip index tag for torch wheels: cu124 / cu121 / cu118 / rocm6.1 / cpu."""
        if self.vendor == "amd":
            return "rocm6.1"
        if self.vendor != "nvidia" or not self.cuda_version:
            return "cpu"
        try:
            major, minor = (self.cuda_version.split(".") + ["0"])[:2]
            major, minor = int(major), int(minor)
        except ValueError:
            return "cpu"
        if major >= 12:
            return "cu124" if minor >= 4 else "cu121"
        if major == 11:
            return "cu118"
        return "cpu"


def detect_gpu() -> GPUInfo:
    """Detect an accelerator without importing torch."""
    # NVIDIA
    if shutil.which("nvidia-smi"):
        rc, out = _run([
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version,compute_cap",
            "--format=csv,noheader,nounits",
        ])
        if rc == 0 and out.strip():
            rows = [r for r in out.strip().splitlines() if r.strip()]
            first = [c.strip() for c in rows[0].split(",")]
            gpu = GPUInfo(vendor="nvidia", count=len(rows))
            gpu.name = first[0] if len(first) > 0 else ""
            try:
                gpu.memory_mb = int(float(first[1]))
            except (IndexError, ValueError):
                pass
            gpu.driver_version = first[2] if len(first) > 2 else ""
            gpu.compute_capability = first[3] if len(first) > 3 else ""

            # CUDA version: nvidia-smi header, then nvcc
            rc2, out2 = _run(["nvidia-smi"])
            m = re.search(r"CUDA Version:\s*([0-9]+\.[0-9]+)", out2)
            if m:
                gpu.cuda_version = m.group(1)
            elif shutil.which("nvcc"):
                rc3, out3 = _run(["nvcc", "--version"])
                m = re.search(r"release\s+([0-9]+\.[0-9]+)", out3)
                if m:
                    gpu.cuda_version = m.group(1)
            return gpu

    # Apple Silicon (Metal / MPS)
    if sys.platform == "darwin" and platform.machine() in ("arm64", "aarch64"):
        return GPUInfo(vendor="apple", name=f"Apple {platform.machine()} GPU", count=1)

    # AMD ROCm
    if shutil.which("rocm-smi") or Path("/opt/rocm").exists():
        rc, out = _run(["rocm-smi", "--showproductname"])
        name = ""
        for line in out.splitlines():
            if ":" in line and "card" in line.lower():
                name = line.split(":")[-1].strip()
                break
        return GPUInfo(vendor="amd", name=name or "AMD GPU", count=1)

    # Intel Arc / oneAPI
    if shutil.which("xpu-smi") or Path("/opt/intel/oneapi").exists():
        return GPUInfo(vendor="intel", name="Intel GPU", count=1)

    return GPUInfo()


# ── device ─────────────────────────────────────────────────────────────

@dataclass
class DeviceInfo:
    os: str = ""                   # linux | macos | windows | android | unknown
    os_name: str = ""              # "Ubuntu 22.04", "macOS 14.5", ...
    distro_id: str = ""            # ubuntu | debian | fedora | alpine | arch | ...
    arch: str = ""                 # x86_64 | arm64 | armv7l
    python_version: str = ""
    python_exe: str = ""
    cpu_count: int = 0
    memory_gb: float = 0.0
    disk_free_gb: float = 0.0

    # environment flavour
    in_venv: bool = False
    in_conda: bool = False
    in_docker: bool = False
    in_wsl: bool = False
    in_termux: bool = False
    is_root: bool = False
    externally_managed: bool = False   # PEP 668

    pkg_manager: str = ""          # apt | dnf | yum | apk | pacman | brew | pkg | winget
    gpu: GPUInfo = field(default_factory=GPUInfo)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["gpu"]["available"] = self.gpu.available
        d["gpu"]["cuda_tag"] = self.gpu.cuda_tag
        d["accelerator"] = self.accelerator
        d["pip_target"] = self.pip_target
        return d

    @property
    def accelerator(self) -> str:
        """What torch-ish device string this machine would use."""
        return {
            "nvidia": "cuda",
            "apple": "mps",
            "amd": "rocm",
            "intel": "xpu",
        }.get(self.gpu.vendor, "cpu")

    @property
    def pip_target(self) -> str:
        """Where a pip install would land."""
        if self.in_venv:
            return "venv"
        if self.in_conda:
            return "conda"
        if self.externally_managed:
            return "user (PEP 668 system python)"
        return "system"

    @property
    def summary(self) -> str:
        bits = [f"{self.os_name} ({self.arch})", f"Python {self.python_version}"]
        if self.gpu.available:
            g = f"{self.gpu.name}"
            if self.gpu.count > 1:
                g += f" x{self.gpu.count}"
            if self.gpu.cuda_version:
                g += f" CUDA {self.gpu.cuda_version}"
            bits.append(g)
        else:
            bits.append("CPU only")
        flags = [n for n, v in (
            ("docker", self.in_docker), ("wsl", self.in_wsl),
            ("termux", self.in_termux), ("venv", self.in_venv),
            ("conda", self.in_conda), ("root", self.is_root),
        ) if v]
        if flags:
            # parentheses, not brackets — square brackets get eaten as Rich markup
            bits.append("(" + ", ".join(flags) + ")")
        return " · ".join(bits)


def _detect_os() -> tuple[str, str, str]:
    """Returns (os, os_name, distro_id)."""
    if "ANDROID_ROOT" in os.environ or "com.termux" in os.environ.get("PREFIX", ""):
        rel = os.environ.get("ANDROID_RELEASE", "")
        return "android", f"Android {rel}".strip(), "termux"

    if sys.platform == "darwin":
        return "macos", f"macOS {platform.mac_ver()[0]}", "macos"

    if sys.platform in ("win32", "cygwin"):
        return "windows", f"Windows {platform.release()}", "windows"

    if sys.platform.startswith("linux"):
        osr = _read("/etc/os-release")
        name = re.search(r'^PRETTY_NAME="?([^"\n]+)"?', osr, re.M)
        did = re.search(r"^ID=\"?([^\"\n]+)\"?", osr, re.M)
        return (
            "linux",
            name.group(1) if name else "Linux",
            (did.group(1) if did else "").lower(),
        )

    return "unknown", platform.system() or "unknown", ""


def _detect_pkg_manager(os_kind: str) -> str:
    if os_kind == "android":
        return "pkg" if shutil.which("pkg") else ""
    if os_kind == "macos":
        return "brew" if shutil.which("brew") else ""
    if os_kind == "windows":
        for m in ("winget", "choco", "scoop"):
            if shutil.which(m):
                return m
        return ""
    for m in ("apt-get", "dnf", "yum", "apk", "pacman", "zypper"):
        if shutil.which(m):
            return "apt" if m == "apt-get" else m
    return ""


def _externally_managed() -> bool:
    """PEP 668 — system python refuses plain `pip install`."""
    try:
        import sysconfig
        stdlib = sysconfig.get_paths().get("stdlib", "")
        if stdlib and (Path(stdlib) / "EXTERNALLY-MANAGED").exists():
            return True
    except Exception:
        pass
    return False


def _memory_gb() -> float:
    # psutil may not be installed yet — do it by hand.
    try:
        if sys.platform.startswith("linux"):
            m = re.search(r"MemTotal:\s+(\d+) kB", _read("/proc/meminfo"))
            if m:
                return round(int(m.group(1)) / 1024 / 1024, 1)
        elif sys.platform == "darwin":
            rc, out = _run(["sysctl", "-n", "hw.memsize"])
            if rc == 0 and out.strip().isdigit():
                return round(int(out.strip()) / 1024 ** 3, 1)
        elif sys.platform == "win32":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = MS()
            st.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return round(st.ullTotalPhys / 1024 ** 3, 1)
    except Exception:
        pass
    return 0.0


def detect_device(probe_gpu: bool = True) -> DeviceInfo:
    """Full device probe. Cheap (a few subprocess calls), no imports needed."""
    os_kind, os_name, distro = _detect_os()

    try:
        du = shutil.disk_usage(str(Path.home()))
        disk_free = round(du.free / 1024 ** 3, 1)
    except OSError:
        disk_free = 0.0

    arch = platform.machine().lower()
    arch = {"amd64": "x86_64", "aarch64": "arm64", "x64": "x86_64"}.get(arch, arch)

    return DeviceInfo(
        os=os_kind,
        os_name=os_name,
        distro_id=distro,
        arch=arch,
        python_version=platform.python_version(),
        python_exe=sys.executable,
        cpu_count=os.cpu_count() or 1,
        memory_gb=_memory_gb(),
        disk_free_gb=disk_free,
        in_venv=sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        in_conda=bool(os.environ.get("CONDA_PREFIX")),
        in_docker=Path("/.dockerenv").exists() or "docker" in _read("/proc/1/cgroup"),
        in_wsl="microsoft" in _read("/proc/version").lower(),
        in_termux=os_kind == "android",
        is_root=hasattr(os, "geteuid") and os.geteuid() == 0,
        externally_managed=_externally_managed(),
        pkg_manager=_detect_pkg_manager(os_kind),
        gpu=detect_gpu() if probe_gpu else GPUInfo(),
    )


# Cached singleton — probing shells out, so don't redo it per call.
_CACHE: Optional[DeviceInfo] = None


def device(refresh: bool = False) -> DeviceInfo:
    global _CACHE
    if _CACHE is None or refresh:
        _CACHE = detect_device()
    return _CACHE


if __name__ == "__main__":
    import json
    print(json.dumps(device().to_dict(), indent=2))
