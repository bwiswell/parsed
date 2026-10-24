"""The running suite: what running a line costs, on a tree the size of a real one.

- **run:** each line run in an open session (``Session.run``): routed to its mount, read and loaded, its handler
  called with a fresh context between the app's hooks, and what came of it put in its envelope.

The app mounts the tree at the root, binds one handler to every command and adds a before and an after hook, so a
line pays for the whole path; the handler and the hooks do nothing. A session is opened once, at a terminal so the
tree's interactive commands run too, on an event loop the suite keeps, and the case runs a line for each command,
:data:`~bench.tree.COMMANDS` lines; the docs quote it for every line and per line.
"""

from __future__ import annotations

import asyncio

from parsed.app import App
from parsed.tree import Tree

from .harness import Case
from .tree import COMMANDS, lines, tree

SUITE = 'running'


def _nothing(*_: object) -> None:
    return None


def cases() -> list[Case]:
    """The running suite's one case.

    Raises:
        RuntimeError: A line doesn't run cleanly, so the case would time a refusal.
    """
    commands = tree()
    built = Tree(commands)
    app = App('bench')
    app.mount(built)
    for found in built.commands:
        app.on(found.cls, _nothing)
    app.before(_nothing)
    app.after(_nothing)
    said = lines(commands)
    loop = asyncio.new_event_loop()
    session = loop.run_until_complete(app.open(terminal=True).__aenter__())

    async def every() -> list[bool]:
        return [(await session.run(line)).ok for line in said]

    if not all(loop.run_until_complete(every())):
        msg = 'a bench line does not run cleanly'
        raise RuntimeError(msg)
    return [Case(suite=SUITE, name='run', iterations=400, per=COMMANDS, run=lambda _: loop.run_until_complete(every()))]
