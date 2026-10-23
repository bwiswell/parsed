"""The waiting suite: how long a wait takes to wake, on a tree the size of a real one.

- **wake:** a change to its wake: the app says its state moved (``session.changed()``), and a line watching a read
  (``--watch``) reads it again and gives its next reply, its envelope made.

The read is the tree's first that can wait, its handler a fake state's, each reply new; the session is opened once,
on an event loop the suite keeps, with ``interval=None``, so only a change wakes the watch. Each operation moves the
state :data:`WAKES` times, each time until the watch's next reply is in; the docs quote it per wake.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from parsed.app import App
from parsed.tree import Tree

from .harness import Case
from .tree import View, lines, tree

if TYPE_CHECKING:
    from parsed.reply import Result

SUITE = 'waiting'

#: The changes one operation wakes the watch for.
WAKES = 50


def cases() -> list[Case]:
    """The waiting suite's one case."""
    built = Tree(tree())
    reader = next(found.cls for found in built.commands if found.can_wait)
    line = f'{lines([reader])[0]} --watch --count {WAKES + 1}'
    moves = [0]
    app = App('bench')
    app.mount(built)
    app.on(reader, lambda *_: View(key='bench', lines=[str(moves[0])]))  # a reply new with each move
    loop = asyncio.new_event_loop()
    session = loop.run_until_complete(app.open(interval=None).__aenter__())

    def setup() -> tuple[asyncio.Task[None], asyncio.Queue[Result]]:
        """A watch started, its first reply in, before any change: untimed."""
        queue: asyncio.Queue[Result] = asyncio.Queue()

        async def watch() -> None:
            async for result in session.watch(line):
                queue.put_nowait(result)

        task = loop.create_task(watch())
        loop.run_until_complete(queue.get())
        return task, queue

    async def wakes(task: asyncio.Task[None], queue: asyncio.Queue[Result]) -> None:
        for _ in range(WAKES):
            moves[0] += 1
            session.changed()
            await queue.get()
        await task

    def run(started: tuple[asyncio.Task[None], asyncio.Queue[Result]]) -> None:
        loop.run_until_complete(wakes(*started))

    return [Case(suite=SUITE, name='wake', iterations=200, per=WAKES, run=run, setup=setup)]
