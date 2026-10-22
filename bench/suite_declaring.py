"""The declaring suite: what a tree the size of a real one costs before any line is read.

- **decorate:** creating and decorating every command class and its base, as importing a module of them does;
- **declare:** each command's first ``declaration``, which checks its constants and binds its phrases;
- **reread:** ``declaration`` again, which the class keeps;
- **build:** the :class:`~parsed.tree.Tree` from commands already declared: their phrases compiled, the whole checked.

Each case covers the whole tree, :data:`~bench.tree.COMMANDS` commands; the docs quote it per tree and per command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from parsed.command import declaration
from parsed.tree import Tree

from .harness import Case
from .tree import COMMANDS, tree

if TYPE_CHECKING:
    from parsed.command import Command, Declaration

SUITE = 'declaring'


def _declare_all(commands: list[type[Command]]) -> list[Declaration]:
    return [declaration(cls) for cls in commands]


def cases() -> list[Case]:
    """The declaring suite's four cases."""
    declared = tree()
    _declare_all(declared)
    return [
        Case(suite=SUITE, name='decorate', iterations=40, per=COMMANDS, run=lambda _: tree()),
        Case(suite=SUITE, name='declare', iterations=40, per=COMMANDS, setup=tree, run=_declare_all),
        Case(suite=SUITE, name='reread', iterations=4_000, per=COMMANDS, setup=lambda: declared, run=_declare_all),
        Case(suite=SUITE, name='build', iterations=400, per=COMMANDS, setup=lambda: declared, run=Tree),
    ]
