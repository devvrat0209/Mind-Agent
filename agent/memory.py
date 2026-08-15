"""Persistent memory backed by SQLite.

Three layers:

* ``facts``      - durable key/value knowledge the agent chooses to remember.
* ``episodes``   - the full conversation transcript, per session.
* ``journal``    - append-only log of self-modifications and notable events.

The database survives restarts, so the agent genuinely accumulates state.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    hits        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS episodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session     TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    extra       TEXT NOT NULL DEFAULT '{}',
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session, id);

CREATE TABLE IF NOT EXISTS journal (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL,
    summary     TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL
);
"""


@dataclass
class Fact:
    key: str
    value: str
    tags: str
    updated_at: float

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "value": self.value, "tags": self.tags, "updated_at": self.updated_at}


class Memory:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ------------------------------------------------------------------ facts
    def remember(self, key: str, value: str, tags: str = "") -> str:
        now = time.time()
        self.conn.execute(
            """
            INSERT INTO facts (key, value, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value, tags=excluded.tags, updated_at=excluded.updated_at
            """,
            (key, value, tags, now, now),
        )
        self.conn.commit()
        return key

    def recall(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM facts WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        self.conn.execute("UPDATE facts SET hits = hits + 1 WHERE key = ?", (key,))
        self.conn.commit()
        return row["value"]

    def forget(self, key: str) -> bool:
        cur = self.conn.execute("DELETE FROM facts WHERE key = ?", (key,))
        self.conn.commit()
        return cur.rowcount > 0

    def search(self, query: str, limit: int = 10) -> list[Fact]:
        like = f"%{query}%"
        rows = self.conn.execute(
            """
            SELECT key, value, tags, updated_at FROM facts
            WHERE key LIKE ? OR value LIKE ? OR tags LIKE ?
            ORDER BY updated_at DESC LIMIT ?
            """,
            (like, like, like, limit),
        ).fetchall()
        return [Fact(r["key"], r["value"], r["tags"], r["updated_at"]) for r in rows]

    def all_facts(self, limit: int = 50) -> list[Fact]:
        rows = self.conn.execute(
            "SELECT key, value, tags, updated_at FROM facts ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [Fact(r["key"], r["value"], r["tags"], r["updated_at"]) for r in rows]

    # --------------------------------------------------------------- episodes
    def log_message(self, session: str, role: str, content: str, **extra: Any) -> None:
        self.conn.execute(
            "INSERT INTO episodes (session, role, content, extra, created_at) VALUES (?, ?, ?, ?, ?)",
            (session, role, content, json.dumps(extra, default=str), time.time()),
        )
        self.conn.commit()

    def history(self, session: str, limit: int = 40) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT role, content FROM episodes WHERE session = ? ORDER BY id DESC LIMIT ?",
            (session, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def sessions(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT session, MAX(id) m FROM episodes GROUP BY session ORDER BY m DESC"
        ).fetchall()
        return [r["session"] for r in rows]

    # ---------------------------------------------------------------- journal
    def journal(self, kind: str, summary: str, detail: str = "") -> None:
        self.conn.execute(
            "INSERT INTO journal (kind, summary, detail, created_at) VALUES (?, ?, ?, ?)",
            (kind, summary, detail, time.time()),
        )
        self.conn.commit()

    def recent_journal(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT kind, summary, detail, created_at FROM journal ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ misc
    def summary_block(self, limit: int = 25) -> str:
        """A compact text block injected into the system prompt each turn."""
        facts = self.all_facts(limit)
        if not facts:
            return "(no long-term memories yet)"
        return "\n".join(f"- {f.key}: {f.value}" for f in facts)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Memory":
        return self

    def __exit__(self, *exc: Iterable[Any]) -> None:
        self.close()
