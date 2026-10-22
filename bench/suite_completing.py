"""The completing suite: what Tab costs, on a tree the size of a real one.

- **complete:** what may come after each line's words but its last (``Tree.complete``): the line walked loosely as
  far as it goes, and the slot's values, the literal words and the flags offered there.

The case completes one line for each command, :data:`~bench.tree.COMMANDS` lines, on a tree built once; the docs
quote it for every line and per line.
"""

from __future__ import annotations

from parsed.tree import Tree

from .harness import Case
from .tree import COMMANDS, lines, tree

SUITE = 'completing'


def cases() -> list[Case]:
    """The completing suite's one case."""
    commands = tree()
    built = Tree(commands)
    typed = [line.rsplit(' ', 1)[0] + ' ' for line in lines(commands)]
    return [
        Case(
            suite=SUITE, name='complete', iterations=400, per=COMMANDS, run=lambda _: [built.complete(t) for t in typed]
        ),
    ]
