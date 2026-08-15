"""REST API for JARVIS.

Endpoints
    GET  /                     service banner
    GET  /health               liveness + dependency/device health
    GET  /device               full device + GPU detection
    GET  /deps                 dependency report
    POST /deps/install         install missing dependencies
    GET  /nim/status           NVIDIA NIM connectivity
    GET  /nim/models           models available on the NIM endpoint
    POST /nim/chat             direct NIM chat completion (bypasses the agent)
    POST /nim/test             smoke-test the configured NIM model
    GET  /telegram/status      Telegram bot token / webhook status
    POST /telegram/send        send a message through the bot
    POST /chat                 talk to the JARVIS agent
    POST /reset                clear agent memory
    GET  /config               non-secret config view

Auth: if JARVIS_API_KEY is set, every route except / and /health requires
`Authorization: Bearer <key>`.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import deps as depmod
from . import nim as nimmod
from .platform_detect import device

START_TIME = time.time()


# ── models ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="Message for the agent")
    reset: bool = Field(False, description="Clear history before this message")


class ChatResponse(BaseModel):
    response: str
    model: str
    elapsed_ms: int


class NIMChatRequest(BaseModel):
    message: str
    model: Optional[str] = Field(None, description="Override the configured NIM model")
    temperature: float = 0.3
    max_tokens: int = 1024
    system: Optional[str] = None


class InstallRequest(BaseModel):
    groups: list[str] = Field(default_factory=lambda: list(depmod.GROUPS))
    include_optional: bool = False
    dry_run: bool = False


class TelegramSendRequest(BaseModel):
    chat_id: int
    text: str
    parse_mode: Optional[str] = "Markdown"


# ── app ────────────────────────────────────────────────────────────────

def _api_key() -> str:
    return os.getenv("JARVIS_API_KEY", "").strip()


async def require_auth(authorization: Optional[str] = Header(None)) -> None:
    key = _api_key()
    if not key:
        return                                  # auth disabled
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    import hmac
    if not hmac.compare_digest(authorization[7:].strip(), key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")


def create_app() -> FastAPI:
    app = FastAPI(
        title="JARVIS API",
        description="Device-aware agent API with NVIDIA NIM and Telegram integration",
        version="0.4.0",
    )

    origins = [o for o in os.getenv("JARVIS_API_CORS", "*").split(",") if o]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _agent: dict[str, Any] = {}

    def agent():
        """Lazy — importing the agent pulls in litellm, which is slow."""
        if "a" not in _agent:
            from .agent import Agent
            from .config import Config
            _agent["a"] = Agent(Config())
        return _agent["a"]

    auth = [Depends(require_auth)]

    # ── meta ───────────────────────────────────────────────────────────

    @app.get("/", tags=["meta"])
    def root():
        return {
            "service": "JARVIS",
            "version": "0.4.0",
            "uptime_s": int(time.time() - START_TIME),
            "auth_required": bool(_api_key()),
            "docs": "/docs",
        }

    @app.get("/health", tags=["meta"])
    def health():
        statuses = depmod.check_all()
        gaps = depmod.missing(statuses)
        dev = device()
        cfg = nimmod.NIMConfig.from_env()
        return {
            "status": "ok" if not gaps else "degraded",
            "uptime_s": int(time.time() - START_TIME),
            "device": {
                "os": dev.os_name,
                "arch": dev.arch,
                "accelerator": dev.accelerator,
                "gpu": dev.gpu.name or None,
            },
            "dependencies": {
                "satisfied": len(statuses) - len(gaps),
                "total": len(statuses),
                "missing": [g.req.dist for g in gaps],
            },
            "integrations": {
                "nvidia_nim": cfg.configured,
                "telegram": bool(os.getenv("JARVIS_TELEGRAM_TOKEN")),
            },
        }

    @app.get("/device", tags=["system"], dependencies=auth)
    def device_info():
        return device(refresh=True).to_dict()

    @app.get("/deps", tags=["system"], dependencies=auth)
    def dependency_report():
        return depmod.report()

    @app.post("/deps/install", tags=["system"], dependencies=auth)
    def install_deps(req: InstallRequest):
        logs: list[str] = []
        statuses, results = depmod.ensure(
            groups=req.groups,
            auto=True,
            include_optional=req.include_optional,
            dry_run=req.dry_run,
            log=logs.append,
        )
        return {
            "installed": [{"spec": r.spec, "ok": r.ok} for r in results],
            "failed": [{"spec": r.spec, "error": r.output[-800:]} for r in results if not r.ok],
            "still_missing": [s.req.dist for s in depmod.missing(statuses)],
            "logs": logs,
        }

    # ── nvidia nim ─────────────────────────────────────────────────────

    @app.get("/nim/status", tags=["nvidia-nim"], dependencies=auth)
    def nim_status():
        cfg = nimmod.NIMConfig.from_env()
        check = nimmod.validate_key(cfg)
        dev = device()
        return {
            "configured": cfg.configured,
            "mode": cfg.mode,
            "api_base": cfg.api_base,
            "model": cfg.model,
            "litellm_model": cfg.litellm_model,
            "api_key": cfg.masked_key(),
            "reachable": check.ok,
            "message": check.message,
            "latency_ms": check.latency_ms,
            "model_count": len(check.models),
            "gpu": {
                "vendor": dev.gpu.vendor,
                "name": dev.gpu.name or None,
                "cuda": dev.gpu.cuda_version or None,
                "can_self_host": nimmod.gpu_ready_for_local()[0],
            },
        }

    @app.get("/nim/models", tags=["nvidia-nim"], dependencies=auth)
    def nim_models():
        cfg = nimmod.NIMConfig.from_env()
        if not cfg.configured:
            raise HTTPException(400, "NVIDIA NIM is not configured — run `jarvis setup nim`")
        check = nimmod.validate_key(cfg)
        if not check.ok:
            raise HTTPException(502, check.message)
        return {
            "current": cfg.model,
            "available": sorted(check.models),
            "recommended": [
                {"group": g, "id": m, "description": d} for g, m, d in nimmod.flat_catalog()
            ],
        }

    @app.post("/nim/chat", tags=["nvidia-nim"], dependencies=auth)
    def nim_chat(req: NIMChatRequest):
        cfg = nimmod.NIMConfig.from_env()
        if not cfg.configured:
            raise HTTPException(400, "NVIDIA NIM is not configured")
        if req.model:
            cfg.model = req.model
        cfg.apply_to_env()

        messages = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        messages.append({"role": "user", "content": req.message})

        t0 = time.time()
        try:
            import litellm
            resp = litellm.completion(
                model=cfg.litellm_model,
                messages=messages,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                api_base=cfg.api_base,
                api_key=cfg.api_key or "not-needed",
            )
        except Exception as e:
            raise HTTPException(502, f"NIM request failed: {e}")

        return {
            "response": resp.choices[0].message.content or "",
            "model": cfg.model,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "usage": getattr(resp, "usage", None) and dict(resp.usage),
        }

    @app.post("/nim/test", tags=["nvidia-nim"], dependencies=auth)
    def nim_test():
        cfg = nimmod.NIMConfig.from_env()
        key_check = nimmod.validate_key(cfg)
        comp = nimmod.test_completion(cfg) if key_check.ok else None
        return {
            "endpoint": {"ok": key_check.ok, "message": key_check.message,
                         "latency_ms": key_check.latency_ms},
            "completion": ({"ok": comp.ok, "message": comp.message,
                            "latency_ms": comp.latency_ms} if comp else None),
        }

    # ── telegram ───────────────────────────────────────────────────────

    @app.get("/telegram/status", tags=["telegram"], dependencies=auth)
    def telegram_status():
        from .wizard import verify_telegram_token
        token = os.getenv("JARVIS_TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            return {"configured": False, "message": "No token — run `jarvis setup telegram`"}
        ok, info = verify_telegram_token(token)
        raw = os.getenv("JARVIS_TELEGRAM_USERS", "")
        return {
            "configured": True,
            "valid": ok,
            "username": info if ok else None,
            "error": None if ok else info,
            "authorized_users": [u.strip() for u in raw.split(",") if u.strip()] or "anyone",
        }

    @app.post("/telegram/send", tags=["telegram"], dependencies=auth)
    def telegram_send(req: TelegramSendRequest):
        import json
        import urllib.request

        token = os.getenv("JARVIS_TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise HTTPException(400, "Telegram is not configured")
        payload = json.dumps({
            "chat_id": req.chat_id, "text": req.text, "parse_mode": req.parse_mode
        }).encode()
        r = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload, headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(r, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            raise HTTPException(502, f"Telegram send failed: {e}")

    # ── agent ──────────────────────────────────────────────────────────

    @app.post("/chat", response_model=ChatResponse, tags=["agent"], dependencies=auth)
    def chat(req: ChatRequest):
        a = agent()
        if req.reset:
            a.reset()
        t0 = time.time()
        try:
            out = a.chat(req.message)
        except Exception as e:
            raise HTTPException(500, f"Agent error: {e}")
        return ChatResponse(
            response=out,
            model=a.config.llm_model,
            elapsed_ms=int((time.time() - t0) * 1000),
        )

    @app.post("/reset", tags=["agent"], dependencies=auth)
    def reset():
        agent().reset()
        return {"status": "reset"}

    # ── heartbeat ──────────────────────────────────────────────────────

    @app.get("/heartbeat", tags=["heartbeat"], dependencies=auth)
    def heartbeat_status():
        from .heartbeat import get_heartbeat, read_persisted_state
        hb = get_heartbeat()
        if hb.running:
            return {"source": "live", **hb.status()}
        persisted = read_persisted_state()
        if persisted:
            return {"source": "persisted", **persisted}
        return {"source": "none", "running": False, "tasks": []}

    @app.post("/heartbeat/start", tags=["heartbeat"], dependencies=auth)
    def heartbeat_start():
        from .heartbeat import get_heartbeat
        hb = get_heartbeat()
        if hb.running:
            return {"status": "already running"}
        hb.start()
        return {"status": "started", "tasks": list(hb.tasks)}

    @app.post("/heartbeat/stop", tags=["heartbeat"], dependencies=auth)
    def heartbeat_stop():
        from .heartbeat import get_heartbeat
        hb = get_heartbeat()
        if not hb.running:
            return {"status": "not running"}
        hb.stop()
        return {"status": "stopped"}

    @app.post("/heartbeat/run/{task_name}", tags=["heartbeat"], dependencies=auth)
    def heartbeat_run(task_name: str):
        from .heartbeat import get_heartbeat
        hb = get_heartbeat()
        if task_name not in hb.tasks:
            raise HTTPException(404, f"Unknown task '{task_name}'. "
                                     f"Tasks: {', '.join(hb.tasks)}")
        result = hb.run_task(task_name)
        return {"task": task_name, "ok": result.ok, "summary": result.summary,
                "alert": result.alert or None}

    @app.get("/config", tags=["meta"], dependencies=auth)
    def config_view():
        cfg = nimmod.NIMConfig.from_env()
        return {
            "llm_model": os.getenv("JARVIS_LLM", "(unset)"),
            "nim": {"mode": cfg.mode, "model": cfg.model,
                    "api_base": cfg.api_base, "api_key": cfg.masked_key()},
            "telegram": {"configured": bool(os.getenv("JARVIS_TELEGRAM_TOKEN")),
                         "restricted": bool(os.getenv("JARVIS_TELEGRAM_USERS"))},
            "api": {"host": os.getenv("JARVIS_API_HOST", "127.0.0.1"),
                    "port": int(os.getenv("JARVIS_API_PORT", "8088")),
                    "auth": bool(_api_key())},
            "workspace": os.getcwd(),
        }

    return app


def serve(host: Optional[str] = None, port: Optional[int] = None, reload: bool = False) -> None:
    """Start the API server (heartbeat daemon runs alongside unless disabled)."""
    import uvicorn

    from .heartbeat import get_heartbeat, heartbeat_enabled
    if heartbeat_enabled():
        get_heartbeat().start()      # idempotent — no-op if already running

    host = host or os.getenv("JARVIS_API_HOST", "127.0.0.1")
    port = int(port or os.getenv("JARVIS_API_PORT", "8088"))
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


def __getattr__(name: str):
    """Lets `uvicorn jarvis.api:app` work without building the app at import time."""
    if name == "app":
        return create_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
