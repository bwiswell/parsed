"""An app: trees mounted under prefixes, the handlers their commands run with, and the names it reads lines with.

``parsed.App(prog)`` holds a program's commands as mounts:

- **``app.mount(target, under=…, params=…)``** mounts a tree, or a module or package of commands by name, under a
  prefix of words (none, by default), and returns its :class:`Mount`. One package may be mounted several times,
  each mount with its own prefix and its own ``params`` (a service's settings, say), so one group serves several
  apps, or one app twice. A mount that would make a line read two ways is refused.
- **``app.on(Cls, handler)``** binds the handler a command runs with, in every mount that holds it;
  ``mount.on(Cls, handler)`` binds one for that mount alone, which wins there. A handler is a callable, or the path
  to one, ``'pkg.module:function'``, imported when it's first looked up. So an app that gathers several packages
  imports none of their runtimes to read a line.
- **``app.names(category, resolver)``** gives the resolver a category's names are read by (:mod:`parsed.names`), in
  every mount; ``mount.names(category, resolver)`` gives one for that mount alone, which wins there.

A line goes to its mount by its first words (:mod:`parsed._walk._route`), then the mount's tree reads it, with the
mount's names: :meth:`App.walk`, :meth:`App.read`, :meth:`App.complete` and :meth:`App.render`, as a tree's.

**A session runs lines** against the app's state: ``async with app.open(state) as session``. A state that opens and
closes (a context manager, as a link to a server is) is entered when the session opens and left when it closes, and
handlers see what entering it gave. Each line's handler is called as ``handler(command, ctx)``, ``ctx`` a fresh
:class:`~parsed.context.Context`, and awaited if it's async; it returns its command's ``REPLY``, text or nothing.

- ``await session.run(line)`` gives what came of it as a :class:`~parsed.reply.Result`, the envelope every parsed
  app answers with, its error and exit code among it: it raises for nothing the line or its handler does.
- ``await session.call(line)`` gives what the handler returned, and lets every error through.
- ``app.run(line, state)`` runs one line in a session of its own, for a program that runs one and exits.

A line that gives ``--help`` runs nothing: it's answered with its command's usage.

**A handler asks first** by returning :class:`~parsed.reply.Ask` ``(question, then)``, having done nothing yet. A
yes runs ``then``, which may ask again: ``--yes`` on the line (or ``yes=True``) answers each question yes; else the
session's ``answer`` does, if it has one (``app.open(state, answer=parsed.reply.terminal)`` prompts a person). A
question left unanswered, or answered no, leaves the line undone, its question in the result (``asks``).

**A line that waits** (``--until``, :mod:`parsed.wait`) reads again until its reply meets every condition, or its
bound passes: at once when the app says its state moved (``session.changed()``), else every ``interval`` seconds
(``app.open(state, interval=…)``, a second by default; ``None`` for an app that signals every change).

**Hooks run around each command,** in a stated order: ``app.before(hook)``, ``app.after(hook)`` and
``app.on_error(hook)`` for every command, or with commands named (``app.before(hook, FleetBuyShip)``), for those
alone. Before hooks run the app's, then the command's; after and on-error hooks the command's, then the app's; each
scope's in the order they were added. A failure in a before hook, the handler, a question's answer or an after hook
runs the on-error hooks, then goes on.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import inspect
import re
from contextlib import AbstractAsyncContextManager, AbstractContextManager, AsyncExitStack
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, NamedTuple, overload

# At runtime: tooling evaluates a class's annotations (`typing.get_type_hints`), and `Routed`'s name a `Reading`.
from ._walk import Reading, Routes
from .command import Command, declaration
from .errors import DeclarationError, ReadError, RenderError
from .reply import Ask, Result
from .tree import Tree

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping
    from types import TracebackType

    from seared import Seared

    from ._walk import Completion
    from .context import Context
    from .names import Resolver
    from .reply import Answer
    from .wait import Wait

#: What a command runs with: a callable, given the command and its context (``handler(command, ctx)``), whose result
#: is awaited if it's awaitable.
type Handler = Callable[..., object]

#: What runs around a command: ``before(command, ctx)``, ``after(command, ctx, found)`` (what its handler came to:
#: its reply, text, nothing, or the question it stopped at) or ``on_error(command, ctx, error)``, awaited if async.
type Hook = Callable[..., object]


class Hooks(NamedTuple):
    """The hooks a command runs with: each stage's, in the order they run."""

    before: tuple[Hook, ...]
    after: tuple[Hook, ...]
    on_error: tuple[Hook, ...]


