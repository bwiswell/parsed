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

**A session runs lines** against the app's state: ``async with app.open(state) as session``, then
``await session.call(line)``. A state that opens and closes (a context manager, as a link to a server is) is entered
when the session opens and left when it closes, and handlers see what entering it gave. Each line's handler is
called as ``handler(command, ctx)``, ``ctx`` a fresh :class:`~parsed.context.Context`, and awaited if it's async.
"""

from __future__ import annotations

import importlib
import inspect
import re
from contextlib import AbstractAsyncContextManager, AbstractContextManager, AsyncExitStack
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, overload

# At runtime: tooling evaluates a class's annotations (`typing.get_type_hints`), and `Routed`'s name a `Reading`.
from ._walk import Reading, Routes
from .command import Command, declaration
from .errors import DeclarationError, RenderError
from .tree import Tree

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from types import TracebackType

    from ._walk import Completion
    from .context import Context
    from .names import Resolver

#: What a command runs with: a callable, given the command and its context (``handler(command, ctx)``), whose result
#: is awaited if it's awaitable.
type Handler = Callable[..., object]

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

    def handler(self, cls: type[Command]) -> Handler | None:
        """The handler bound to ``cls`` by :meth:`on`, imported from its path the first time; ``None`` if none is.

        A mount's own is :meth:`Mount.handler`'s.

        Raises:
            ImportError: Its path doesn't import, or names nothing in its module.
            TypeError: Its path names something that isn't callable.
        """
        return self._bound.handler(cls)

    @overload
    def open(self, state: None = None, *, verbosity: int = 0) -> Session[None]: ...
    @overload
    def open[S](self, state: AbstractAsyncContextManager[S], *, verbosity: int = 0) -> Session[S]: ...
    @overload
    def open[S](self, state: AbstractContextManager[S], *, verbosity: int = 0) -> Session[S]: ...
    @overload
    def open[S](self, state: S, *, verbosity: int = 0) -> Session[S]: ...
    def open(self, state: object = None, *, verbosity: int = 0) -> Session[Any]:
        """A session of the app, to run lines against ``state``: ``async with app.open(state) as session``.

        Args:
            state: What handlers are given as ``ctx.state``: the app's own (a link, a mirror). A context manager,
                sync or async, is entered when the session opens, and its handlers see what entering it gave; it's
                left when the session closes. ``None`` by default, for an app with no state.
            verbosity: How much handlers should say (``ctx.verbosity``): ``0`` by default, more for more.
        """
        return Session(self, state, verbosity=verbosity)

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
    """

    def __init__(self, app: App, state: object, *, verbosity: int) -> None:
        """Hold what to open; nothing is entered until the session opens."""
        self.app = app
        self.verbosity = verbosity
        self._given = state
        self._state: Any = None
        self._stack: AsyncExitStack | None = None
        self._closed = False

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
        self._stack = stack
        return self

    async def __aexit__(
        self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None
    ) -> bool:
        """Close: leave the state, if it was entered, telling it of any error the session's body raised."""
        stack, self._stack, self._closed = self._stack, None, True
        if stack is None:
            return False
        return bool(await stack.__aexit__(kind, error, traceback))

    async def call(self, line: str) -> object:
        """Run the command ``line`` says by its handler, with a fresh context, and give what the handler returns.

        The line goes to its mount and is loaded there (:meth:`App.walk`); its handler is the mount's, else the
        app's (:meth:`Mount.handler`), called as ``handler(command, ctx)`` and awaited if it's async.

        Raises:
            RuntimeError: The session isn't open.
            ReadError: The line doesn't read.
            LookupError: Its command has no handler.
            ImportError: Its handler's path doesn't import.
            Exception: Whatever its handler raises.
        """
        self._check_open()
        routed = self.app.walk(line)
        command = routed.load()
        handler = routed.mount.handler(routed.command)
        if handler is None:
            msg = f'{routed.command.__qualname__} has no handler in {routed.mount.label}: bind one with app.on'
            raise LookupError(msg)
        found = handler(command, self.context(routed))
        return await found if inspect.isawaitable(found) else found

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
