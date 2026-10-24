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

A line that gives ``--help`` runs nothing: it's answered with its command's usage, or, short of a command, with what
it may still say, each command's usage beneath where its words go. parsed's own flags may stand anywhere on a line.

**Whether a person is at a terminal** is the front end's to say: ``app.open(state, terminal=True)``. It's ``False``
by default, so a program that runs lines in-process needn't say so. Without one, a line that says an ``INTERACTIVE``
command is refused before its values are loaded or any hook runs, naming its ``INSTEAD`` (a ``refused`` error, exit
3); a handler reads it as ``ctx.terminal``, to give text where it would draw.

**Subjects** are the words a session tries before a bare line (``fleet prospector``, so ``mine`` reads as
``fleet prospector mine``): ``app.open(state, subjects=…)``, or ``session.use(…)``, from a handler too
(``ctx.session``). The line is read as typed first; only where its first word begins no command is each subject tried,
in turn, and the first whose words go on into it is the line's. They stay out of schemas and keys, as the instance a
line reads to is the same either way. ``app.walk``, ``app.read`` and ``app.complete`` take ``subjects=`` too.

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
import json
import re
import sys
from contextlib import AbstractAsyncContextManager, AbstractContextManager, AsyncExitStack
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, NamedTuple, cast, overload

# At runtime: tooling evaluates a class's annotations (`typing.get_type_hints`), and `Routed`'s name a `Reading`.
from ._walk import RESERVED, Completion, Reading, Routes, beneath, goes, split
from ._walk._complete import being_typed
from ._walk._terms import HELP, JSON
from ._walk._walker import _flag
from .argv import options_of
from .argv import read as read_args
from .command import Command, declaration, is_chain_base
from .errors import DeclarationError, ReadError, RefusedError, RenderError, TimedOutError
from .help import Entry, cleaned, listing, summary
from .help import command as command_help
from .kinds import spell_span
from .reply import CODES, Ask, Result
from .reply import terminal as ask_at_terminal
from .tree import Tree

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping, Sequence
    from types import TracebackType

    from seared import Seared

    from ._walk import Token
    from .context import Context
    from .names import Resolver
    from .reply import Answer
    from .tree import End
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
        options: The root options' class, a seared class whose fields are the flags before a command line's first
            word (``--config``), each optional; read once by :meth:`main`, and given to handlers as ``ctx.options``.
            ``None`` by default, for none.
        version: The program's version, as ``--version`` says it before the first word; ``None`` for none.

    Attributes:
        prog: The program's name.
        options: The root options' class, or ``None``.
        version: The program's version, or ``None``.

    Raises:
        DeclarationError: ``prog`` isn't a name; ``options`` isn't a seared class, or a field of it is required, has
            no word form, is read as a name, or takes a flag of parsed's; or ``version`` isn't a string.
    """

    def __init__(self, prog: str, *, options: type[Seared] | None = None, version: str | None = None) -> None:
        """An app with nothing mounted yet."""
        if not isinstance(prog, str) or not prog.strip():
            msg = f"App({prog!r}): prog is the program's name, as it's typed"
            raise DeclarationError(msg)
        self.prog = prog
        self._options = options_of(prog, options, version)
        self.options = self._options.cls
        self.version = version
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

    def mount(self, target: Tree | str, *, under: str = '', params: object = None, doc: str | None = None) -> Mount:
        """Mount ``target``'s commands under ``under``, a prefix of words, with ``params`` for their handlers.

        Args:
            target: A tree, or a module or package of commands by name, collected as ``Tree.collect`` does. A tree
                under a prefix of its own keeps it, beneath ``under``.
            under: The prefix its lines begin with (``'relay'``); none by default.
            params: What its handlers are given beside the command: a service's settings, say.
            doc: What it's for, as help says it on its namespace's line; by default its module's docstring (a
                tree's first command's).

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
        mounted = Mount(self, tree, source=source, params=params, doc=doc)
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

    def on_chain(self, base: type[Command], handler: Handler | str) -> None:
        """Bind ``handler`` to a chain, in every mount that holds its steps, unless the mount binds its own.

        It's called as ``handler(steps, ctx)``, ``steps`` the instance of each step the line says, in order. A lone
        step with no handler of its own runs by it too, as a chain of one.

        Args:
            base: The chain's base: the class that declares ``STEPS = True``.
            handler: A callable, or the path to one, as :meth:`on` takes it.

        Raises:
            DeclarationError: ``base`` isn't a chain's base, the handler isn't a callable or a path, or the chain
                has a handler bound here already.
        """
        self._bound.on_chain(base, handler)

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

        ``commands`` may name a chain's base, for the chains it runs.

        Raises:
            DeclarationError: ``hook`` isn't callable, or one of ``commands`` isn't a command class or a chain's base.
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
            command = isinstance(cls, type) and issubclass(cls, Command) and declaration(cls).is_command
            if not (command or is_chain_base(cls)):
                msg = f"{stage}(…, {cls!r}): a command class, with a PHRASE, or a chain's base"
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

    def chain_handler(self, base: type[Command]) -> Handler | None:
        """The handler bound to a chain by :meth:`on_chain`, imported from its path the first time; ``None`` if none.

        Raises:
            ImportError: Its path doesn't import, or names nothing in its module.
            TypeError: Its path names something that isn't callable.
        """
        return self._bound.chain_handler(base)

    @overload
    def open(
        self,
        state: None = None,
        *,
        verbosity: int = 0,
        answer: Answer | None = None,
        interval: float | None = 1.0,
        subjects: Sequence[str] = (),
        terminal: bool = False,
        options: Seared | None = None,
    ) -> Session[None]: ...
    @overload
    def open[S](
        self,
        state: AbstractAsyncContextManager[S],
        *,
        verbosity: int = 0,
        answer: Answer | None = None,
        interval: float | None = 1.0,
        subjects: Sequence[str] = (),
        terminal: bool = False,
        options: Seared | None = None,
    ) -> Session[S]: ...
    @overload
    def open[S](
        self,
        state: AbstractContextManager[S],
        *,
        verbosity: int = 0,
        answer: Answer | None = None,
        interval: float | None = 1.0,
        subjects: Sequence[str] = (),
        terminal: bool = False,
        options: Seared | None = None,
    ) -> Session[S]: ...
    @overload
    def open[S](
        self,
        state: S,
        *,
        verbosity: int = 0,
        answer: Answer | None = None,
        interval: float | None = 1.0,
        subjects: Sequence[str] = (),
        terminal: bool = False,
        options: Seared | None = None,
    ) -> Session[S]: ...
    def open(  # noqa: PLR0913 -- its state, and how its lines are said, answered, waited on, read and run
        self,
        state: object = None,
        *,
        verbosity: int = 0,
        answer: Answer | None = None,
        interval: float | None = 1.0,
        subjects: Sequence[str] = (),
        terminal: bool = False,
        options: Seared | None = None,
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
            subjects: The words tried before a bare line, in turn (``'fleet prospector'``); none by default.
            terminal: Whether a person is at a terminal (``ctx.terminal``): ``False`` by default, so a line that
                says an ``INTERACTIVE`` command is refused, naming its ``INSTEAD``.
            options: The root options (``ctx.options``), an instance of the app's options class; by default, each
                field's default, or ``None`` for an app with no options class.

        Raises:
            ValueError: ``interval`` isn't a positive number of seconds, or ``None``; or a subject isn't words a
                command begins with (:meth:`Session.use`).
            TypeError: ``terminal`` isn't ``True`` or ``False``, or ``options`` isn't the app's root options.
        """
        return Session(
            self,
            state,
            verbosity=verbosity,
            answer=answer,
            interval=interval,
            subjects=subjects,
            terminal=terminal,
            options=options,
        )

    def run(  # noqa: PLR0913 -- the line, its state, and how it's said, answered and waited on
        self,
        line: str,
        state: object = None,
        *,
        verbosity: int = 0,
        yes: bool = False,
        answer: Answer | None = None,
        interval: float | None = 1.0,
        subjects: Sequence[str] = (),
        terminal: bool = False,
        options: Seared | None = None,
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
            subjects: The words tried before a bare line, as :meth:`open` takes them.
            terminal: Whether a person is at a terminal, as :meth:`open` takes it.
            options: The root options, as :meth:`open` takes them.

        Raises:
            RuntimeError: It's called inside a running event loop.
            ValueError: As :meth:`open` raises it.
            TypeError: As :meth:`open` raises it.
        """
        if _looping():
            msg = 'app.run(line) runs an event loop of its own; inside one, open a session: async with app.open(state)'
            raise RuntimeError(msg)

        opened = self.open(
            state,
            verbosity=verbosity,
            answer=answer,
            interval=interval,
            subjects=subjects,
            terminal=terminal,
            options=options,
        )

        async def once() -> Result:
            async with opened as session:
                return await session.run(line, yes=yes)

        return asyncio.run(once())

    def main(
        self,
        argv: Sequence[str] | None = None,
        state: object = None,
        *,
        verbosity: int = 0,
        interval: float | None = 1.0,
        subjects: Sequence[str] = (),
    ) -> int:
        """Run a program's arguments as its command line, and give its exit code: ``sys.exit(app.main())``.

        The arguments are the root options, then a line (:mod:`parsed.argv`); parsed's own flags given among the
        root options are the line's. A person is at a terminal when stdin and stdout both are one, and there a
        question a line asks is put to them (``parsed.reply.terminal``). Each result's text is written as it comes (a
        watch's, each change): to stdout when it went well, else to stderr. With ``--json``, each result's envelope
        is a line of JSON on stdout instead (:meth:`Result.to_json`). ``--help`` with no words writes the program's
        usage above what it may say, and ``--version`` its version.

        Args:
            argv: The arguments, after the program's name: ``sys.argv[1:]`` by default.
            state: The app's state, as :meth:`open` takes it.
            verbosity: How much handlers should say, as :meth:`open` takes it.
            interval: How often a wait reads again, as :meth:`open` takes it.
            subjects: The words tried before a bare line, as :meth:`open` takes them.

        Raises:
            RuntimeError: It's called inside a running event loop.
        """
        if _looping():
            msg = 'app.main() runs an event loop of its own; inside one, open a session: async with app.open(state)'
            raise RuntimeError(msg)
        args = sys.argv[1:] if argv is None else list(argv)
        try:
            said = read_args(args, self._options)
        except ReadError as e:
            _report(_refused(' '.join(args), None, e), as_json=_asks_json(args))
            return CODES[e.kind]
        if said.version:
            _write(f'{self.prog} {self.version}', ok=True)
            return 0
        as_json = JSON in said.own or JSON in _own_given(said.line)
        if HELP in said.own and not said.line.strip() and not as_json:
            _write(self._options.help() + '\n', ok=True)  # the program's, above what it may say
        terminal = _at_terminal()
        opened = self.open(
            state,
            verbosity=verbosity,
            answer=ask_at_terminal if terminal else None,
            interval=interval,
            subjects=subjects,
            terminal=terminal,
            options=said.options,
        )

        async def each() -> int:
            code = 0
            async with opened as session, contextlib.aclosing(session.watch(said.run)) as results:
                async for result in results:
                    _report(result, as_json=as_json)
                    code = result.code
            return code

        try:
            return asyncio.run(each())
        except KeyboardInterrupt:
            return _INTERRUPTED

    def walk(self, line: str, *, subjects: Sequence[str] = (), placeholders: bool = False) -> Routed:
        """The mount ``line`` goes to, and what its tree reads the line to, with the mount's names.

        Args:
            line: The line.
            subjects: The words tried before a bare line, in turn (see the module): the line read as typed first.
            placeholders: Whether a ``<name>`` word stands for any value, as :meth:`Tree.walk` takes it.

        Raises:
            ReadError: The line reaches no mount, or its mount's tree refuses it.
            ValueError: A subject isn't words a command begins with.
        """
        return self._walk(line, self._subjects(subjects), placeholders=placeholders)

    def _walk(self, line: str, subjects: tuple[str, ...], *, placeholders: bool = False) -> Routed:
        said = self._said(line, subjects)
        mount = self._routes.route(said)
        return Routed(mount, mount.tree.walk(said, mount.resolvers, placeholders=placeholders))

    def read(self, line: str, *, subjects: Sequence[str] = ()) -> Command:
        """The command ``line`` says, loaded by seared, as :meth:`walk` routes and reads it.

        Raises:
            ReadError: As :meth:`walk` does, or a value seared refuses.
            ValueError: A subject isn't words a command begins with.
        """
        return self.walk(line, subjects=subjects).load()

    def complete(self, text: str, *, subjects: Sequence[str] = ()) -> Completion:
        """What may come next on ``text``, a line up to the cursor: its mount's tree's offers, or a prefix's words.

        With ``subjects``, a first word offers the commands' first words and then each subject's next words; after
        it, a line whose first word begins no command is completed under the subject that would read it.

        Raises:
            ValueError: A subject isn't words a command begins with.
        """
        return self._complete(text, self._subjects(subjects))

    def _complete(self, text: str, subjects: tuple[str, ...]) -> Completion:
        if not subjects:
            return self._offered(text)
        tokens, _ = being_typed(text)
        if tokens:
            return self._offered(self._said(text, subjects, partial=True))
        found = self._offered(text)
        words = list(found.words)
        for subject in subjects:
            words += [word for word in self._offered(f'{subject} {text}').words if word not in words]
        return Completion(words=words, replace=found.replace)

    def _offered(self, text: str) -> Completion:
        found = self._routes.complete(text)
        if isinstance(found, Mount):
            return found.tree.complete(text, found.resolvers)
        return found

    def subject_of(self, line: str, subjects: Sequence[str]) -> str | None:
        """The subject ``line`` reads under: ``None`` where it's read as typed (see the module).

        Raises:
            ValueError: A subject isn't words a command begins with.
        """
        return self._subject(line, self._subjects(subjects))

    def _listing(self, line: str, subjects: tuple[str, ...], *, terminal: bool) -> str | None:
        """What a line that asks for help may still say, where it stops short of a command (see :mod:`parsed.help`).

        Each mount beneath where its words go: a mount whose prefix they stop short of as its namespace's line, its
        prefix and its summary; any other by each command beneath, its usage and its summary. In the order they're
        mounted and declared. An ``INTERACTIVE`` command is left out when no one is at a terminal, or the line gives
        ``--json``; where that leaves nothing, each one's refusal is said instead. ``None`` for a line that doesn't
        ask, or whose words go nowhere.
        """
        said = self._said(line, subjects)
        try:
            tokens = split(said)
        except ReadError:
            return None
        flags = _before_dashes(tokens)
        if not any(_flag(token) == (HELP, None) for token in flags):
            return None
        everything = terminal and not any(_flag(token) == (JSON, None) for token in flags)
        entries, refused = self._entries(_routing(flags), tokens, said, everything=everything)
        if entries:
            return listing(entries)
        return '\n'.join(dict.fromkeys(refused)) or None

    def _entries(
        self, routing: list[Token], tokens: list[Token], said: str, *, everything: bool
    ) -> tuple[list[Entry], list[str]]:
        """A listing's entries, and the refusals of the interactive commands it left out (see :meth:`_listing`)."""
        entries: dict[str, Entry] = {}
        refused: list[str] = []
        for mount in self._routes.beneath(routing):
            if len(routing) < len(mount.under.split()):  # its prefix not yet said: its namespace's line
                if everything or any(not found.interactive for found in mount.tree.commands):
                    entries.setdefault(mount.under, Entry(f'{mount.under} …', mount.summary))
                continue
            for end in beneath(mount.tree, tokens) or ():
                if not everything and end.declaration.interactive:
                    refused.append(_for_a_person(mount, end, said).message)
                    continue
                usage = mount.tree.usage(end)
                entries.setdefault(usage, Entry(usage, summary(end.declaration.cls)))
        return list(entries.values()), refused

    def _help(self, routed: Routed) -> str:
        """The help a line that gives ``--help`` says, where it says a command: the command's, by the phrase it said."""
        end = routed.reading.end
        found = end.declaration
        instead = None if found.instead is None else _saying(routed.mount, found.instead).usage_of(found.instead)
        return command_help(routed.mount.tree, found.cls, phrase=found.phrases.index(end.bound), instead=instead)

    def _said(self, line: str, subjects: tuple[str, ...], *, partial: bool = False) -> str:
        """The line to read: ``line``, after the subject it reads under, if one."""
        subject = self._subject(line, subjects, partial=partial)
        return line if subject is None else f'{subject} {line}'

    def _subject(self, line: str, subjects: tuple[str, ...], *, partial: bool = False) -> str | None:
        """The first subject whose words go on into ``line``'s first word, where that word begins no command.

        parsed's own flags before the first word are passed over. A line whose words don't split is read as typed, to
        be refused.
        """
        if not subjects:
            return None
        try:
            tokens = being_typed(line)[0] if partial else split(line)
        except ReadError:
            return None
        first = next((token for token in tokens if not _is_own(token)), None)
        if first is None or _flag(first) is not None or self._routes.begins(first):
            return None
        return next((subject for subject in subjects if self._goes([*split(subject), first])), None)

    def _goes(self, tokens: list[Token]) -> bool:
        """Whether words go on in the app: along a mount's prefix, or into a mount whose tree takes them."""
        reached = self._routes.reach(tokens)
        return reached if isinstance(reached, bool) else goes(reached.tree, tokens)

    def _subjects(self, subjects: Sequence[str]) -> tuple[str, ...]:
        """``subjects``, checked: each words, no flag among them, that a command of the app begins with.

        Raises:
            ValueError: One isn't.
        """
        if isinstance(subjects, str):
            msg = f"subjects={subjects!r}: a sequence of subjects; one alone needs a trailing comma: ('…',)"
            raise ValueError(msg)  # noqa: TRY004 -- a value of the right type, said the wrong way
        checked: list[str] = []
        for subject in subjects:
            said = subject.strip() if isinstance(subject, str) else ''
            try:
                tokens = split(said)
            except ReadError as e:
                msg = f'subject {subject!r}: {e}'
                raise ValueError(msg) from None
            if not tokens or any(_flag(token) is not None or token.raw == '--' for token in tokens):
                msg = f"subject {subject!r}: a subject is words a line begins with, no flags: 'fleet prospector'"
                raise ValueError(msg)
            if not self._goes(tokens):
                msg = f'subject {subject!r}: no command of {self.prog} begins with its words'
                raise ValueError(msg)
            checked.append(said)
        return tuple(checked)

    def render(self, command: Command | Sequence[Command], *, mount: Mount | None = None) -> str:
        """The line that says ``command``, by its mount's tree, prefix and all.

        Args:
            command: An instance of a mounted command; or a chain's steps, said in the mount of its first.
            mount: The mount to say it in, where its command is mounted more than once.

        Raises:
            RenderError: Its command is mounted nowhere, more than once and ``mount`` doesn't say which, or not in
                ``mount``; or no phrase can say it; or the steps aren't one chain's (:meth:`Tree.render`).
        """
        if isinstance(command, (list, tuple)) and not command:
            msg = 'a chain has a step at least: no steps, no line'
            raise RenderError(msg)
        cls = type(command[0] if isinstance(command, (list, tuple)) else command)
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
        doc: What it's for: the ``doc`` it was mounted with, else its module's docstring; ``None`` for neither.
    """

    def __init__(self, app: App, tree: Tree, *, source: str, params: object, doc: str | None = None) -> None:
        """Hold the tree and its parameters; nothing bound yet."""
        self.app = app
        self.tree = tree
        self.source = source
        self.params = params
        self.doc = cleaned(doc) if doc is not None else cleaned(getattr(sys.modules.get(source), '__doc__', None))
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
    def summary(self) -> str | None:
        """The first line of its ``doc``, as help says it on its namespace's line; ``None`` for none."""
        return None if self.doc is None else self.doc.splitlines()[0]

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

    def on_chain(self, base: type[Command], handler: Handler | str) -> None:
        """Bind ``handler`` to a chain in this mount alone, over the app's, as :meth:`App.on_chain` takes it.

        Raises:
            DeclarationError: As :meth:`App.on_chain` does, or none of the chain's steps is one of the mount's.
        """
        if is_chain_base(base) and not any(found.chain is base for found in self.tree.commands):
            msg = (
                f"{self.label} has no step of {base.__qualname__}'s chain: bind it on the app, or on the mount that has"
            )
            raise DeclarationError(msg)
        self._bound.on_chain(base, handler)

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

    def chain_handler(self, base: type[Command]) -> Handler | None:
        """The handler a chain runs with in this mount: its own, else the app's; ``None`` if neither binds one.

        Raises:
            ImportError: Its path doesn't import, or names nothing in its module.
            TypeError: Its path names something that isn't callable.
        """
        own = self._bound.chain_handler(base)
        return own if own is not None else self.app.chain_handler(base)


class Session[S]:
    """An app, open: its state held for every line it calls, until it closes (see the module).

    Made by :meth:`App.open`, and used once, as ``async with app.open(state) as session``.

    Attributes:
        app: The app.
        verbosity: How much handlers should say: ``0`` by default, more for more.
        answer: What answers a question a line asks, when ``--yes`` doesn't; ``None`` leaves it unanswered.
        interval: How often, in seconds, a wait reads again when nothing has changed; ``None``: only on a change.
        terminal: Whether a person is at a terminal: without one, an ``INTERACTIVE`` command is refused.
        options: The root options: an instance of the app's options class, or ``None`` for an app with none.
    """

    def __init__(  # noqa: PLR0913 -- the app, its state, and how its lines are said, answered, waited on and read
        self,
        app: App,
        state: object,
        *,
        verbosity: int,
        answer: Answer | None,
        interval: float | None,
        subjects: Sequence[str] = (),
        terminal: bool = False,
        options: Seared | None = None,
    ) -> None:
        """Hold what to open; nothing is entered until the session opens.

        Raises:
            ValueError: ``interval`` isn't a positive number of seconds, or ``None``; or a subject isn't words a
                command begins with.
            TypeError: ``terminal`` isn't ``True`` or ``False``, or ``options`` isn't the app's root options.
        """
        if interval is not None and (
            isinstance(interval, bool) or not isinstance(interval, int | float) or interval <= 0
        ):
            msg = f'interval={interval!r}: how often a wait reads again, a positive number of seconds, or None'
            raise ValueError(msg)
        if not isinstance(terminal, bool):
            msg = f'terminal={terminal!r}: whether a person is at a terminal, True or False'
            raise TypeError(msg)
        declared = app.options
        if options is not None and (declared is None or not isinstance(options, declared)):
            want = (
                'the app has no root options: App(prog, options=…)'
                if declared is None
                else f"an instance of {declared.__qualname__}, the app's root options"
            )
            msg = f'options={options!r}: {want}'
            raise TypeError(msg)
        self.app = app
        self.verbosity = verbosity
        self.answer = answer
        self.interval = interval
        self.terminal = terminal
        self.options = options if options is not None else app._options.defaults()  # noqa: SLF001 -- the app's
        self._given = state
        self._state: Any = None
        self._stack: AsyncExitStack | None = None
        self._closed = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._change = asyncio.Event()
        self._subjects = app._subjects(subjects)  # noqa: SLF001 -- the session is the app's

    def __repr__(self) -> str:
        """The session, by its app and whether it's open."""
        stage = 'closed' if self._closed else 'open' if self._stack is not None else 'not yet open'
        return f'<Session of {self.app.prog}, {stage}>'

    @property
    def is_open(self) -> bool:
        """Whether it's open: entered, and not yet left."""
        return self._stack is not None

    @property
    def subjects(self) -> tuple[str, ...]:
        """The words tried before a bare line, in turn: the first whose words go on into it reads it."""
        return self._subjects

    def use(self, *subjects: str) -> None:
        """Make ``subjects`` the session's, in place of those it had; none, for none.

        A handler says it as ``ctx.session.use(f'fleet {command.fleet}')``: the lines after it read under them. The
        line as typed is read first, and each subject is tried only where its first word begins no command.

        Raises:
            ValueError: A subject isn't words, without a flag, that a command of the app begins with.
        """
        self._subjects = self.app._subjects(subjects)  # noqa: SLF001 -- the session is the app's

    def complete(self, text: str) -> Completion:
        """What may come next on ``text``, a line up to the cursor, as the app offers it with the session's subjects."""
        return self.app._complete(text, self._subjects)  # noqa: SLF001 -- the session is the app's

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
        ``asks``, with nothing done. ``yes`` answers every question yes, as ``--yes`` does. A wait says how long it
        waited (``waited``); past its bound, its error is a ``timeout``, exit 7, with its last reply. A line that
        watches gives its last result here; :meth:`watch` gives each.

        Raises:
            RuntimeError: The session isn't open.
        """
        last: Result | None = None
        async with contextlib.aclosing(self.watch(line, yes=yes)) as results:
            async for result in results:
                last = result
        return cast('Result', last)  # a line always comes to one result at least

    async def watch(self, line: str, *, yes: bool = False) -> AsyncGenerator[Result]:
        """Run ``line``, giving what came of it each time its reply changes: a result for each, as ``--watch`` asks.

        A line that watches gives its first reply, then one each time it changes, until its count, its bound, its
        conditions, or the task running it is cancelled (a signal, at a front end). Each result's ``to_json()`` is a
        line of a stream, for a tool that reads one (Claude Code's Monitor). Any other line gives its one result, as
        :meth:`run` does. Nothing the line or its handler does is raised: the last result says how it ended.

        Raises:
            RuntimeError: The session isn't open.
        """
        self._check_open()
        try:
            routed = self.app._walk(line, self._subjects)  # noqa: SLF001 -- the session is the app's
        except ReadError as e:
            listed = self.app._listing(line, self._subjects, terminal=self.terminal)  # noqa: SLF001
            said = self.app._said(line, self._subjects)  # noqa: SLF001
            yield _refused(line, None, e) if listed is None else Result(said, text=listed)
            return
        if 'help' in routed.reading.own:
            yield Result(routed.reading.line, routed.said, text=self.app._help(routed))  # noqa: SLF001
            return
        try:
            self._check_terminal(routed)
            steps = [step.load() for step in routed.reading.steps]
        except (RefusedError, ReadError) as e:
            yield _refused(line, routed.said, e)
            return
        try:
            async with contextlib.aclosing(self._handling(routed, steps, yes=yes)) as handling:
                async for found, waited in handling:
                    yield _outcome(routed, found, waited)
        except TimedOutError as e:
            yield _timed_out(routed, e)
        except Exception as e:  # noqa: BLE001 -- a handler's failure is the result's, never the caller's
            yield _failed(routed, e)

    async def call(self, line: str, *, yes: bool = False) -> object:
        """Run the command ``line`` says by its handler, with a fresh context, and give what the handler returns.

        The line goes to its mount and is loaded there (:meth:`App.walk`); its handler is the mount's, else the
        app's (:meth:`Mount.handler`), called as ``handler(command, ctx)`` and awaited if it's async. It returns its
        command's ``REPLY``, text or nothing, or asks first. A line that gives ``--help`` runs nothing: it gives the
        command's usage, or short of a command, the usage of each it may still say. With no one at a terminal, a line
        that says an ``INTERACTIVE`` command is refused before its values are loaded or any hook runs.

        A question is answered yes by ``--yes`` or ``yes``, else by the session's ``answer``; a yes runs what the
        handler asked to do, which may ask again. A question left unanswered, or answered no, is given back: the
        :class:`~parsed.reply.Ask` itself, with nothing done.

        Raises:
            RuntimeError: The session isn't open.
            ReadError: The line doesn't read.
            RefusedError: It says an ``INTERACTIVE`` command, and no one is at a terminal.
            LookupError: Its command has no handler.
            ImportError: Its handler's path doesn't import.
            TypeError: Its handler returned something besides its ``REPLY``, text, nothing or an ``Ask``.
            TimedOutError: A line that waits passed its bound before its reply met every condition: it carries the
                last reply, and how long it waited.
            Exception: Whatever its handler raises, or its answer.
        """
        self._check_open()
        try:
            routed = self.app._walk(line, self._subjects)  # noqa: SLF001 -- the session is the app's
        except ReadError:
            listed = self.app._listing(line, self._subjects, terminal=self.terminal)  # noqa: SLF001
            if listed is None:
                raise
            return listed
        if 'help' in routed.reading.own:
            return self.app._help(routed)  # noqa: SLF001
        self._check_terminal(routed)
        found: Seared | str | Ask | None = None
        steps = [step.load() for step in routed.reading.steps]
        async with contextlib.aclosing(self._handling(routed, steps, yes=yes)) as handling:
            async for each, _ in handling:
                found = each
        return found

    async def _handling(
        self, routed: Routed, steps: list[Command], *, yes: bool
    ) -> AsyncGenerator[tuple[Seared | str | Ask | None, float | None]]:
        """Call the line's handler between its hooks: what it came to, and for a watch each reply in turn.

        A command runs by its own handler; a chain, or a lone step with none of its own, by its chain's, given the
        steps. A line that waits reads until it's met, or refused past its bound, each with how long it had waited.
        """
        cls, handler, command = _handled_by(routed, steps)
        hooks, ctx = self.app.hooks(cls), self.context(routed)
        yes = yes or 'yes' in routed.reading.own

        async def read() -> Seared | str | Ask | None:
            found = _checked(await _awaited(handler(command, ctx)), cls)
            while isinstance(found, Ask) and (yes or await self._answered(found.question)):
                found = _checked(await _awaited(found.then()), cls)
            return found

        clock = asyncio.get_running_loop()
        try:
            for hook in hooks.before:
                await _awaited(hook(command, ctx))
            wait, change = routed.reading.wait, self._change  # the change held before the read, so none is missed
            started = clock.time()
            found = await read()
            if wait is None:
                yield found, None
            else:
                waiting = _Waiting(self, wait, read, cls, routed.said, started)
                async with contextlib.aclosing(waiting.replies(found, change)) as replies:
                    async for found in replies:
                        yield found, round(clock.time() - started, 3)
            for hook in hooks.after:
                await _awaited(hook(command, ctx, found))
        except Exception as error:
            for hook in hooks.on_error:
                await _awaited(hook(command, ctx, error))
            raise

    async def _answered(self, question: str) -> bool:
        """Whether the session's answer says yes to ``question``; no, with none."""
        if self.answer is None:
            return False
        return bool(await _awaited(self.answer(question)))

    def context(self, routed: Routed) -> Context[S]:
        """The context a line's handler is given, for ``routed``: this session, its mount and its reading."""
        from .context import Context  # here: the context's module imports this one

        return Context(self, routed.mount, routed.reading)

    def _check_terminal(self, routed: Routed) -> None:
        """Refuse a line that says a command for a person at a terminal, where none is: a chain's step among them."""
        if self.terminal:
            return
        for step in routed.reading.steps:
            if step.end.declaration.interactive:
                raise _for_a_person(routed.mount, step.end, routed.reading.line)

    def _check_open(self) -> None:
        if self._stack is None:
            msg = f'{self!r}: call lines inside `async with app.open(state) as session`'
            raise RuntimeError(msg)


@dataclass(slots=True)
class _Waiting:
    """A line's wait, as a session reads it: again on a change or the interval, until it's met, counted or bound."""

    session: Session[Any]
    wait: Wait
    read: Callable[[], Awaitable[Seared | str | Ask | None]]
    cls: type[Command]
    said: str
    started: float

    async def replies(self, found: Seared | str | Ask | None, change: asyncio.Event) -> AsyncGenerator[Seared | Ask]:
        """Each reply a watch gives as it changes, or the one a wait meets; the question, if one stops it.

        At the bound it stops, reading again only if a change woke it there. Conditions unmet at the bound are a
        :class:`~parsed.errors.TimedOutError`, carrying the last reply; a watch with none just ends.
        """
        wait, clock = self.wait, asyncio.get_running_loop()
        deadline = None if wait.timeout is None else self.started + wait.timeout
        shown, last, met = 0, None, False
        while True:
            if isinstance(found, Ask):
                yield found
                return
            reply = _replied(found, self.cls)
            wire = type(reply).dump(reply)
            if wait.watch and wire != last:
                yield reply
                shown, last = shown + 1, wire
            met = bool(wait.until) and wait.met(reply)
            if met or (wait.count is not None and shown >= wait.count):
                break
            if not await self._woken(change, deadline):
                break
            change, found = self.session._change, await self.read()  # noqa: SLF001 -- the session's own wait
        if wait.until and not met and (wait.count is None or shown < wait.count):
            unmet = ' and '.join(condition.text for condition in wait.until)
            bound = spell_span(cast('float', wait.timeout))
            msg = f'{self.said}: {unmet} not met within {bound}'
            raise TimedOutError(msg, reply=reply, waited=round(clock.time() - self.started, 3))
        if not wait.watch:
            yield reply

    async def _woken(self, change: asyncio.Event, deadline: float | None) -> bool:
        """Wait for a change, or the interval, short of the deadline: whether to read again."""
        clock, interval = asyncio.get_running_loop(), self.session.interval
        left = None if deadline is None else deadline - clock.time()
        if left is not None and left <= 0:
            return False
        seconds = left if interval is None else interval if left is None else min(left, interval)
        woke = await _woken(change, seconds)
        return woke or deadline is None or clock.time() < deadline


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
        phrase = self.reading.phrase
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
        self.chains: dict[type, _Handler] = {}
        self.names: dict[str, Resolver] = {}

    def on(self, cls: type[Command], handler: Handler | str) -> None:
        if not (isinstance(cls, type) and issubclass(cls, Command)) or not declaration(cls).is_command:
            msg = f'on({cls!r}, …): a command class, with a PHRASE'
            raise DeclarationError(msg)
        self._bind(self.handlers, cls, handler, 'on', 'a handler')

    def on_chain(self, base: type[Command], handler: Handler | str) -> None:
        if not is_chain_base(base):
            msg = f"on_chain({base!r}, …): a chain's base, without a PHRASE, declaring STEPS = True"
            raise DeclarationError(msg)
        self._bind(self.chains, base, handler, 'on_chain', "a chain's handler")

    def _bind(self, bound: dict[type, _Handler], cls: type, handler: Handler | str, verb: str, what: str) -> None:
        name = cls.__qualname__
        if isinstance(handler, str) and not _PATH.fullmatch(handler):
            msg = f"{verb}({name}, {handler!r}): a handler's path is a module and a name in it: 'pkg.module:function'"
            raise DeclarationError(msg)
        if not isinstance(handler, str) and not callable(handler):
            msg = f"{verb}({name}, {handler!r}): a handler is a callable, or the path to one: 'pkg.module:function'"
            raise DeclarationError(msg)
        if cls in bound:
            msg = f'{name} has {what}{self._here()} already: bind one once'
            raise DeclarationError(msg)
        bound[cls] = _Handler(handler)

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

    def chain_handler(self, base: type) -> Handler | None:
        found = self.chains.get(base)
        return None if found is None else found.resolve(base)

    def _here(self) -> str:
        return f' in {self.where}' if self.where else ''


def _handled_by(routed: Routed, steps: list[Command]) -> tuple[type[Command], Handler, Command | list[Command]]:
    """Who runs a line, and with what: its class, its handler, and the command or a chain's steps.

    A command runs by its own handler. A chain, or a lone step with no handler of its own, runs by its chain's, and
    the chain's base stands for it to its hooks and its reply.

    Raises:
        LookupError: Nothing is bound to run it.
    """
    cls, chain, mount = routed.command, routed.reading.chain, routed.mount
    own = None if len(steps) > 1 else mount.handler(cls)
    if own is not None:
        return cls, own, steps[0]
    chained = None if chain is None else mount.chain_handler(chain)
    if chain is not None and chained is not None:
        return chain, chained, steps
    if chain is None:
        msg = f'{cls.__qualname__} has no handler in {mount.label}: bind one with app.on'
    elif len(steps) > 1:
        msg = f"{chain.__qualname__}'s chain has no handler in {mount.label}: bind one with app.on_chain"
    else:
        msg = (
            f"{cls.__qualname__} has no handler in {mount.label}, nor has {chain.__qualname__}'s chain: bind one with "
            f'app.on, or app.on_chain'
        )
    raise LookupError(msg)


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


def _outcome(routed: Routed, found: Seared | str | Ask | None, waited: float | None) -> Result:
    """What a line came to, from what its handler gave: the question it stopped at, its reply, or its text."""
    line, said, wait = routed.reading.line, routed.said, routed.reading.wait
    done = 'dry-run' not in routed.reading.own
    if isinstance(found, Ask):
        return Result(line, said, asks=found.question, waited=waited, text=found.question)
    if found is None or isinstance(found, str):
        return Result(line, said, done=done, text=found)
    met = None if wait is None or not wait.until else wait.met(found)
    return Result(line, said, done=done, met=met, waited=waited, reply=found, text=str(found))


def _for_a_person(mount: Mount, end: End, line: str) -> RefusedError:
    """The refusal of a command for a person at a terminal: its phrase, and what's said in its place, if anything."""
    message = f'{_under(mount.tree, end.bound.phrase.text)} is for a person at a terminal'
    instead = end.declaration.instead
    if instead is None:
        return RefusedError(message, line=line)
    tree = _saying(mount, instead)
    said = _under(tree, cast('str', declaration(instead).phrase))
    return RefusedError(f'{message}: say `{tree.usage_of(instead)}` instead', line=line, instead=said)


def _saying(mount: Mount, cls: type[Command]) -> Tree:
    """The tree that says ``cls`` for a line gone to ``mount``: the mount's, else the first that holds it, else its own.

    Its own is a tree of it alone, so its phrase is said with no prefix.
    """
    held = mount if mount.holds(cls) else next((other for other in mount.app.mounts if other.holds(cls)), None)
    return held.tree if held is not None else Tree((cls,))


def _under(tree: Tree, phrase: str) -> str:
    """A phrase after its tree's prefix."""
    return f'{tree.under} {phrase}' if tree.under else phrase


def _refused(line: str, said: str | None, error: ReadError | RefusedError) -> Result:
    """A line refused: one that doesn't read, a value its field refuses, or a command for a person at a terminal."""
    return Result(error.line or line, said, ok=False, text=str(error), error=error.to_json(), exception=error)


def _timed_out(routed: Routed, error: TimedOutError) -> Result:
    """A wait past its bound: the last reply, ``met`` false, and a ``timeout`` error, exit 7."""
    return Result(
        routed.reading.line,
        routed.said,
        ok=False,
        done=True,
        met=False,
        waited=error.waited,
        reply=error.reply,
        text=error.message,
        error={'error': 'timeout', 'message': error.message},
        exception=error,
    )


def _failed(routed: Routed, error: Exception) -> Result:
    """A handler that failed: its exception, named, as the result's ``handler`` error."""
    message = f'{type(error).__name__}: {error}' if str(error) else type(error).__name__
    error_data = {'error': 'handler', 'message': message}
    return Result(routed.reading.line, routed.said, ok=False, text=message, error=error_data, exception=error)


def _replied(found: object, cls: type[Command]) -> Seared:
    """What a waited-on handler returned, if it's its ``REPLY``: refused otherwise, as a wait reads its values."""
    reply = declaration(cls).reply
    if reply is None or not isinstance(found, reply):
        said = 'nothing' if found is None else f'a {type(found).__name__}'
        what = 'its REPLY' if reply is None else f'its REPLY ({reply.__name__})'
        msg = f"{cls.__qualname__}'s handler returned {said}: a wait reads {what}, so it returns one"
        raise TypeError(msg)
    return found


async def _woken(change: asyncio.Event, seconds: float | None) -> bool:
    """Wait for ``change``, at most ``seconds`` (``None``: as long as it takes): whether it came."""
    with contextlib.suppress(TimeoutError):
        async with asyncio.timeout(seconds):
            await change.wait()
    return change.is_set()


async def _awaited(found: object) -> object:
    """``found``, awaited if it's awaitable: what a sync or an async callable gave."""
    return await found if inspect.isawaitable(found) else found


#: The exit code of a program stopped by an interrupt (Ctrl-C), as a shell gives it: 128 and ``SIGINT``.
_INTERRUPTED = 130


def _routing(flags: list[Token]) -> list[Token]:
    """The words a line's mount is found by: up to a field's flag, parsed's own passed over, as the routes read them."""
    found: list[Token] = []
    for token in flags:
        if _flag(token) is not None and not _is_own(token):
            break
        if not _is_own(token):
            found.append(token)
    return found


def _before_dashes(tokens: list[Token]) -> list[Token]:
    """A line's words up to ``--``, after which none is a flag."""
    ends = next((at for at, token in enumerate(tokens) if token.raw == '--'), len(tokens))
    return tokens[:ends]


def _is_own(token: Token) -> bool:
    """Whether ``token`` is one of parsed's own flags: ``--help`` (``-h``), ``--json``, ``--yes`` or ``--dry-run``."""
    found = _flag(token)
    return found is not None and found[0] in RESERVED


def _own_given(line: str) -> frozenset[str]:
    """The flags of parsed's own a line gives, by name; none for a line whose words don't split."""
    try:
        tokens = split(line)
    except ReadError:
        return frozenset()
    return frozenset(cast('tuple[str, None]', _flag(token))[0] for token in _before_dashes(tokens) if _is_own(token))


def _asks_json(args: Sequence[str]) -> bool:
    """Whether a program's arguments give ``--json``, before any ``--``: for a refusal before the line is read."""
    ends = args.index('--') if '--' in args else len(args)
    return f'--{JSON}' in args[:ends]


def _report(result: Result, *, as_json: bool) -> None:
    """Write what came of a line: its envelope as a line of JSON on stdout, or its text, for people."""
    if as_json:
        _write(json.dumps(result.to_json()), ok=True)
    elif result.text is not None:
        _write(result.text, ok=result.ok)


def _write(text: str, *, ok: bool) -> None:
    """Write a line for people: to stdout when it went well, else to stderr, at once."""
    stream = sys.stdout if ok else sys.stderr
    stream.write(text + '\n')
    stream.flush()


def _at_terminal() -> bool:
    """Whether a person is at a terminal: whether stdin and stdout both are one."""
    return all(stream is not None and stream.isatty() for stream in (sys.stdin, sys.stdout))


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
