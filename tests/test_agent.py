"""Offline tests: memory persistence, self-editing safety, and the tool loop.

Run with:  python -m unittest discover -s tests
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import selfedit  # noqa: E402
from agent.config import CONFIG  # noqa: E402
from agent.core import Agent  # noqa: E402
from agent.memory import Memory  # noqa: E402
from agent import tools  # noqa: E402


class FakeLLM:
    """Replays a scripted list of assistant messages."""

    def __init__(self, script):
        self.script = list(script)
        self.seen = []

    def chat(self, messages, tools=None, temperature=None):
        self.seen.append(messages)
        return self.script.pop(0)


def tool_call(name, **args):
    return {
        "content": None,
        "tool_calls": [
            {"id": f"c_{name}", "function": {"name": name, "arguments": json.dumps(args)}}
        ],
    }


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.mem = Memory(self.dir / "m.sqlite3")

    def tearDown(self):
        self.mem.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_remember_and_recall(self):
        self.mem.remember("user.name", "Devvrat")
        self.assertEqual(self.mem.recall("user.name"), "Devvrat")

    def test_upsert_overwrites(self):
        self.mem.remember("k", "v1")
        self.mem.remember("k", "v2")
        self.assertEqual(self.mem.recall("k"), "v2")
        self.assertEqual(len(self.mem.all_facts()), 1)

    def test_persists_across_reopen(self):
        self.mem.remember("pref.lang", "python")
        self.mem.close()
        again = Memory(self.dir / "m.sqlite3")
        self.assertEqual(again.recall("pref.lang"), "python")
        again.close()

    def test_search_and_forget(self):
        self.mem.remember("a.b", "loves sqlite", tags="db")
        self.assertTrue(self.mem.search("sqlite"))
        self.assertTrue(self.mem.forget("a.b"))
        self.assertFalse(self.mem.search("sqlite"))

    def test_history_is_ordered(self):
        for i in range(3):
            self.mem.log_message("s", "user", f"m{i}")
        self.assertEqual([m["content"] for m in self.mem.history("s")], ["m0", "m1", "m2"])


class SelfEditTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        CONFIG.state_dir = self.dir / "state"
        CONFIG.ensure_dirs()
        self.target = "scratch_test_module.py"
        selfedit.write_source(self.target, "VALUE = 1\n")

    def tearDown(self):
        path = selfedit.AGENT_ROOT / self.target
        if path.exists():
            path.unlink()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_read_write_roundtrip(self):
        self.assertIn("VALUE = 1", selfedit.read_source(self.target, with_line_numbers=False))

    def test_patch_applies(self):
        res = selfedit.patch_source(self.target, "VALUE = 1", "VALUE = 42")
        self.assertTrue(res.ok, res.message)
        self.assertIn("VALUE = 42", selfedit.read_source(self.target, with_line_numbers=False))

    def test_syntax_error_is_rejected(self):
        res = selfedit.write_source(self.target, "def broken(:\n")
        self.assertFalse(res.ok)
        self.assertIn("syntax error", res.message)
        # original content untouched
        self.assertIn("VALUE = 1", selfedit.read_source(self.target, with_line_numbers=False))

    def test_ambiguous_patch_is_refused(self):
        selfedit.write_source(self.target, "X = 1\nX = 1\n")
        res = selfedit.patch_source(self.target, "X = 1", "X = 2")
        self.assertFalse(res.ok)
        self.assertIn("matches 2 times", res.message)

    def test_rollback_restores_previous(self):
        selfedit.patch_source(self.target, "VALUE = 1", "VALUE = 99")
        res = selfedit.rollback(self.target)
        self.assertTrue(res.ok, res.message)
        self.assertIn("VALUE = 1", selfedit.read_source(self.target, with_line_numbers=False))

    def test_path_escape_is_blocked(self):
        with self.assertRaises(selfedit.SelfEditError):
            selfedit.read_source("../../etc/passwd")

    def test_disabled_self_edit(self):
        CONFIG.allow_self_edit = False
        try:
            res = selfedit.write_source(self.target, "VALUE = 7\n")
            self.assertFalse(res.ok)
        finally:
            CONFIG.allow_self_edit = True


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.mem = Memory(self.dir / "m.sqlite3")

    def tearDown(self):
        self.mem.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_plain_answer(self):
        agent = Agent("t", self.mem, FakeLLM([{"content": "hello there"}]))
        self.assertEqual(agent.chat("hi"), "hello there")
        self.assertEqual(self.mem.history("t")[-1]["content"], "hello there")

    def test_tool_call_then_answer(self):
        llm = FakeLLM([
            tool_call("remember", key="user.city", value="Delhi"),
            {"content": "noted"},
        ])
        agent = Agent("t", self.mem, llm)
        self.assertEqual(agent.chat("I live in Delhi"), "noted")
        self.assertEqual(self.mem.recall("user.city"), "Delhi")

    def test_unknown_tool_does_not_crash(self):
        llm = FakeLLM([tool_call("nope"), {"content": "recovered"}])
        agent = Agent("t", self.mem, llm)
        self.assertEqual(agent.chat("go"), "recovered")

    def test_memory_reaches_the_prompt(self):
        self.mem.remember("user.name", "Ada")
        llm = FakeLLM([{"content": "ok"}])
        Agent("t", self.mem, llm).chat("who am I?")
        self.assertIn("Ada", llm.seen[0][0]["content"])

    def test_step_limit(self):
        llm = FakeLLM([tool_call("change_history") for _ in range(50)])
        agent = Agent("t", self.mem, llm)
        self.assertIn("stopped after", agent.chat("loop"))

    def test_every_tool_has_a_schema(self):
        for schema in tools.schemas():
            fn = schema["function"]
            self.assertTrue(fn["name"] and fn["description"])
            self.assertNotIn("memory", fn["parameters"]["properties"])


if __name__ == "__main__":
    unittest.main()
