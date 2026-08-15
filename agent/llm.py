"""Tiny OpenAI-compatible chat client built on the standard library.

No third-party dependencies: works against OpenAI, OpenRouter, Groq, Together,
Ollama (``/v1``), vLLM, LM Studio - anything exposing ``/chat/completions``.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .config import CONFIG


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        self.base_url = (base_url or CONFIG.base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else CONFIG.api_key
        self.model = model or CONFIG.model
        self.timeout = timeout or CONFIG.request_timeout

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": CONFIG.temperature if temperature is None else temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network
            detail = exc.read().decode("utf-8", "replace")[:800]
            raise LLMError(f"HTTP {exc.code} from {self.base_url}: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network
            raise LLMError(f"cannot reach {self.base_url}: {exc.reason}") from exc

        choices = body.get("choices") or []
        if not choices:
            raise LLMError(f"no choices in response: {json.dumps(body)[:400]}")
        return choices[0]["message"]
