"""The rendering suite: what writing an instance back to its line costs, on a tree the size of a real one.

- **render:** each command's instance, read from its line, written back to a line (``Tree.render``): its phrase
  picked, its values spelled by their kinds and quoted where they must be, its flags given.

The case renders an instance of each command, :data:`~bench.tree.COMMANDS` of them, on a tree built once; the docs
quote it for every command and per command.
"""

from __future__ import annotations

from parsed.tree import Tree

from .harness import Case
from .tree import COMMANDS, lines, tree

SUITE = 'rendering'


def cases() -> list[Case]:
    """The rendering suite's one case."""
    commands = tree()
    built = Tree(commands)
    instances = [built.read(line) for line in lines(commands)]
    return [
        Case(
            suite=SUITE,
            name='render',
            iterations=400,
            per=COMMANDS,
            run=lambda _: [built.render(command) for command in instances],
        ),
    ]
