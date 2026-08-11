# JARVIS — Self-Editing AI Agent

A CLI AI agent that can read, understand, and **edit its own source code**.

It's an agent that improves itself. You talk to it, it thinks, it can modify its own files, add new capabilities, fix its own bugs, and evolve.

## Install

```bash
cd jarvis-agent
pip install -e .
```

## Configure

Set your LLM provider:

```bash
# OpenAI
export JARVIS_LLM=openai/gpt-4o
export OPENAI_API_KEY=sk-...

# Anthropic
export JARVIS_LLM=anthropic/claude-sonnet-4-20250514
export ANTHROPIC_API_KEY=sk-ant-...

# Ollama (local, free)
ollama pull llama3
export JARVIS_LLM=ollama/llama3
```

## Run

```bash
jarvis
```

## What It Can Do

| Tool | Description |
|------|-------------|
| `read_file` | Read any file (including its own source) |
| `write_file` | Create or overwrite any file |
| `edit_file` | Search & replace in a file (surgical edits) |
| `list_files` | List directory contents |
| `run_code` | Execute Python code and see output |
| `shell` | Run shell commands |
| `self_inspect` | List its own source files + sizes |
| `git_diff` | See what it changed |
| `git_commit` | Commit its changes |
| `rollback` | Undo the last edit |

## Self-Editing

The agent knows its own codebase. You can say:

- *"Add a weather tool to yourself"*
- *"Your error handling in tools.py is weak, fix it"*
- *"Add unit tests for the LLM module"*
- *"Refactor your memory system to use SQLite"*

It will read its own files, plan the changes, show you a diff, and apply them (with your approval).

## Safety

- Every self-edit shows a **diff** before applying
- You must **approve** changes (or use `--auto-approve` at your own risk)
- **Rollback** undoes the last change
- **Git commits** after each approved edit so you have history
- The agent **cannot** edit files outside its own directory unless you allow it
