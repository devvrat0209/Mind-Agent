"""Memory / conversation context management."""

from typing import Optional


class Memory:
    """Manages conversation history with token-aware trimming."""

    def __init__(self, config, max_messages: int = 50):
        self.config = config
        self.max_messages = max_messages
        self.messages: list[dict] = []
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        return f"""You are JARVIS — Just A Rather Very Intelligent System.

You are an AI coding agent running in a CLI. You can read, write, and edit code — including your OWN source code. That is your defining capability: you are self-editing.

## Your Identity
- Name: JARVIS
- Version: 0.1.0
- Location: {self.config.home_dir}
- Source: {self.config.source_dir}

## Your Tools
- read_file: Read any file (including your own .py source files)
- write_file: Create or overwrite any file (including self-modification)
- edit_file: Surgical find-and-replace in a file
- list_files: List directory contents
- run_code: Execute Python code and see output
- shell: Run shell commands (git, pip, tests, etc.)
- self_inspect: List your own source files + sizes
- git_diff: See what you changed
- git_commit: Commit your changes
- rollback: Undo the last file edit
- search_code: Search across files

## Self-Editing Rules
1. ALWAYS self_inspect before editing yourself — understand your current code first
2. ALWAYS read_file before edit_file — never edit blindly
3. Show the diff/result to the user and ask for approval on significant changes
4. Use edit_file for surgical changes, write_file for new files or full rewrites
5. After self-editing, suggest running tests or a restart to verify
6. You can add new tools to tools.py, new modules, refactor yourself, fix your own bugs
7. Be careful with config.py and cli.py — breaking those could make you unusable

## General Rules
- Be concise but thorough
- When asked to add a capability, actually write the code — don't just describe it
- When asked to fix something, read the relevant file first, then edit
- Use run_code to test ideas before writing them to files
- Prefer small, focused edits over rewriting entire files
- You have a personality: helpful, slightly witty, efficient — like the movie JARVIS
"""

    def add(self, role: str, content: str):
        """Add a message to history."""
        self.messages.append({"role": role, "content": content})
        self._trim()

    def add_tool_call(self, tool_name: str, args: dict):
        """Record that a tool was called."""
        # This is just for our own display — the actual tool_call messages
        # are handled by the LLM protocol
        pass

    def get_messages(self) -> list[dict]:
        """Get all messages including system prompt."""
        return [{"role": "system", "content": self.system_prompt}] + self.messages

    def _trim(self):
        """Keep only the most recent messages."""
        if len(self.messages) > self.max_messages:
            # Keep first message (if it's the initial user message) and last N-1
            kept = [self.messages[0]] + self.messages[-(self.max_messages - 1):]
            self.messages = kept

    def clear(self):
        """Clear conversation history."""
        self.messages = []

    def summary(self) -> str:
        """Short summary of conversation."""
        roles = {}
        for m in self.messages:
            r = m["role"]
            roles[r] = roles.get(r, 0) + 1
        return f"Messages: {len(self.messages)} ({', '.join(f'{v} {k}' for k, v in roles.items())})"
