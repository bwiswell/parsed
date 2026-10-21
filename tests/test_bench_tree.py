"""Tests for ``bench/tree.py``: the generated tree is the size, and has the shapes, its docstring says.

It's also a test of ``declaration`` at scale: every one of its commands must declare.
"""

from __future__ import annotations

from bench.tree import COMMANDS, tree
from parsed.command import declaration


def test_it_declares_every_command():
    commands = tree()
    assert len(commands) == COMMANDS == 263
    assert all(declaration(cls).is_command for cls in commands)


def test_it_has_every_shape():
    found = [declaration(cls) for cls in tree()]
    assert sum(any(bound.renames for bound in d.phrases) for d in found) == 66  # every fourth
    assert sum(any(bound.left_out for bound in d.phrases) for d in found) == 38  # one in seven
    assert any(d.interactive and d.instead is not None for d in found)
    assert any(d.asks for d in found)
    assert any(d.reply is not None for d in found)
    assert any(d.flags for d in found)


def test_each_call_declares_new_classes():
    first, second = tree(3), tree(3)
    assert [cls.PHRASE for cls in first] == [cls.PHRASE for cls in second]
    assert not set(first) & set(second)
