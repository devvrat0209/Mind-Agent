"""Self-modification machinery.

The agent can read and rewrite the files that define it. Every write:

1. is restricted to the agent's own source tree (no escaping via ``..``),
2. snapshots the previous content into a timestamped backup,
3. is syntax-checked with ``compile()`` when it is a ``.py`` file,
4. is automatically rolled back if the check fails,
5. is recorded in the journal so the change history is durable.
"""
from __future__ import annotations

import difflib
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from .config import AGENT_ROOT, CONFIG


class SelfEditError(Exception):
    pass


@dataclass
class EditResult:
    path: str
    ok: bool
    message: str
    diff: str = ""
    backup: str | None = None


def _resolve(relative_path: str) -> Path:
    """Resolve a path inside the agent source tree, refusing escapes."""
    base = AGENT_ROOT
    candidate = (base / relative_path).resolve()
    if candidate != base and base not in candidate.parents:
        raise SelfEditError(
            f"refusing to touch {relative_path!r}: outside the agent source tree ({base})"
        )
    return candidate


def list_source_files() -> list[str]:
    return sorted(
        str(p.relative_to(AGENT_ROOT))
        for p in AGENT_ROOT.rglob("*.py")
        if "__pycache__" not in p.parts
    )


def read_source(relative_path: str, with_line_numbers: bool = True) -> str:
    path = _resolve(relative_path)
    if not path.is_file():
        raise SelfEditError(f"no such file: {relative_path}")
    text = path.read_text(encoding="utf-8")
    if not with_line_numbers:
        return text
    width = len(str(text.count("\n") + 1))
    return "\n".join(
        f"{i:>{width}} | {line}" for i, line in enumerate(text.splitlines(), start=1)
    )


def _backup(path: Path) -> Path:
    CONFIG.ensure_dirs()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = CONFIG.backup_dir / f"{path.name}.{stamp}.{int(time.time()*1000)%1000:03d}.bak"
    shutil.copy2(path, target)
    return target


def _validate(path: Path, text: str) -> None:
    if path.suffix == ".py":
        compile(text, str(path), "exec")  # raises SyntaxError


def write_source(relative_path: str, content: str) -> EditResult:
    """Overwrite (or create) a file in the agent's own tree, with rollback."""
    if not CONFIG.allow_self_edit:
        return EditResult(relative_path, False, "self-editing is disabled (AGENT_ALLOW_SELF_EDIT=0)")

    path = _resolve(relative_path)
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    backup = str(_backup(path)) if path.is_file() else None

    try:
        _validate(path, content)
    except SyntaxError as exc:
        return EditResult(
            relative_path, False, f"rejected: syntax error at line {exc.lineno}: {exc.msg}",
            backup=backup,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    diff = "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        )
    )
    return EditResult(relative_path, True, "written", diff=diff, backup=backup)


def patch_source(relative_path: str, find: str, replace: str, count: int = 1) -> EditResult:
    """Exact-string replacement inside one of the agent's files."""
    path = _resolve(relative_path)
    if not path.is_file():
        return EditResult(relative_path, False, f"no such file: {relative_path}")
    old = path.read_text(encoding="utf-8")
    occurrences = old.count(find)
    if occurrences == 0:
        return EditResult(relative_path, False, "the `find` text was not found verbatim")
    if count == 1 and occurrences > 1:
        return EditResult(
            relative_path, False,
            f"`find` matches {occurrences} times; make it unique or pass count=-1",
        )
    new = old.replace(find, replace) if count < 0 else old.replace(find, replace, count)
    return write_source(relative_path, new)


def rollback(relative_path: str) -> EditResult:
    """Restore the most recent backup of a file."""
    path = _resolve(relative_path)
    CONFIG.ensure_dirs()
    candidates = sorted(CONFIG.backup_dir.glob(f"{path.name}.*.bak"))
    if not candidates:
        return EditResult(relative_path, False, "no backups available")
    latest = candidates[-1]
    shutil.copy2(latest, path)
    return EditResult(relative_path, True, f"restored from {latest.name}", backup=str(latest))


def list_backups(relative_path: str | None = None) -> list[str]:
    CONFIG.ensure_dirs()
    pattern = f"{Path(relative_path).name}.*.bak" if relative_path else "*.bak"
    return sorted(p.name for p in CONFIG.backup_dir.glob(pattern))