#: The stages hooks run at, in the order a line meets them.
_STAGES = ('before', 'after', 'on_error')

#: The path to a handler: a module's dotted name, ``:``, and a name in it (dotted, for an attribute's).
_PATH = re.compile(r'[A-Za-z_]\w*(\.[A-Za-z_]\w*)*:[A-Za-z_]\w*(\.[A-Za-z_]\w*)*')


class App:
    """A program's commands: trees mounted under prefixes, with their handlers and names (see the module).

    Args:
        prog: The program's name, as it's typed: ``farlandia``.

    Raises:
        DeclarationError: ``prog`` isn't a name.
    """

    def __init__(self, prog: str) -> None:
        """An app with nothing mounted yet."""
        if not isinstance(prog, str) or not prog.strip():
            msg = f"App({prog!r}): prog is the program's name, as it's typed"
            raise DeclarationError(msg)
        self.prog = prog
        self._mounts: list[Mount] = []
        self._routes: Routes[Mount] = Routes()
        self._bound = _Bindings('')
        self._hooks: dict[str, list[tuple[Hook, frozenset[type]]]] = {stage: [] for stage in _STAGES}

    @property
    def mounts(self) -> tuple[Mount, ...]:
        """Its mounts, in the order they were mounted."""
        return tuple(self._mounts)

    @property
    def resolvers(self) -> Mapping[str, Resolver]:
        """The resolvers given for every mount, by category."""
        return MappingProxyType(self._bound.names)

    def mount(self, target: Tree | str, *, under: str = '', params: object = None) -> Mount:
        """Mount ``target``'s commands under ``under``, a prefix of words, with ``params`` for their handlers.

        Args:
            target: A tree, or a module or package of commands by name, collected as ``Tree.collect`` does. A tree
                under a prefix of its own keeps it, beneath ``under``.
            under: The prefix its lines begin with (``'relay'``); none by default.
            params: What its handlers are given beside the command: a service's settings, say.

        Raises:
            DeclarationError: Its commands don't build a tree, ``under`` isn't words, or a line would read two ways
                with a mount already made: the message names both.
            ImportError: A module named doesn't import.
        """
        if isinstance(target, str):
            tree, source = Tree.collect(target, under=under), target
        elif isinstance(target, Tree):
            tree = target
            if under.strip():
                beneath = f'{under} {target.under}' if target.under else under
                tree = Tree((found.cls for found in target.commands), under=beneath)
            source = target.commands[0].cls.__module__ if target.commands else 'a tree'
        else:
            msg = f'mount({target!r}): a tree, or a module or package of commands by name'
            raise DeclarationError(msg)
        mounted = Mount(self, tree, source=source, params=params)
        self._routes.add(mounted)
        self._mounts.append(mounted)
        return mounted

    def on(self, cls: type[Command], handler: Handler | str) -> None:
        """Bind ``handler`` to ``cls``, in every mount that holds it, unless the mount binds its own.

        Args:
            cls: A command class.
            handler: A callable, or the path to one: ``'pkg.module:function'``, imported when it's first looked up.

        Raises:
            DeclarationError: ``cls`` isn't a command class, the handler isn't a callable or a path, or ``cls`` has a
                handler bound here already.
        """
        self._bound.on(cls, handler)

    def names(self, category: str, resolver: Resolver) -> None:
        """Read ``category``'s names by ``resolver``, in every mount, unless the mount gives its own.

        Raises:
            DeclarationError: ``category`` isn't a name, ``resolver`` has no ``lookup``, ``suggest`` and ``options``,
                or the category has a resolver here already.
        """
        self._bound.name(category, resolver)

    def before(self, hook: Hook, *commands: type[Command]) -> None:
        """Run ``hook(command, ctx)`` before each command's handler: every command's, or only ``commands``'.

        A before hook that raises stops the line, its handler not run, as the handler's own failure would.

        Raises:
            DeclarationError: ``hook`` isn't callable, or one of ``commands`` isn't a command class.
        """
        self._hook('before', hook, commands)

    def after(self, hook: Hook, *commands: type[Command]) -> None:
        """Run ``hook(command, ctx, found)`` after each command's handler: every command's, or only ``commands``'.

        ``found`` is what the handler came to: its reply, text, nothing, or the question it stopped at.

        Raises:
            DeclarationError: As :meth:`before` does.
        """
        self._hook('after', hook, commands)

    def on_error(self, hook: Hook, *commands: type[Command]) -> None:
        """Run ``hook(command, ctx, error)`` when a command's line fails: every command's, or only ``commands``'.

        It runs for a failure in a before hook, the handler, a question's answer or an after hook; the error goes on
        after the on-error hooks have run.

        Raises:
            DeclarationError: As :meth:`before` does.
        """
        self._hook('on_error', hook, commands)

    def hooks(self, cls: type[Command]) -> Hooks:
        """The hooks ``cls`` runs with, each stage's in the order they run.

        Before hooks: the app's, then the command's; after and on-error hooks: the command's, then the app's. Each
        scope's run in the order they were added.
        """
        found: dict[str, tuple[Hook, ...]] = {}
        for stage in _STAGES:
            every = [hook for hook, only in self._hooks[stage] if not only]
            own = [hook for hook, only in self._hooks[stage] if cls in only]
            found[stage] = tuple(every + own if stage == 'before' else own + every)
        return Hooks(**found)

    def _hook(self, stage: str, hook: Hook, commands: tuple[type[Command], ...]) -> None:
        if not callable(hook):
            msg = f'{stage}({hook!r}, …): a hook is a callable'
            raise DeclarationError(msg)
        for cls in commands:
            if not (isinstance(cls, type) and issubclass(cls, Command)) or not declaration(cls).is_command:
                msg = f'{stage}(…, {cls!r}): a command class, with a PHRASE'
                raise DeclarationError(msg)
        self._hooks[stage].append((hook, frozenset(commands)))

    def handler(self, cls: type[Command]) -> Handler | None:
        """The handler bound to ``cls`` by :meth:`on`, imported from its path the first time; ``None`` if none is.

        A mount's own is :meth:`Mount.handler`'s.

        Raises:
            ImportError: Its path doesn't import, or names nothing in its module.
            TypeError: Its path names something that isn't callable.
        """
        return self._bound.handler(cls)

    @overload
    def open(
        self, state: None = None, *, verbosity: int = 0, answer: Answer | None = None, interval: float | None = 1.0
    ) -> Session[None]: ...
    @overload
    def open[S](
        self,
        state: AbstractAsyncContextManager[S],
        *,
        verbosity: int = 0,
        answer: Answer | None = None,
        interval: float | None = 1.0,
    ) -> Session[S]: ...
    @overload
    def open[S](
        self,
        state: AbstractContextManager[S],
        *,
        verbosity: int = 0,
        answer: Answer | None = None,
        interval: float | None = 1.0,
    ) -> Session[S]: ...
    @overload
    def open[S](
        self, state: S, *, verbosity: int = 0, answer: Answer | None = None, interval: float | None = 1.0
    ) -> Session[S]: ...
    def open(
        self, state: object = None, *, verbosity: int = 0, answer: Answer | None = None, interval: float | None = 1.0
    ) -> Session[Any]:
        """A session of the app, to run lines against ``state``: ``async with app.open(state) as session``.

        Args:
            state: What handlers are given as ``ctx.state``: the app's own (a link, a mirror). A context manager,
                sync or async, is entered when the session opens, and its handlers see what entering it gave; it's
                left when the session closes. ``None`` by default, for an app with no state.
            verbosity: How much handlers should say (``ctx.verbosity``): ``0`` by default, more for more.
            answer: What answers a question a line asks, when ``--yes`` doesn't: yes or no from the question, sync
                or async (``parsed.reply.terminal`` asks a person). With none, a question is left unanswered.
            interval: How often, in seconds, a wait reads again when the app says nothing has changed; ``None`` for
                an app that calls ``session.changed()`` on every change, so a wait reads only then.

        Raises:
            ValueError: ``interval`` isn't a positive number of seconds, or ``None``.
        """
        return Session(self, state, verbosity=verbosity, answer=answer, interval=interval)

    def run(  # noqa: PLR0913 -- the line, its state, and how it's said, answered and waited on
        self,
        line: str,
        state: object = None,
        *,
        verbosity: int = 0,
        yes: bool = False,
        answer: Answer | None = None,
        interval: float | None = 1.0,
    ) -> Result:
        """Run one line in a session of its own, opened around it and closed after: for a program that runs one.

        It gives what :meth:`Session.run` gives. It runs an event loop for the session (``asyncio.run``), so it's
        called outside one; inside one, open a session.

        Args:
            line: The line.
            state: The app's state, as :meth:`open` takes it.
            verbosity: How much handlers should say, as :meth:`open` takes it.
            yes: Whether to answer every question the line asks yes, as ``--yes`` does.
            answer: What answers a question otherwise, as :meth:`open` takes it.
            interval: How often a wait reads again, as :meth:`open` takes it.

        Raises:
            RuntimeError: It's called inside a running event loop.
        """
        if _looping():
            msg = 'app.run(line) runs an event loop of its own; inside one, open a session: async with app.open(state)'
            raise RuntimeError(msg)

        async def once() -> Result:
            async with self.open(state, verbosity=verbosity, answer=answer, interval=interval) as session:
                return await session.run(line, yes=yes)

        return asyncio.run(once())

    def walk(self, line: str, *, placeholders: bool = False) -> Routed:
        """The mount ``line`` goes to, and what its tree reads the line to, with the mount's names.

        Args:
            line: The line.
            placeholders: Whether a ``<name>`` word stands for any value, as :meth:`Tree.walk` takes it.

        Raises:
            ReadError: The line reaches no mount, or its mount's tree refuses it.
        """
        mount = self._routes.route(line)
        return Routed(mount, mount.tree.walk(line, mount.resolvers, placeholders=placeholders))

    def read(self, line: str) -> Command:
        """The command ``line`` says, loaded by seared, as :meth:`walk` routes and reads it.

        Raises:
            ReadError: As :meth:`walk` does, or a value seared refuses.
        """
        return self.walk(line).load()

    def complete(self, text: str) -> Completion:
        """What may come next on ``text``, a line up to the cursor: its mount's tree's offers, or a prefix's words."""
        found = self._routes.complete(text)
        if isinstance(found, Mount):
            return found.tree.complete(text, found.resolvers)
        return found

    def render(self, command: Command, *, mount: Mount | None = None) -> str:
        """The line that says ``command``, by its mount's tree, prefix and all.

        Args:
            command: An instance of a mounted command.
            mount: The mount to say it in, where its command is mounted more than once.

        Raises:
            RenderError: Its command is mounted nowhere, more than once and ``mount`` doesn't say which, or not in
                ``mount``; or no phrase can say it.
        """
        cls = type(command)
        if mount is None:
            holding = [found for found in self._mounts if found.holds(cls)]
            if not holding:
                msg = f'{cls.__qualname__} is mounted nowhere in {self.prog}'
                raise RenderError(msg)
            if len(holding) > 1:
                where = ', '.join(found.label for found in holding)
                msg = f'{cls.__qualname__} is mounted {len(holding)} times ({where}): say which, with mount='
                raise RenderError(msg)
            mount = holding[0]
        elif mount.app is not self or not mount.holds(cls):
            msg = f'{cls.__qualname__} is not mounted in {mount.label}'
            raise RenderError(msg)
        return mount.tree.render(command, mount.resolvers)


