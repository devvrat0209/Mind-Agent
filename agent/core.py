"""The agent loop: perceive -> think -> act (tools) -> remember."""
from __future__ import annotations

import json
from typing import Any, Callable

from . import tools
from .config import CONFIG
from .llm import LLMClient, LLMError
from .memory import Memory
from .selfedit import list_source_files

SYSTEM_PROMPT = """\
You are a self-modifying agent. Your source code lives in the `agent/` Python
package and you have tools to read, patch, overwrite and roll back that code,
plus a SQLite-backed long-term memory that persists across restarts.

Operating principles:
1. Memory: before answering questions about the user or the project, consult
   memory (`recall` / `search_memory`). When you learn something durable -
   a preference, a decision, a fact about the project, a lesson from a failed
   edit - store it with `remember`. Keys are namespaced like `user.name`.
2. Self-modification: to change your own behaviour, first `read_own_code` the
   relevant file, then make the smallest possible `patch_own_code` edit, then
   run `self_check`. If the check fails, `rollback_own_code` immediately and
   explain what went wrong.
3. Honesty: never claim to have changed code or remembered something unless the
   corresponding tool call actually succeeded.
4. Code changes only take effect after the process restarts; say so when it
   matters.

Your source files: {files}

Long-term memory (most recently updated):
{memories}
"""


class Agent:
    def __init__(
        self,
        session: str = "default",
        memory: Memory | None = None,
        llm: LLMClient | None = None,
    ):
        CONFIG.ensure_dirs()
        self.session = session
        self.memory = memory or Memory(CONFIG.db_path)
        self.llm = llm or LLMClient()

    # ------------------------------------------------------------------ prompt
    def system_message(self) -> dict[str, str]:
        return {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                files=", ".join(list_source_files()),
                memories=self.memory.summary_block(),
            ),
        }

    def _conversation(self) -> list[dict[str, Any]]:
        return [self.system_message()] + self.memory.history(
            self.session, CONFIG.max_history_messages
        )

    # -------------------------------------------------------------------- loop
    def chat(
        self,
        user_input: str,
        on_event: Callable[[str, str], None] | None = None,
    ) -> str:
        """Run one turn to completion, returning the final assistant text."""
        emit = on_event or (lambda kind, text: None)
        self.memory.log_message(self.session, "user", user_input)

        messages = self._conversation()
        pending: list[dict[str, Any]] = []

        for step in range(CONFIG.max_steps):
            try:
                reply = self.llm.chat(messages + pending, tools=tools.schemas())
            except LLMError as exc:
                error = f"[llm error] {exc}"
                self.memory.log_message(self.session, "assistant", error)
                return error

            calls = reply.get("tool_calls") or []
            content = reply.get("content") or ""

            if not calls:
                self.memory.log_message(self.session, "assistant", content)
                return content

            if content:
                emit("thought", content)
            pending.append(
                {"role": "assistant", "content": content or None, "tool_calls": calls}
            )

            for tc in calls:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError as exc:
                    args, result = {}, f"error: malformed arguments: {exc}"
                else:
                    emit("tool", f"{name}({', '.join(f'{k}={v!r}'[:80] for k, v in args.items())})")
                    result = tools.call(name, args, self.memory)
                emit("result", result[:500])
                pending.append(
                    {"role": "tool", "tool_call_id": tc.get("id", name), "content": result}
                )
                self.memory.log_message(
                    self.session, "system", f"[tool:{name}] {result[:1000]}", tool=name
                )

        exhausted = f"[stopped after {CONFIG.max_steps} steps without a final answer]"
        self.memory.log_message(self.session, "assistant", exhausted)
        return exhausted

    def close(self) -> None:
        self.memory.close()
