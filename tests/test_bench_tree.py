"""Tests for ``bench/tree.py``: the generated tree is the size, and has the shapes, its docstring says.

It's also a test of ``declaration`` and reading at scale: every one of its commands must declare, and its line read.
"""

from __future__ import annotations

from bench.tree import COMMANDS, lines, tree
from parsed.command import declaration
from parsed.tree import Tree


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


def test_each_line_reads_to_its_command():
    commands = tree()
    built = Tree(commands)
    said = lines(commands)
    assert len(said) == COMMANDS
    assert [built.walk(line).command for line in said] == commands
    assert any('--for 90s' in line for line in said)
    assert all(isinstance(built.read(line), cls) for line, cls in zip(said, commands, strict=True))
