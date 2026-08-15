"""NVIDIA NIM integration.

Two deployment shapes are supported:

  hosted  — NVIDIA's cloud endpoint at https://integrate.api.nvidia.com/v1
            (get an `nvapi-...` key from https://build.nvidia.com)
  local   — a self-hosted NIM container, typically http://localhost:8000/v1
            (needs an NVIDIA GPU + the NGC container)

Both speak the OpenAI-compatible protocol, so the agent routes them through
LiteLLM with the `nvidia_nim/` prefix.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

HOSTED_BASE = "https://integrate.api.nvidia.com/v1"
LOCAL_BASE = "http://localhost:8000/v1"

# Popular build.nvidia.com models, grouped for the wizard.
CATALOG: dict[str, list[tuple[str, str]]] = {
    "General": [
        ("meta/llama-3.3-70b-instruct", "Llama 3.3 70B — strong all-rounder, tool calling"),
        ("meta/llama-3.1-405b-instruct", "Llama 3.1 405B — highest quality, slower"),
        ("meta/llama-3.1-8b-instruct", "Llama 3.1 8B — fastest, cheapest"),
        ("mistralai/mixtral-8x22b-instruct-v0.1", "Mixtral 8x22B — solid MoE"),
        ("microsoft/phi-3-medium-128k-instruct", "Phi-3 Medium — 128k context"),
    ],
    "Reasoning & code": [
        ("nvidia/llama-3.1-nemotron-70b-instruct", "Nemotron 70B — NVIDIA-tuned, great at reasoning"),
        ("deepseek-ai/deepseek-r1", "DeepSeek R1 — deep reasoning"),
        ("qwen/qwen2.5-coder-32b-instruct", "Qwen2.5 Coder 32B — code specialist"),
    ],
    "Vision": [
        ("meta/llama-3.2-90b-vision-instruct", "Llama 3.2 90B Vision — images + text"),
        ("microsoft/phi-3.5-vision-instruct", "Phi-3.5 Vision — light multimodal"),
    ],
}

DEFAULT_MODEL = "meta/llama-3.3-70b-instruct"

# Env var names
ENV_KEY = "NVIDIA_NIM_API_KEY"
ENV_BASE = "NVIDIA_NIM_API_BASE"
ENV_MODEL = "JARVIS_NIM_MODEL"
ENV_MODE = "JARVIS_NIM_MODE"          # hosted | local


def flat_catalog() -> list[tuple[str, str, str]]:
    """[(group, model_id, description), ...]"""
    return [(g, m, d) for g, items in CATALOG.items() for m, d in items]


# ── config ─────────────────────────────────────────────────────────────

@dataclass
class NIMConfig:
    api_key: str = ""
    api_base: str = HOSTED_BASE
    model: str = DEFAULT_MODEL
    mode: str = "hosted"              # hosted | local
    timeout: int = 60

    @classmethod
    def from_env(cls) -> "NIMConfig":
        mode = os.getenv(ENV_MODE, "hosted").strip().lower()
        base = os.getenv(ENV_BASE, "").strip()
        if not base:
            base = LOCAL_BASE if mode == "local" else HOSTED_BASE
        return cls(
            api_key=(os.getenv(ENV_KEY) or os.getenv("NVIDIA_API_KEY") or "").strip(),
            api_base=base.rstrip("/"),
            model=os.getenv(ENV_MODEL, DEFAULT_MODEL).strip(),
            mode=mode,
        )

    @property
    def configured(self) -> bool:
        # local NIM containers usually need no key
        return bool(self.api_key) or self.mode == "local"

    @property
    def litellm_model(self) -> str:
        """Model string the agent hands to LiteLLM."""
        m = self.model
        return m if m.startswith("nvidia_nim/") else f"nvidia_nim/{m}"

    def apply_to_env(self) -> None:
        """Export so LiteLLM picks the endpoint up."""
        if self.api_key:
            os.environ[ENV_KEY] = self.api_key
            os.environ.setdefault("NVIDIA_API_KEY", self.api_key)
        os.environ[ENV_BASE] = self.api_base
        os.environ[ENV_MODEL] = self.model
        os.environ[ENV_MODE] = self.mode

    def masked_key(self) -> str:
        k = self.api_key
        if not k:
            return "(none)"
        return f"{k[:8]}…{k[-4:]}" if len(k) > 14 else "…"


# ── HTTP (stdlib, so this works before httpx is installed) ─────────────

def _request(url: str, key: str, payload: Optional[dict], timeout: int) -> tuple[int, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, body
    except urllib.error.URLError as e:
        return 0, str(e.reason)
    except Exception as e:  # timeouts, TLS, ...
        return 0, str(e)


@dataclass
class NIMCheck:
    ok: bool
    status: int = 0
    message: str = ""
    models: list[str] = None
    latency_ms: int = 0

    def __post_init__(self):
        if self.models is None:
            self.models = []


def validate_key(cfg: NIMConfig) -> NIMCheck:
    """Hit /models — cheapest way to prove the key and endpoint work."""
    import time

    if cfg.mode == "hosted" and not cfg.api_key:
        return NIMCheck(False, 0, "No API key set. Get one at https://build.nvidia.com")
    if cfg.mode == "hosted" and not cfg.api_key.startswith("nvapi-"):
        # warn but still try — NVIDIA could change the prefix
        pass

    t0 = time.time()
    status, body = _request(f"{cfg.api_base}/models", cfg.api_key, None, cfg.timeout)
    dt = int((time.time() - t0) * 1000)

    if status == 200:
        models = []
        if isinstance(body, dict):
            models = [m.get("id", "") for m in body.get("data", []) if isinstance(m, dict)]
        return NIMCheck(True, status, f"Connected — {len(models)} models available", models, dt)
    if status == 401:
        return NIMCheck(False, 401, "Unauthorized — the API key was rejected", latency_ms=dt)
    if status == 403:
        return NIMCheck(False, 403, "Forbidden — key lacks access to this endpoint", latency_ms=dt)
    if status == 0:
        hint = ""
        if cfg.mode == "local":
            hint = " Is the NIM container running? `docker ps`"
        return NIMCheck(False, 0, f"Cannot reach {cfg.api_base}: {body}.{hint}", latency_ms=dt)
    return NIMCheck(False, status, f"HTTP {status}: {str(body)[:300]}", latency_ms=dt)


def test_completion(cfg: NIMConfig, prompt: str = "Reply with exactly: OK") -> NIMCheck:
    """End-to-end smoke test against the configured model."""
    import time

    payload = {
        "model": cfg.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 16,
        "temperature": 0,
    }
    t0 = time.time()
    status, body = _request(f"{cfg.api_base}/chat/completions", cfg.api_key, payload, cfg.timeout)
    dt = int((time.time() - t0) * 1000)

    if status == 200 and isinstance(body, dict):
        try:
            text = body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            text = "(empty response)"
        return NIMCheck(True, 200, f"Model replied: {text[:120]}", latency_ms=dt)
    if status == 404:
        return NIMCheck(False, 404, f"Model '{cfg.model}' not found on this endpoint", latency_ms=dt)
    return NIMCheck(False, status, f"HTTP {status}: {str(body)[:300]}", latency_ms=dt)


def list_models(cfg: NIMConfig) -> list[str]:
    check = validate_key(cfg)
    return sorted(check.models)


# ── local container helper ─────────────────────────────────────────────

def local_container_command(model: str = "meta/llama-3.1-8b-instruct",
                            port: int = 8000,
                            ngc_key_var: str = "NGC_API_KEY") -> str:
    """The `docker run` line for self-hosting a NIM. Requires an NVIDIA GPU."""
    return (
        f"docker run --rm --gpus all --shm-size=16GB \\\n"
        f"  -e NGC_API_KEY=${ngc_key_var} \\\n"
        f"  -v ~/.cache/nim:/opt/nim/.cache \\\n"
        f"  -u $(id -u) -p {port}:8000 \\\n"
        f"  nvcr.io/nim/{model}:latest"
    )


def local_readiness(base: str = LOCAL_BASE, timeout: int = 5) -> NIMCheck:
    """Check whether a local NIM container is up."""
    root = base.rstrip("/").removesuffix("/v1")
    status, body = _request(f"{root}/v1/health/ready", "", None, timeout)
    if status == 200:
        return NIMCheck(True, 200, "Local NIM container is ready")
    status2, _ = _request(f"{base.rstrip('/')}/models", "", None, timeout)
    if status2 == 200:
        return NIMCheck(True, 200, "Local NIM responding on /models")
    return NIMCheck(False, status, f"No local NIM at {base}")


def gpu_ready_for_local() -> tuple[bool, str]:
    """Can this machine actually host a NIM container?"""
    from .platform_detect import device

    dev = device()
    if dev.gpu.vendor != "nvidia":
        return False, "Self-hosting a NIM needs an NVIDIA GPU — use the hosted endpoint instead."
    if dev.gpu.memory_mb and dev.gpu.memory_mb < 16000:
        return False, (f"GPU has {dev.gpu.memory_mb} MB; most NIMs want ≥16 GB. "
                       "Small models may still fit.")
    import shutil
    if not shutil.which("docker"):
        return False, "Docker is not installed — required to run a NIM container."
    return True, f"{dev.gpu.name} ({dev.gpu.memory_mb} MB) — ready for a local NIM."
