"""Device access tools — full system control.

File system, processes, network, clipboard, screenshots,
downloads, system info, media, notifications, app control.
"""

import os
import subprocess
import shutil
import platform
import json
import time
import base64
from pathlib import Path
from typing import Optional

import psutil


class DeviceTools:
    """Full device access tools."""

    def __init__(self, config):
        self.config = config

    @property
    def tool_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "system_info",
                    "description": "Get full system info: OS, CPU, RAM, disk, uptime, battery, network interfaces.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_processes",
                    "description": "List running processes with CPU/memory usage. Can filter by name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filter": {"type": "string", "description": "Filter processes by name", "default": ""},
                            "kill": {"type": "integer", "description": "PID to kill (optional)", "default": 0},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "network_info",
                    "description": "Get network interfaces, IPs, connections, bandwidth usage.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "disk_usage",
                    "description": "Get disk usage for all mounted partitions.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "screenshot",
                    "description": "Take a screenshot and return the file path.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Where to save (default: /tmp/jarvis_screenshot.png)", "default": ""},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clipboard_read",
                    "description": "Read the system clipboard contents.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clipboard_write",
                    "description": "Write text to the system clipboard.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Text to copy to clipboard"},
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "open_app",
                    "description": "Open an application or file with the system's default handler.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string", "description": "App name or file/URL to open"},
                        },
                        "required": ["target"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "download_file",
                    "description": "Download a file from a URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to download"},
                            "filename": {"type": "string", "description": "Local filename to save as (default: derived from URL)", "default": ""},
                        },
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notify",
                    "description": "Send a desktop notification.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Notification title"},
                            "message": {"type": "string", "description": "Notification body"},
                        },
                        "required": ["title", "message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "media_capture",
                    "description": "Capture photo from webcam or record audio from microphone.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["photo", "audio"], "description": "photo (webcam) or audio (mic)"},
                            "duration": {"type": "integer", "description": "Duration in seconds for audio recording (default 5)", "default": 5},
                        },
                        "required": ["type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "environment_vars",
                    "description": "Read or set environment variables.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["list", "get", "set"], "description": "list all, get one, or set one"},
                            "key": {"type": "string", "description": "Variable name", "default": ""},
                            "value": {"type": "string", "description": "Value to set", "default": ""},
                        },
                        "required": ["action"],
                    },
                },
            },
        ]

    def call(self, name: str, args: dict) -> dict:
        """Execute a device tool. Returns {output, error, data}."""
        method = getattr(self, f"_tool_{name}", None)
        if not method:
            return {"output": f"Unknown device tool: {name}", "error": True, "data": {}}
        try:
            return method(**args)
        except Exception as e:
            return {"output": f"Error in {name}: {e}", "error": True, "data": {}}

    # ── Implementations ────────────────────────────────────

    def _tool_system_info(self) -> dict:
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "hostname": platform.node(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
            "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 2),
            "ram_used_gb": round(psutil.virtual_memory().used / 1e9, 2),
            "ram_percent": psutil.virtual_memory().percent,
            "uptime_seconds": int(time.time() - psutil.boot_time()),
        }
        # Battery
        if hasattr(psutil, "sensors_battery"):
            bat = psutil.sensors_battery()
            if bat:
                info["battery_percent"] = bat.percent
                info["battery_plugged"] = bat.power_plugged
        output_lines = [f"{k}: {v}" for k, v in info.items()]
        return {"output": "\n".join(output_lines), "error": False, "data": info}

    def _tool_list_processes(self, filter: str = "", kill: int = 0) -> dict:
        if kill:
            try:
                p = psutil.Process(kill)
                name = p.name()
                p.kill()
                return {"output": f"Killed process {kill} ({name})", "error": False, "data": {}}
            except psutil.NoSuchProcess:
                return {"output": f"Process {kill} not found", "error": True, "data": {}}

        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                info = p.info
                if filter and filter.lower() not in info["name"].lower():
                    continue
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU usage
        procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
        procs = procs[:50]  # top 50

        lines = [f"{'PID':>7} {'CPU%':>6} {'MEM%':>6} {'STATUS':<10} NAME"]
        for p in procs:
            lines.append(f"{p['pid']:>7} {p.get('cpu_percent',0) or 0:>5.1f}% {p.get('memory_percent',0) or 0:>5.1f}% {p.get('status',''):<10} {p['name']}")

        return {"output": "\n".join(lines), "error": False, "data": {"count": len(procs)}}

    def _tool_network_info(self) -> dict:
        # Interfaces
        addrs = psutil.net_if_addrs()
        ifaces = []
        for name, addr_list in addrs.items():
            for a in addr_list:
                if a.family.name in ("AF_INET", "AF_INET6"):
                    ifaces.append(f"  {name}: {a.address} ({a.family.name})")

        # Connections
        conns = psutil.net_connections(kind="inet")
        active = [c for c in conns if c.status == "ESTABLISHED"][:20]
        conn_lines = [f"  {c.laddr.ip}:{c.laddr.port} → {c.raddr.ip}:{c.raddr.port} (PID {c.pid})" for c in active]

        # IO counters
        io = psutil.net_io_counters()
        io_info = f"  Total: ↓ {io.bytes_recv/1e6:.1f} MB  ↑ {io.bytes_sent/1e6:.1f} MB"

        output = f"Interfaces:\n" + "\n".join(ifaces) + f"\n\nActive Connections ({len(active)}):\n" + "\n".join(conn_lines) + f"\n\nTraffic:\n{io_info}"
        return {"output": output, "error": False, "data": {}}

    def _tool_disk_usage(self) -> dict:
        lines = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                lines.append(
                    f"  {part.device} on {part.mountpoint} ({part.fstype})\n"
                    f"    Total: {usage.total/1e9:.1f} GB | Used: {usage.used/1e9:.1f} GB ({usage.percent}%) | Free: {usage.free/1e9:.1f} GB"
                )
            except PermissionError:
                lines.append(f"  {part.device} on {part.mountpoint} — (permission denied)")
        return {"output": "\n".join(lines), "error": False, "data": {}}

    def _tool_screenshot(self, path: str = "") -> dict:
        save_path = path or "/tmp/jarvis_screenshot.png"
        try:
            # Try scrot (Linux)
            result = subprocess.run(["scrot", save_path], capture_output=True, timeout=5)
            if result.returncode == 0:
                return {"output": f"Screenshot saved: {save_path}", "error": False, "data": {"path": save_path}}
        except FileNotFoundError:
            pass
        try:
            # Try gnome-screenshot
            result = subprocess.run(["gnome-screenshot", "-f", save_path], capture_output=True, timeout=5)
            if result.returncode == 0:
                return {"output": f"Screenshot saved: {save_path}", "error": False, "data": {"path": save_path}}
        except FileNotFoundError:
            pass
        try:
            # Try Python Pillow ImageGrab
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(save_path)
            return {"output": f"Screenshot saved: {save_path}", "error": False, "data": {"path": save_path}}
        except Exception as e:
            return {"output": f"Screenshot failed: {e}. Install scrot or use a display server.", "error": True, "data": {}}

    def _tool_clipboard_read(self) -> dict:
        try:
            result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                return {"output": result.stdout, "error": False, "data": {}}
        except FileNotFoundError:
            pass
        try:
            result = subprocess.run(["xsel", "--clipboard", "--output"], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                return {"output": result.stdout, "error": False, "data": {}}
        except FileNotFoundError:
            pass
        try:
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                return {"output": result.stdout, "error": False, "data": {}}
        except FileNotFoundError:
            pass
        return {"output": "No clipboard tool found. Install xclip or xsel.", "error": True, "data": {}}

    def _tool_clipboard_write(self, text: str) -> dict:
        try:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, check=True, timeout=3)
            return {"output": "Copied to clipboard", "error": False, "data": {}}
        except FileNotFoundError:
            pass
        try:
            subprocess.run(["xsel", "--clipboard", "--input"], input=text, text=True, check=True, timeout=3)
            return {"output": "Copied to clipboard", "error": False, "data": {}}
        except FileNotFoundError:
            pass
        try:
            subprocess.run(["pbcopy"], input=text, text=True, check=True, timeout=3)
            return {"output": "Copied to clipboard", "error": False, "data": {}}
        except FileNotFoundError:
            pass
        return {"output": "No clipboard tool found. Install xclip or xsel.", "error": True, "data": {}}

    def _tool_open_app(self, target: str) -> dict:
        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", target])
            elif platform.system() == "Windows":
                os.startfile(target)
            else:
                subprocess.Popen(["xdg-open", target])
            return {"output": f"Opened: {target}", "error": False, "data": {}}
        except Exception as e:
            return {"output": f"Failed to open: {e}", "error": True, "data": {}}

    def _tool_download_file(self, url: str, filename: str = "") -> dict:
        import aiohttp
        name = filename or url.split("/")[-1].split("?")[0] or "downloaded_file"
        save_path = self.config.workspace / name

        # Synchronous download using urllib
        from urllib.request import urlretrieve
        try:
            urlretrieve(url, str(save_path))
            size = save_path.stat().st_size
            return {"output": f"Downloaded: {save_path} ({size:,} bytes)", "error": False, "data": {"path": str(save_path)}}
        except Exception as e:
            return {"output": f"Download failed: {e}", "error": True, "data": {}}

    def _tool_notify(self, title: str, message: str) -> dict:
        try:
            subprocess.run(["notify-send", title, message], check=True, timeout=3)
            return {"output": f"Notification sent: {title}", "error": False, "data": {}}
        except FileNotFoundError:
            pass
        # Fallback: write to a file that a notifier could watch
        return {"output": f"No notify-send. Message: [{title}] {message}", "error": False, "data": {}}

    def _tool_media_capture(self, type: str, duration: int = 5) -> dict:
        if type == "photo":
            save_path = "/tmp/jarvis_webcam.jpg"
            try:
                # Try fswebcam (Linux)
                result = subprocess.run(["fswebcam", "--no-banner", "-r", "1280x720", save_path], capture_output=True, timeout=10)
                if result.returncode == 0:
                    return {"output": f"Photo captured: {save_path}", "error": False, "data": {"path": save_path}}
            except FileNotFoundError:
                pass
            return {"output": "No webcam tool found. Install fswebcam.", "error": True, "data": {}}

        elif type == "audio":
            save_path = "/tmp/jarvis_recording.wav"
            try:
                # Try arecord (Linux ALSA)
                result = subprocess.run(["arecord", "-f", "cd", "-d", str(duration), save_path], capture_output=True, timeout=duration + 5)
                if result.returncode == 0:
                    return {"output": f"Audio recorded: {save_path} ({duration}s)", "error": False, "data": {"path": save_path}}
            except FileNotFoundError:
                pass
            try:
                # Try sox
                result = subprocess.run(["rec", "-r", "16000", "-c", "1", save_path, "trim", "0", str(duration)], capture_output=True, timeout=duration + 5)
                if result.returncode == 0:
                    return {"output": f"Audio recorded: {save_path} ({duration}s)", "error": False, "data": {"path": save_path}}
            except FileNotFoundError:
                pass
            return {"output": "No audio recorder found. Install arecord or sox.", "error": True, "data": {}}

        return {"output": f"Unknown media type: {type}", "error": True, "data": {}}

    def _tool_environment_vars(self, action: str, key: str = "", value: str = "") -> dict:
        if action == "list":
            vars_list = [f"  {k}={v}" for k, v in sorted(os.environ.items()) if not k.startswith("_")]
            return {"output": "\n".join(vars_list[:100]), "error": False, "data": {}}
        elif action == "get":
            val = os.environ.get(key, "")
            return {"output": val or f"(not set)", "error": False, "data": {}}
        elif action == "set":
            os.environ[key] = value
            return {"output": f"Set {key}={value}", "error": False, "data": {}}
        return {"output": f"Unknown action: {action}", "error": True, "data": {}}
