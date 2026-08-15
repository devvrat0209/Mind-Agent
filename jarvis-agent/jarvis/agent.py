"""Core agent loop — thinks, calls tools, self-edits."""

import json
from typing import Optional

from .config import Config
from .llm import call_llm, extract_response, extract_tool_calls, count_tokens
from .tools import ToolRegistry, ToolResult
from .memory import Memory


class Agent:
    """The JARVIS agent — reads, thinks, acts, self-edits."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.tools = ToolRegistry(self.config)
        self.memory = Memory(self.config)
        self.turn_count = 0

    def chat(self, user_input: str) -> str:
        """Process a user message — may involve multiple tool calls."""
        self.memory.add("user", user_input)
        self.turn_count += 1

        # Agent loop: think -> act -> observe -> think again
        all_output = []
        remaining_calls = self.config.max_tool_calls_per_turn

        while remaining_calls > 0:
            # Call LLM
            try:
                response = call_llm(
                    model=self.config.llm_model,
                    messages=self.memory.get_messages(),
                    tools=self.tools.tool_schemas,
                    temperature=self.config.llm_temperature,
                    max_tokens=self.config.llm_max_tokens,
                    **self.config.llm_kwargs(),
                )
            except Exception as e:
                error_msg = f"LLM error: {e}"
                all_output.append(f"⚠ {error_msg}")
                self.memory.add("assistant", error_msg)
                break

            # Extract text response
            text = extract_response(response)
            tool_calls = extract_tool_calls(response)

            # If there's text, add it
            if text:
                all_output.append(text)
                self.memory.add("assistant", text)

            # If no tool calls, we're done
            if not tool_calls:
                break

            # Process tool calls
            remaining_calls -= len(tool_calls)
            tool_messages = []

            for tc in tool_calls:
                name = tc["name"]
                args = tc["arguments"]

                # Execute tool
                result: ToolResult = self.tools.call(name, args)

                # Format for display
                if result.error:
                    display = f"❌ {name}({json.dumps(args, ensure_ascii=False)[:100]}): {result.output[:300]}"
                else:
                    display = f"✓ {name}({json.dumps(args, ensure_ascii=False)[:100]}): {result.output[:500]}"

                all_output.append(display)

                # Add to memory as tool call + result
                self.memory.messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args, ensure_ascii=False),
                        },
                    }],
                })
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result.output[:2000],  # truncate long outputs
                })

            # Add tool results to memory
            for tm in tool_messages:
                self.memory.messages.append(tm)

        return "\n\n".join(all_output)

    def reset(self):
        """Reset conversation."""
        self.memory.clear()
        self.turn_count = 0