class Mount:
    """A tree mounted in an app under its prefix, with its own parameters, and handlers and names that win in it.

    Made by :meth:`App.mount`.

    Attributes:
        app: The app it's mounted in.
        tree: Its tree, under its prefix.
        source: Where its commands come from: the module or package named, or a tree's first command's module.
        params: What its handlers are given beside the command; ``None`` if nothing.
    """

    def __init__(self, app: App, tree: Tree, *, source: str, params: object) -> None:
        """Hold the tree and its parameters; nothing bound yet."""
        self.app = app
        self.tree = tree
        self.source = source
        self.params = params
        self._held = frozenset(found.cls for found in tree.commands)
        self._bound = _Bindings(self.label)

    def __repr__(self) -> str:
        """The mount, by its label."""
        return f'<Mount {self.label}>'

    @property
    def under(self) -> str:
        """Its prefix's words, separated by single spaces; ``''`` at the root."""
        return self.tree.under

    @property
    def label(self) -> str:
        """The mount as a refusal names it: its source, and its prefix."""
        return f'{self.source} under {self.under!r}' if self.under else f'{self.source} at the root'

    @property
    def resolvers(self) -> Mapping[str, Resolver]:
        """The resolvers its lines are read with, by category: the app's, and its own, which win."""
        return MappingProxyType({**self.app.resolvers, **self._bound.names})

    def holds(self, cls: type) -> bool:
        """Whether ``cls`` is one of its commands."""
        return cls in self._held

    def on(self, cls: type[Command], handler: Handler | str) -> None:
        """Bind ``handler`` to ``cls`` in this mount alone, over the app's, as :meth:`App.on` takes it.

        Raises:
            DeclarationError: As :meth:`App.on` does, or ``cls`` isn't one of its commands.
        """
        if isinstance(cls, type) and issubclass(cls, Command) and not self.holds(cls):
            msg = f'{self.label} has no {cls.__qualname__}: bind it on the app, or on the mount that has it'
            raise DeclarationError(msg)
        self._bound.on(cls, handler)

    def names(self, category: str, resolver: Resolver) -> None:
        """Read ``category``'s names by ``resolver`` in this mount alone, over the app's, as :meth:`App.names` takes.

        Raises:
            DeclarationError: As :meth:`App.names` does.
        """
        self._bound.name(category, resolver)

    def handler(self, cls: type[Command]) -> Handler | None:
        """The handler ``cls`` runs with in this mount: its own, else the app's; ``None`` if neither binds one.

        Raises:
            ImportError: Its path doesn't import, or names nothing in its module.
            TypeError: Its path names something that isn't callable.
        """
        own = self._bound.handler(cls)
        return own if own is not None else self.app.handler(cls)


