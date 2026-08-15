# my-agent

A self-editing AI agent with persistent memory. It can read its own source
code, patch it, verify the result, and roll back — and it remembers what it
learns across restarts in a SQLite database.

**Zero dependencies.** Pure Python 3.9+ standard library. Works with OpenAI,
OpenRouter, Groq, Together, Ollama, vLLM — anything speaking the
OpenAI `/chat/completions` API.

## Quick start

```bash
# See it work with no API key at all (scripted model, real agent code):
python3 demo.py

# Real usage:
export AGENT_API_KEY=sk-...
export AGENT_MODEL=gpt-4o-mini
python3 -m agent
```

Local model instead:

```bash
export AGENT_BASE_URL=http://localhost:11434/v1
export AGENT_MODEL=qwen2.5-coder:7b
export AGENT_API_KEY=ollama
python3 -m agent
```

## What it can do

```
you › remember that I deploy on Fridays and prefer pytest over unittest
→ remember(key='pref.deploy_day', value='Friday')
→ remember(key='pref.test_framework', value='pytest')
agent › Stored both.

you › add a tool that tells the current time
→ read_own_code(path='tools.py')
→ patch_own_code(path='tools.py', find='# ---- shell', replace='@tool(...)...')
→ self_check()
agent › Added `current_time` to tools.py and verified the package still
        imports. Restart me and the tool will be live.
```

Restart the process and it still knows you deploy on Fridays.

## How it works

```
agent/
├── core.py      the loop: prompt → model → tool calls → observations → answer
├── memory.py    SQLite: facts (durable KV) · episodes (transcript) · journal (audit)
├── selfedit.py  sandboxed read/patch/write/rollback of the agent's own files
├── tools.py     tool registry; @tool decorator generates the JSON schemas
├── llm.py       ~70-line OpenAI-compatible client over urllib
├── config.py    env-driven configuration and safety switches
└── cli.py       REPL with slash commands
```

**Memory** is three tables in `.agent_state/memory.sqlite3`:

| table | purpose |
| --- | --- |
| `facts` | durable key/value knowledge the agent chooses to keep; injected into every system prompt |
| `episodes` | full conversation transcript, per named session (`--session work`) |
| `journal` | append-only audit log of every self-modification, success or failure |

**Self-editing** goes through `selfedit.py`, which enforces four guarantees on
every write:

1. **Sandboxed** — paths are resolved and rejected if they escape `agent/`.
2. **Backed up** — the previous content is snapshotted to `.agent_state/backups/`.
3. **Syntax-checked** — `.py` writes must `compile()`; a bad edit never reaches disk.
4. **Reversible** — `rollback_own_code` restores the latest backup; `self_check`
   import-checks the package in a subprocess.

Code edits apply on the **next restart** (Python won't safely hot-swap a running
module), and the agent is instructed to say so rather than pretend otherwise.

## Tools available to the model

| tool | description |
| --- | --- |
| `remember` / `recall` / `search_memory` / `forget` | long-term memory |
| `list_own_code` / `read_own_code` | introspect its own source |
| `patch_own_code` / `write_own_code` | modify itself (guarded) |
| `rollback_own_code` / `change_history` | undo and audit |
| `self_check` | verify the package still imports |
| `run_shell` | run tests, git, grep in the project dir |

Adding a tool is one decorated function in `tools.py` — the schema is derived
automatically:

```python
@tool("Return the current time.", tz=_s("Optional timezone", optional=True))
def current_time(tz: str = "UTC", *, memory: Memory) -> str:
    return datetime.now(ZoneInfo(tz)).isoformat()
```

## REPL commands

`/help` `/tools` `/memory` `/history` `/journal` `/files` `/read <file>`
`/reset` `/quit`

## Configuration

All via environment variables (see `.env.example`):

| variable | default | meaning |
| --- | --- | --- |
| `AGENT_API_KEY` | — | API key |
| `AGENT_BASE_URL` | `https://api.openai.com/v1` | provider endpoint |
| `AGENT_MODEL` | `gpt-4o-mini` | model name |
| `AGENT_MAX_STEPS` | `12` | tool-calls per turn before stopping |
| `AGENT_STATE_DIR` | `.agent_state` | where memory + backups live |
| `AGENT_ALLOW_SELF_EDIT` | `1` | set `0` to make the agent read-only |
| `AGENT_ALLOW_SHELL` | `1` | set `0` to disable shell access |

## Tests

```bash
python3 -m unittest discover -s tests -v   # 18 tests, no network needed
```

They cover memory persistence across reopen, path-escape rejection, syntax-error
rejection, ambiguous-patch refusal, rollback, and the full tool-calling loop via
a fake LLM.

## Safety notes

This agent runs shell commands and rewrites its own source. Run it in a
container or VM you don't mind it breaking, keep `.agent_state/` and the repo
under version control, and set `AGENT_ALLOW_SELF_EDIT=0` / `AGENT_ALLOW_SHELL=0`
if you just want the memory layer.
