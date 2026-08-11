"""LLM interface — multi-provider via litellm."""

import json
import litellm
from typing import Optional


def call_llm(
    model: str,
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> dict:
    """Call any LLM provider via litellm.

    Returns the raw litellm response.
    """
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = litellm.completion(**kwargs)
    return response


def extract_response(response: dict) -> str:
    """Get the text content from a response."""
    choice = response.choices[0]
    if choice.message.content:
        return choice.message.content
    return ""


def extract_tool_calls(response: dict) -> list[dict]:
    """Get tool calls from a response."""
    choice = response.choices[0]
    if choice.message.tool_calls:
        return [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": json.loads(tc.function.arguments),
            }
            for tc in choice.message.tool_calls
        ]
    return []


def count_tokens(messages: list[dict], model: str) -> int:
    """Count tokens in a message list."""
    try:
        return litellm.token_counter(model=model, messages=messages)
    except Exception:
        # Fallback: rough estimate
        total = sum(len(m.get("content", "") or "") for m in messages)
        return total // 4