class Session[S]:
    """An app, open: its state held for every line it calls, until it closes (see the module).

    Made by :meth:`App.open`, and used once, as ``async with app.open(state) as session``.

    Attributes:
        app: The app.
        verbosity: How much handlers should say: ``0`` by default, more for more.
        answer: What answers a question a line asks, when ``--yes`` doesn't; ``None`` leaves it unanswered.
        interval: How often, in seconds, a wait reads again when nothing has changed; ``None``: only on a change.
    """

    def __init__(
        self, app: App, state: object, *, verbosity: int, answer: Answer | None, interval: float | None
    ) -> None:
        """Hold what to open; nothing is entered until the session opens."""
        if interval is not None and (
            isinstance(interval, bool) or not isinstance(interval, int | float) or interval <= 0
        ):
            msg = f'interval={interval!r}: how often a wait reads again, a positive number of seconds, or None'
            raise ValueError(msg)
        self.app = app
        self.verbosity = verbosity
        self.answer = answer
        self.interval = interval
        self._given = state
        self._state: Any = None
        self._stack: AsyncExitStack | None = None
        self._closed = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._change = asyncio.Event()

    def __repr__(self) -> str:
        """The session, by its app and whether it's open."""
        stage = 'closed' if self._closed else 'open' if self._stack is not None else 'not yet open'
        return f'<Session of {self.app.prog}, {stage}>'

    @property
    def is_open(self) -> bool:
        """Whether it's open: entered, and not yet left."""
        return self._stack is not None

    @property
    def state(self) -> S:
        """The app's state, as the session opened it.

        Raises:
            RuntimeError: The session isn't open.
        """
        self._check_open()
        return self._state

    async def __aenter__(self) -> Session[S]:
        """Open: enter the state, if it's a context manager.

        Raises:
            RuntimeError: The session has been opened before.
        """
        if self._stack is not None or self._closed:
            msg = f'{self!r} opens once: open another with app.open(state)'
            raise RuntimeError(msg)
        stack = AsyncExitStack()
        given = self._given
        if isinstance(given, AbstractAsyncContextManager):
            self._state = await stack.enter_async_context(given)
        elif isinstance(given, AbstractContextManager):
            self._state = stack.enter_context(given)
        else:
            self._state = given
        self._loop = asyncio.get_running_loop()
        self._stack = stack
        return self

    async def __aexit__(
        self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Close: leave the state, if it was entered, telling it of any error the session's body raised.

        The error goes on past the session, whatever the state makes of it: a session never swallows one.
        """
        stack, self._stack, self._closed = self._stack, None, True
        if stack is not None:
            await stack.__aexit__(kind, error, traceback)

    def changed(self) -> None:
        """Say the app's state moved: every wait on the session reads again, at once. From any thread.

        Wire it where the app learns of a change: ``controls.on_change = session.changed``. A session that isn't
        open has nothing waiting, so it's a no-op there.
        """
        loop = self._loop
        if loop is None or self._stack is None:
            return
        if _looping() and asyncio.get_running_loop() is loop:
            self._wake()
        else:
            loop.call_soon_threadsafe(self._wake)

    def _wake(self) -> None:
        """Set the change every wait holds, and hold a fresh one for the next."""
        change, self._change = self._change, asyncio.Event()
        change.set()

    async def run(self, line: str, *, yes: bool = False) -> Result:
        """Run ``line`` as :meth:`call` does, and give what came of it: the envelope, its error and exit code among it.

        A line that doesn't read, a value its field refuses, and a handler that fails, has no binding or returns what
        it shouldn't, each comes back as the result's error, none of them raised. A question it stops at is its
        ``asks``, with nothing done. ``yes`` answers every question yes, as ``--yes`` does.

        Raises:
            RuntimeError: The session isn't open.
        """
        self._check_open()
        try:
            routed = self.app.walk(line)
        except ReadError as e:
            return Result(line, ok=False, text=str(e), error=e.to_json(), exception=e)
        said, own = routed.said, routed.reading.own
        if 'help' in own:
            return Result(line, said, text=routed.mount.tree.usage(routed.reading.end))
        try:
            command = routed.load()
        except ReadError as e:
            return Result(line, said, ok=False, text=str(e), error=e.to_json(), exception=e)
        try:
            found = await self._handled(routed, command, yes=yes)
        except Exception as e:  # noqa: BLE001 -- a handler's failure is the result's, never the caller's
            message = f'{type(e).__name__}: {e}' if str(e) else type(e).__name__
            return Result(
                line, said, ok=False, text=message, error={'error': 'handler', 'message': message}, exception=e
            )
        return _outcome(line, said, found, dry_run='dry-run' in own, wait=routed.reading.wait)

    async def call(self, line: str, *, yes: bool = False) -> object:
        """Run the command ``line`` says by its handler, with a fresh context, and give what the handler returns.

        The line goes to its mount and is loaded there (:meth:`App.walk`); its handler is the mount's, else the
        app's (:meth:`Mount.handler`), called as ``handler(command, ctx)`` and awaited if it's async. It returns its
        command's ``REPLY``, text or nothing, or asks first. A line that gives ``--help`` runs nothing: it gives the
        command's usage.

        A question is answered yes by ``--yes`` or ``yes``, else by the session's ``answer``; a yes runs what the
        handler asked to do, which may ask again. A question left unanswered, or answered no, is given back: the
        :class:`~parsed.reply.Ask` itself, with nothing done.

        Raises:
            RuntimeError: The session isn't open.
            ReadError: The line doesn't read.
            LookupError: Its command has no handler.
            ImportError: Its handler's path doesn't import.
            TypeError: Its handler returned something besides its ``REPLY``, text, nothing or an ``Ask``.
            Exception: Whatever its handler raises, or its answer.
        """
        self._check_open()
        routed = self.app.walk(line)
        if 'help' in routed.reading.own:
            return routed.mount.tree.usage(routed.reading.end)
        return await self._handled(routed, routed.load(), yes=yes)

    async def _handled(self, routed: Routed, command: Command, *, yes: bool) -> Seared | str | Ask | None:
        """Call the handler for ``command`` between its hooks, check what it returned, and ask each question it asks."""
        cls = routed.command
        handler = routed.mount.handler(cls)
        if handler is None:
            msg = f'{cls.__qualname__} has no handler in {routed.mount.label}: bind one with app.on'
            raise LookupError(msg)
        hooks, ctx = self.app.hooks(cls), self.context(routed)
        yes = yes or 'yes' in routed.reading.own

        async def read() -> Seared | str | Ask | None:
            found = _checked(await _awaited(handler(command, ctx)), cls)
            while isinstance(found, Ask) and (yes or await self._answered(found.question)):
                found = _checked(await _awaited(found.then()), cls)
            return found

        try:
            for hook in hooks.before:
                await _awaited(hook(command, ctx))
            wait, change = routed.reading.wait, self._change  # the change held before the read, so none is missed
            found = await read()
            if wait is not None:
                found = await self._waited(wait, found, change, read, cls)
            for hook in hooks.after:
                await _awaited(hook(command, ctx, found))
        except Exception as error:
            for hook in hooks.on_error:
                await _awaited(hook(command, ctx, error))
            raise
        return found

    async def _waited(
        self,
        wait: Wait,
        found: Seared | str | Ask | None,
        change: asyncio.Event,
        read: Callable[[], Awaitable[Seared | str | Ask | None]],
        cls: type[Command],
    ) -> Seared | str | Ask | None:
        """Read again, on a change or the interval, until a reply meets every condition, or the bound passes.

        At the bound it stops, reading again only if a change woke it there.
        """
        clock = asyncio.get_running_loop()
        deadline = clock.time() + wait.timeout
        while not isinstance(found, Ask):
            reply = _replied(found, cls)
            left = deadline - clock.time()
            if wait.met(reply) or left <= 0:
                break
            woke = await _woken(change, left if self.interval is None else min(left, self.interval))
            if not woke and clock.time() >= deadline:
                break
            change = self._change
            found = await read()
        return found

    async def _answered(self, question: str) -> bool:
        """Whether the session's answer says yes to ``question``; no, with none."""
        if self.answer is None:
            return False
        return bool(await _awaited(self.answer(question)))

    def context(self, routed: Routed) -> Context[S]:
        """The context a line's handler is given, for ``routed``: this session, its mount and its reading."""
        from .context import Context  # here: the context's module imports this one

        return Context(self, routed.mount, routed.reading)

    def _check_open(self) -> None:
        if self._stack is None:
            msg = f'{self!r}: call lines inside `async with app.open(state) as session`'
            raise RuntimeError(msg)


@dataclass(frozen=True, slots=True)
class Routed:
    """A line, gone to its mount and read by the mount's tree.

    Attributes:
        mount: The mount it went to.
        reading: What its tree read it to: the command, and each field's words and value.
    """

    mount: Mount
    reading: Reading

    @property
    def command(self) -> type[Command]:
        """The command class it says."""
        return self.reading.command

    @property
    def said(self) -> str:
        """The phrase that said it, after its mount's prefix: ``'relay run'``, ``'fleet {fleet} mine'``."""
        phrase = self.reading.end.bound.phrase.text
        return f'{self.mount.under} {phrase}' if self.mount.under else phrase

    def load(self) -> Command:
        """The command, loaded by seared from its fields' values.

        Raises:
            ReadError: A value seared refuses.
        """
        return self.reading.load()


@dataclass(slots=True)
class _Handler:
    """A handler as bound: a callable, or the path to one, imported the first time it's looked up."""

    said: Handler | str
    found: Handler | None = None

    def resolve(self, cls: type) -> Handler:
        if self.found is None:
            self.found = self.said if not isinstance(self.said, str) else _imported(self.said, cls)
        return self.found


class _Bindings:
    """What an app or a mount binds: handlers, by command class, and resolvers, by category."""

    def __init__(self, where: str) -> None:
        self.where = where
        self.handlers: dict[type, _Handler] = {}
        self.names: dict[str, Resolver] = {}

    def on(self, cls: type[Command], handler: Handler | str) -> None:
        if not (isinstance(cls, type) and issubclass(cls, Command)) or not declaration(cls).is_command:
            msg = f'on({cls!r}, …): a command class, with a PHRASE'
            raise DeclarationError(msg)
        name = cls.__qualname__
        if isinstance(handler, str) and not _PATH.fullmatch(handler):
            msg = f"on({name}, {handler!r}): a handler's path is a module and a name in it: 'pkg.module:function'"
            raise DeclarationError(msg)
        if not isinstance(handler, str) and not callable(handler):
            msg = f"on({name}, {handler!r}): a handler is a callable, or the path to one: 'pkg.module:function'"
            raise DeclarationError(msg)
        if cls in self.handlers:
            msg = f'{name} has a handler{self._here()} already: bind one once'
            raise DeclarationError(msg)
        self.handlers[cls] = _Handler(handler)

    def name(self, category: str, resolver: Resolver) -> None:
        if not isinstance(category, str) or not category.isidentifier():
            msg = f'names({category!r}, …): a category is a name, such as fleet or station'
            raise DeclarationError(msg)
        if not all(callable(getattr(resolver, method, None)) for method in ('lookup', 'suggest', 'options')):
            msg = f'names({category!r}, {resolver!r}): a resolver has lookup, suggest and options'
            raise DeclarationError(msg)
        if category in self.names:
            msg = f'{category} has a resolver{self._here()} already: give one once'
            raise DeclarationError(msg)
        self.names[category] = resolver

    def handler(self, cls: type) -> Handler | None:
        found = self.handlers.get(cls)
        return None if found is None else found.resolve(cls)

    def _here(self) -> str:
        return f' in {self.where}' if self.where else ''


def _checked(found: object, cls: type[Command]) -> Seared | str | Ask | None:
    """What a handler returned, if it's its command's ``REPLY``, text, nothing or an ``Ask``: refused otherwise."""
    reply = declaration(cls).reply
    if found is None or isinstance(found, (str, Ask)) or (reply is not None and isinstance(found, reply)):
        return found
    said = f"{cls.__qualname__}'s handler returned a {type(found).__name__}"
    if reply is None:
        msg = f'{said}: a handler returns text or nothing, or the REPLY its command declares, or asks first'
    else:
        msg = f'{said}: a handler returns its REPLY ({reply.__name__}), text or nothing, or asks first'
    raise TypeError(msg)


def _outcome(line: str, said: str, found: Seared | str | Ask | None, *, dry_run: bool, wait: Wait | None) -> Result:
    """What a line came to, from what its handler gave: the question it stopped at, its reply, or its text."""
    if isinstance(found, Ask):
        return Result(line, said, asks=found.question, text=found.question)
    if found is None or isinstance(found, str):
        return Result(line, said, done=not dry_run, text=found)
    met = None if wait is None else wait.met(found)
    return Result(line, said, done=not dry_run, met=met, reply=found, text=str(found))


def _replied(found: object, cls: type[Command]) -> Seared:
    """What a waited-on handler returned, if it's its ``REPLY``: refused otherwise, as a wait reads its values."""
    reply = declaration(cls).reply
    if reply is None or not isinstance(found, reply):
        said = 'nothing' if found is None else f'a {type(found).__name__}'
        what = 'its REPLY' if reply is None else f'its REPLY ({reply.__name__})'
        msg = f"{cls.__qualname__}'s handler returned {said}: a wait reads {what}, so it returns one"
        raise TypeError(msg)
    return found


async def _woken(change: asyncio.Event, seconds: float) -> bool:
    """Wait for ``change``, at most ``seconds``: whether it came."""
    with contextlib.suppress(TimeoutError):
        async with asyncio.timeout(seconds):
            await change.wait()
    return change.is_set()


async def _awaited(found: object) -> object:
    """``found``, awaited if it's awaitable: what a sync or an async callable gave."""
    return await found if inspect.isawaitable(found) else found


def _looping() -> bool:
    """Whether an event loop is running in this thread."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _imported(path: str, cls: type) -> Handler:
    """The callable ``path`` names, imported: refused, naming the command, if it doesn't import or isn't one."""
    module, _, names = path.partition(':')
    said = f"{cls.__qualname__}'s handler {path!r}"
    try:
        found: object = importlib.import_module(module)
    except ImportError as e:
        msg = f"{said} doesn't import: {e}"
        raise ImportError(msg, name=module) from e
    for name in names.split('.'):
        try:
            found = getattr(found, name)
        except AttributeError:
            msg = f'{said}: {module} has no {names}'
            raise ImportError(msg, name=module) from None
    if not callable(found):
        msg = f'{said} is a {type(found).__name__}, not a callable'
        raise TypeError(msg)
    return found
