"""Tests for ``parsed/app.py``: an app's mounts, the handlers their commands run with, and the names it reads with."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import _support_farlandia as farlandia
import _support_handlers as handlers
import _support_service as service
import pytest

import parsed
from parsed._walk import Completion
from parsed.app import App, Mount, Routed
from parsed.doc import command_key, load_chain
from parsed.errors import DeclarationError, ReadError, RefusedError, RenderError
from parsed.tree import Tree

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def app() -> App:
    """The terminal game's commands at the root, and a service's skeleton twice, each with its own settings."""
    found = App('farlandia')
    found.names('fleet', farlandia.NAMES['fleet'])
    found.mount('_support_farlandia')
    found.mount('_support_service', under='relay', params=service.RelaySettings())
    found.mount(Tree.collect('_support_service'), under='gateway', params=service.GatewaySettings())
    return found


def _mount(app: App, under: str) -> Mount:
    return next(found for found in app.mounts if found.under == under)


class TestTheApp:
    def test_its_program_and_its_mounts_in_order(self, app):
        assert app.prog == 'farlandia'
        assert [found.under for found in app.mounts] == ['', 'relay', 'gateway']

    @pytest.mark.parametrize('prog', ['', '  ', 3])
    def test_a_program_needs_a_name(self, prog):
        with pytest.raises(DeclarationError, match=r"prog is the program's name"):
            App(prog)

    def test_exported(self):
        assert parsed.App is App


class TestMounting:
    def test_a_package_by_name(self, app):
        relay = _mount(app, 'relay')
        assert relay.tree.under == 'relay'
        assert (relay.source, relay.label) == ('_support_service', "_support_service under 'relay'")
        assert repr(relay) == "<Mount _support_service under 'relay'>"
        assert _mount(app, '').label == '_support_farlandia at the root'

    def test_a_tree_as_it_is_at_the_root(self):
        tree = Tree.collect('_support_farlandia')
        assert App('farm').mount(tree).tree is tree

    def test_a_tree_s_own_prefix_kept_beneath(self):
        mounted = App('rio').mount(Tree.collect('_support_service', under='relay'), under='rio')
        assert mounted.under == 'rio relay'
        assert mounted.source == '_support_service'

    def test_each_mount_with_its_own_params(self, app):
        assert _mount(app, 'relay').params == service.RelaySettings()
        assert _mount(app, 'gateway').params == service.GatewaySettings()
        assert _mount(app, '').params is None

    def test_a_line_that_would_read_two_ways_names_both_mounts(self, app):
        pattern = r"_support_service under 'relay' and _support_service under 'relay' both say 'relay run'"
        with pytest.raises(DeclarationError, match=pattern):
            app.mount('_support_service', under='relay')
        assert len(app.mounts) == 3  # nothing mounted

    def test_not_a_tree_or_a_name(self):
        with pytest.raises(DeclarationError, match=r'mount\(3\): a tree, or a module or package of commands by name'):
            App('farm').mount(3)  # ty: ignore[invalid-argument-type] -- the refusal under test

    def test_a_module_that_doesn_t_import(self):
        with pytest.raises(ImportError):
            App('farm').mount('_support_nowhere')

    def test_a_prefix_that_isn_t_words(self):
        with pytest.raises(DeclarationError, match=r"under='Relay': 'Relay' is not a word"):
            App('farm').mount('_support_service', under='Relay')


class TestReading:
    def test_a_line_goes_to_its_mount(self, app):
        found = app.walk('relay run --config c.toml --yes')
        assert isinstance(found, Routed)
        assert found.mount is _mount(app, 'relay')
        assert found.command is service.Run
        assert found.reading.own == {'yes'}
        assert found.load() == service.Run(config=Path('c.toml'))

    def test_read_goes_on_to_the_instance(self, app):
        assert app.read('gateway status') == service.Status()
        assert app.read('fleet f1 mine --for 90s') == farlandia.FleetMine(fleet='f1', for_=timedelta(seconds=90))

    def test_placeholders_when_asked(self, app):
        assert app.walk('relay run --config <config>', placeholders=True).reading.data() == {'config': '<config>'}

    @pytest.mark.parametrize(
        ('line', 'says'),
        [
            ('rela run', "no command 'rela'; did you mean relay?"),
            ('relay', 'relay: then what? run | validate-config | status'),
            ('relay run --port 1', 'no command takes --port'),  # past its words, the mount's tree reads it
        ],
    )
    def test_a_line_that_doesn_t_read(self, app, line, says):
        with pytest.raises(ReadError) as caught:
            app.read(line)
        assert str(caught.value).startswith(says)

    def test_complete_by_its_mount_or_a_prefix(self, app):
        assert app.complete('rel') == (['relay'], 3)
        assert app.complete('relay ').words == ['run', 'validate-config', 'status']
        assert app.complete('relay run --c') == (['--config'], 3)
        assert app.complete('fleet ').words == ['Prospector', 'Hauler']  # the app's names
        assert app.complete('').words[-2:] == ['relay', 'gateway']


@parsed.parsed
class Hail(parsed.Command):
    """A command no app here mounts."""

    PHRASE = 'hail'


class TestRendering:
    def test_by_its_one_mount(self, app):
        assert app.render(farlandia.FleetDock(fleet='f1')) == 'fleet f1 dock'

    def test_with_the_mount_s_names(self, app):
        # A detachment's key is said by its twin, as only the names tell.
        app.names('detachment', farlandia.NAMES['detachment'])
        assert app.render(farlandia.FleetMine(fleet='d2')) == 'detachment d2 mine'

    def test_a_command_mounted_twice_needs_its_mount(self, app):
        pattern = r"Run is mounted 2 times \(_support_service under 'relay', _support_service under 'gateway'\)"
        with pytest.raises(RenderError, match=pattern):
            app.render(service.Run())
        assert app.render(service.Run(), mount=_mount(app, 'gateway')) == 'gateway run'

    def test_a_command_mounted_nowhere(self, app):
        with pytest.raises(RenderError, match=r'Hail is mounted nowhere in farlandia'):
            app.render(Hail())

    def test_a_mount_that_doesn_t_hold_it(self, app):
        with pytest.raises(RenderError, match=r"Log is not mounted in _support_service under 'relay'"):
            app.render(farlandia.Log(), mount=_mount(app, 'relay'))

    def test_a_chain_s_steps_by_its_first_s_mount(self, app):
        steps = [farlandia.FleetJump(fleet='f1', system='sol'), farlandia.FleetMine(fleet='f1')]
        assert app.render(steps) == 'fleet f1 jump sol then mine'
        with pytest.raises(RenderError, match=r'a chain has a step at least'):
            app.render([])

    def test_a_mount_of_another_app(self, app):
        other = App('other').mount('_support_service')
        with pytest.raises(RenderError, match=r'Run is not mounted in _support_service at the root'):
            app.render(service.Run(), mount=other)


class TestHandlers:
    def test_bound_on_the_app_for_every_mount(self, app):
        app.on(service.Run, handlers.run)
        assert _mount(app, 'relay').handler(service.Run) is handlers.run
        assert _mount(app, 'gateway').handler(service.Run) is handlers.run
        assert app.handler(service.Run) is handlers.run

    def test_a_mount_s_own_wins_there(self, app):
        app.on(service.Run, handlers.run)
        _mount(app, 'gateway').on(service.Run, handlers.Service.status)
        assert _mount(app, 'gateway').handler(service.Run) is handlers.Service.status
        assert _mount(app, 'relay').handler(service.Run) is handlers.run

    def test_none_when_none_is_bound(self, app):
        assert _mount(app, 'relay').handler(service.Status) is None
        assert app.handler(service.Status) is None

    def test_a_path_imported_when_it_s_first_looked_up(self, app, monkeypatch):
        monkeypatch.delitem(sys.modules, '_support_handlers')
        app.on(service.Run, '_support_handlers:run')
        _mount(app, 'gateway').on(service.Run, '_support_handlers:Service.status')
        assert '_support_handlers' not in sys.modules
        ran = _mount(app, 'relay').handler(service.Run)
        assert '_support_handlers' in sys.modules
        assert ran is not None
        assert ran(service.Run(), None) == 'ran Run(config=None)'
        assert app.handler(service.Run) is ran  # imported once
        assert _mount(app, 'gateway').handler(service.Run)(service.Run(), None) == 'status of Run(config=None)'

    @pytest.mark.parametrize(
        ('path', 'error', 'message'),
        [
            ('_support_nowhere:run', ImportError, r"Run's handler '_support_nowhere:run' doesn't import: No module"),
            ('_support_handlers:walk', ImportError, r"Run's handler '_support_handlers:walk': _support_handlers has"),
            ('_support_handlers:COUNT', TypeError, r"Run's handler '_support_handlers:COUNT' is a int, not a callable"),
        ],
    )
    def test_a_path_that_names_no_handler(self, app, path, error, message):
        app.on(service.Run, path)
        with pytest.raises(error, match=message):
            app.handler(service.Run)

    @pytest.mark.parametrize(
        ('cls', 'handler', 'message'),
        [
            (service.Run, 'handlers.run', r"on\(Run, 'handlers.run'\): a handler's path is a module and a name in it"),
            (service.Run, 'a:b c', r"a handler's path is a module and a name in it: 'pkg.module:function'"),
            (service.Run, 3, r'on\(Run, 3\): a handler is a callable, or the path to one'),
            (service.ServiceCommand, handlers.run, r'on\(.*ServiceCommand.*, …\): a command class, with a PHRASE'),
            (service.RelaySettings, handlers.run, r'on\(.*RelaySettings.*, …\): a command class'),
            ('run', handlers.run, r"on\('run', …\): a command class"),
        ],
    )
    def test_refused_when_bound(self, app, cls, handler, message):
        with pytest.raises(DeclarationError, match=message):
            app.on(cls, handler)

    def test_bound_once(self, app):
        app.on(service.Run, handlers.run)
        with pytest.raises(DeclarationError, match=r'Run has a handler already: bind one once'):
            app.on(service.Run, handlers.run)
        relay = _mount(app, 'relay')
        relay.on(service.Run, handlers.run)
        with pytest.raises(DeclarationError, match=r"Run has a handler in _support_service under 'relay' already"):
            relay.on(service.Run, handlers.run)

    def test_a_mount_binds_only_its_own_commands(self, app):
        with pytest.raises(DeclarationError, match=r"_support_service under 'relay' has no Log: bind it on the app"):
            _mount(app, 'relay').on(farlandia.Log, handlers.run)


class _Fleets:
    """A resolver that knows one fleet, by another name than the fixture's."""

    def lookup(self, word, scope):
        return 'f9' if word.lower() == 'flagship' else None

    def suggest(self, word, scope):
        return []

    def options(self, scope):
        return ['Flagship']


class TestNames:
    def test_the_app_s_in_every_mount(self, app):
        assert app.read('fleet Prospector mine').fleet == 'f1'
        assert dict(app.resolvers) == {'fleet': farlandia.NAMES['fleet']}
        assert dict(_mount(app, 'relay').resolvers) == {'fleet': farlandia.NAMES['fleet']}

    def test_a_mount_s_own_wins_there(self, app):
        _mount(app, '').names('fleet', _Fleets())
        assert app.read('fleet Flagship mine').fleet == 'f9'
        assert app.complete('fleet ').words == ['Flagship']
        assert _mount(app, 'relay').resolvers['fleet'] is farlandia.NAMES['fleet']

    def test_given_after_mounting_too(self, app):
        app.names('station', farlandia.NAMES['station'])
        assert app.read('fleet f1 dock vesta').station == 'vesta'

    @pytest.mark.parametrize(
        ('category', 'resolver', 'message'),
        [
            ('a fleet', _Fleets(), r"names\('a fleet', …\): a category is a name"),
            ('station', object(), r"names\('station', <object .*>\): a resolver has lookup, suggest and options"),
            ('fleet', _Fleets(), r'fleet has a resolver already: give one once'),
        ],
    )
    def test_refused(self, app, category, resolver, message):
        with pytest.raises(DeclarationError, match=message):
            app.names(category, resolver)

    def test_a_mount_gives_one_once(self, app):
        relay = _mount(app, 'relay')
        relay.names('fleet', _Fleets())
        with pytest.raises(DeclarationError, match=r"fleet has a resolver in _support_service under 'relay' already"):
            relay.names('fleet', _Fleets())


class _Link:
    """A state that opens and closes, as a link to a server does: it keeps what happened to it."""

    def __init__(self) -> None:
        self.happened: list[object] = []

    async def __aenter__(self) -> dict[str, str]:
        self.happened.append('opened')
        return {'link': 'up'}

    async def __aexit__(self, kind, error, traceback) -> bool:
        self.happened.append(('closed', kind))
        return False


class _File:
    """A state that opens and closes, synchronously."""

    def __init__(self) -> None:
        self.happened: list[str] = []

    def __enter__(self) -> str:
        self.happened.append('opened')
        return 'contents'

    def __exit__(self, kind, error, traceback) -> bool:
        self.happened.append('closed')
        return False


class TestSessions:
    async def test_a_state_held_while_it_s_open(self, app):
        state = object()
        session = app.open(state)
        assert not session.is_open
        async with session as opened:
            assert opened is session
            assert session.is_open
            assert session.state is state
        assert not session.is_open

    async def test_a_state_that_opens_and_closes_is_entered_and_left(self, app):
        link = _Link()
        async with app.open(link) as session:
            assert session.state == {'link': 'up'}  # what entering it gave
            assert link.happened == ['opened']
        assert link.happened == ['opened', ('closed', None)]

    async def test_a_sync_one_too(self, app):
        file = _File()
        async with app.open(file) as session:
            assert session.state == 'contents'
        assert file.happened == ['opened', 'closed']

    async def test_left_with_the_error_its_body_raised(self, app):
        link = _Link()
        with pytest.raises(ValueError, match='boom'):
            async with app.open(link):
                msg = 'boom'
                raise ValueError(msg)
        assert link.happened == ['opened', ('closed', ValueError)]

    async def test_none_for_an_app_with_no_state(self, app):
        async with app.open() as session:
            assert session.state is None
            assert session.verbosity == 0

    async def test_its_verbosity(self, app):
        async with app.open(verbosity=2) as session:
            assert session.verbosity == 2

    async def test_opened_once(self, app):
        session = app.open()
        async with session:
            pass
        with pytest.raises(RuntimeError, match=r'<Session of farlandia, closed> opens once: open another'):
            async with session:
                pass

    async def test_its_state_only_while_it_s_open(self, app):
        session = app.open(3)
        with pytest.raises(RuntimeError, match=r'not yet open>: call lines inside `async with app.open'):
            _ = session.state

    async def test_sessions_are_apart(self, app):
        async with app.open('one') as one, app.open('two') as two:
            assert (one.state, two.state) == ('one', 'two')

    def test_said_by_its_app_and_its_stage(self, app):
        assert repr(app.open()) == '<Session of farlandia, not yet open>'


class _Recorder:
    """A handler that keeps each command and context it's given, and returns nothing."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, parsed.Context]] = []

    def __call__(self, command, ctx) -> None:
        self.calls.append((command, ctx))


class _AsyncRecorder(_Recorder):
    """The same, as a coroutine."""

    async def __call__(self, command, ctx) -> None:
        await asyncio.sleep(0)
        self.calls.append((command, ctx))


class TestCalling:
    async def test_a_line_runs_by_its_handler_with_its_context(self, app):
        recorder = _Recorder()
        app.on(farlandia.FleetMine, recorder)
        async with app.open('state') as session:
            assert await session.call('fleet Prospector mine --for 90s') is None
            ((command, ctx),) = recorder.calls
            assert command == farlandia.FleetMine(fleet='f1', for_=timedelta(seconds=90))
            assert isinstance(ctx, parsed.Context)
            assert (ctx.session, ctx.state, ctx.mount) == (session, 'state', _mount(app, ''))
        with pytest.raises(RuntimeError, match=r'closed>: call lines inside'):
            _ = ctx.state  # left when the session closed

    async def test_an_async_handler_awaited(self, app):
        recorder = _AsyncRecorder()
        app.on(service.Run, recorder)
        async with app.open() as session:
            assert await session.call('relay run --config c.toml') is None
        ((command, ctx),) = recorder.calls
        assert command == service.Run(config=Path('c.toml'))
        assert ctx.params == service.RelaySettings()

    async def test_by_the_mount_s_handler(self, app):
        recorder = _Recorder()
        app.on(service.Run, recorder)
        _mount(app, 'gateway').on(service.Run, handlers.Service.status)
        async with app.open() as session:
            assert await session.call('gateway run') == 'status of Run(config=None)'
            assert await session.call('relay run') is None
        assert [command for command, _ in recorder.calls] == [service.Run()]

    async def test_a_handler_by_its_path(self, app):
        app.on(service.Status, '_support_handlers:run')
        async with app.open() as session:
            assert await session.call('relay status') == 'ran Status(config=None)'

    async def test_a_command_with_no_handler(self, app):
        async with app.open() as session:
            with pytest.raises(LookupError, match=r"Status has no handler in _support_service under 'relay': bind one"):
                await session.call('relay status')

    async def test_a_line_that_doesn_t_read(self, app):
        async with app.open() as session:
            with pytest.raises(ReadError, match=r"no command 'rela'; did you mean relay\?"):
                await session.call('rela run')

    async def test_what_its_handler_raises(self, app):
        def broken(command, ctx):
            raise KeyError(command)

        app.on(service.Run, broken)
        async with app.open() as session:
            with pytest.raises(KeyError):
                await session.call('relay run')

    async def test_only_while_it_s_open(self, app):
        session = app.open()
        async with session:
            pass
        with pytest.raises(RuntimeError, match=r'closed>: call lines inside `async with app.open\(state\) as session`'):
            await session.call('relay run')


def _shown(command, ctx):
    return farlandia.FleetView(fleet=command.fleet, docked=True)


def _said(command, ctx):
    return f'{command.fleet} mines'


class TestRunning:
    @pytest.fixture
    def bound(self, app) -> App:
        app.on(farlandia.FleetsShow, _shown)
        app.on(farlandia.FleetMine, _said)
        return app

    async def _run(self, app: App, line: str):
        async with app.open() as session:
            return await session.run(line)

    async def test_a_reply(self, bound):
        found = await self._run(bound, 'fleets show f1')
        assert found == parsed.Result(
            'fleets show f1',
            'fleets show {fleet}',
            done=True,
            reply=farlandia.FleetView(fleet='f1', docked=True),
            text="FleetView(fleet='f1', docked=True)",
        )
        assert found.code == 0

    async def test_text(self, bound):
        found = await self._run(bound, 'fleet f1 mine')
        assert (found.ok, found.done, found.reply, found.text) == (True, True, None, 'f1 mines')

    async def test_nothing(self, app):
        app.on(service.Run, lambda command, ctx: None)
        found = await self._run(app, 'relay run')
        assert (found.command, found.ok, found.done, found.text) == ('relay run', True, True, None)

    async def test_a_dry_run_is_not_done(self, bound):
        found = await self._run(bound, 'fleet f1 mine --dry-run')
        assert (found.ok, found.done, found.text) == (True, False, 'f1 mines')

    async def test_help_runs_nothing(self, bound):
        found = await self._run(bound, 'relay run --help')
        assert found == parsed.Result('relay run --help', 'relay run', text='relay run [--config <config>]')
        found = await self._run(bound, 'log 0 --help')  # its values aren't loaded, so not refused
        assert (found.ok, found.text) == (True, 'log [<n>]')

    async def test_a_line_that_doesn_t_read(self, bound):
        found = await self._run(bound, 'rela run')
        assert (found.command, found.ok, found.done, found.code) == (None, False, False, 2)
        assert found.text == "no command 'rela'; did you mean relay?"
        assert found.error == found.exception.to_json()
        assert isinstance(found.exception, ReadError)

    async def test_a_value_its_field_refuses(self, bound):
        found = await self._run(bound, 'log 0')
        assert (found.command, found.ok, found.code) == ('log {n}', False, 4)
        assert found.error['field'] == 'n'

    async def test_a_handler_that_raises(self, app):
        def broken(command, ctx):
            msg = 'nope'
            raise KeyError(msg)

        app.on(service.Run, broken)
        found = await self._run(app, 'relay run')
        assert (found.command, found.ok, found.done, found.code) == ('relay run', False, False, 1)
        assert found.error == {'error': 'handler', 'message': "KeyError: 'nope'"}
        assert found.text == "KeyError: 'nope'"
        assert isinstance(found.exception, KeyError)

    async def test_a_handler_that_raises_without_a_message(self, app):
        def broken(command, ctx):
            raise RuntimeError

        app.on(service.Run, broken)
        assert (await self._run(app, 'relay run')).text == 'RuntimeError'

    async def test_a_command_with_no_handler(self, app):
        found = await self._run(app, 'relay status')
        assert found.code == 1
        assert (
            found.text == "LookupError: Status has no handler in _support_service under 'relay': bind one with app.on"
        )

    @pytest.mark.parametrize(
        ('line', 'returned', 'says'),
        [
            (
                'log',
                {'lines': []},
                (
                    "Log's handler returned a dict: a handler returns text or nothing, or the REPLY its command "
                    'declares, or asks first'
                ),
            ),
            (
                'fleets show f1',
                service.RelaySettings(),
                (
                    "FleetsShow's handler returned a RelaySettings: a handler returns its REPLY (FleetView), text "
                    'or nothing, or asks first'
                ),
            ),
        ],
    )
    async def test_a_handler_that_returns_what_it_shouldn_t(self, app, line, returned, says):
        app.on(type(app.read(line)), lambda command, ctx: returned)
        found = await self._run(app, line)
        assert (found.ok, found.done, found.code) == (False, False, 1)
        assert found.text == f'TypeError: {says}'

    async def test_only_while_it_s_open(self, app):
        with pytest.raises(RuntimeError, match=r'not yet open>: call lines inside'):
            await app.open().run('relay run')


class TestCallingWithHelpAndReplies:
    async def test_help_gives_the_usage_and_runs_nothing(self, app):
        recorder = _Recorder()
        app.on(service.Run, recorder)
        async with app.open() as session:
            assert await session.call('relay run --help') == 'relay run [--config <config>]'
        assert recorder.calls == []

    async def test_a_reply_it_shouldn_t_return_is_raised(self, app):
        app.on(farlandia.Log, lambda command, ctx: 3)
        async with app.open() as session:
            with pytest.raises(TypeError, match=r"Log's handler returned a int: a handler returns text or nothing"):
                await session.call('log')


class TestOneLine:
    def test_a_line_run_in_a_session_of_its_own(self, app):
        app.on(farlandia.FleetMine, _said)
        link = _Link()
        found = app.run('fleet f1 mine', link, verbosity=1)
        assert (found.ok, found.text) == (True, 'f1 mines')
        assert link.happened == ['opened', ('closed', None)]

    def test_its_state_seen_by_the_handler(self, app):
        app.on(service.Run, lambda command, ctx: f'{ctx.state} at {ctx.verbosity}')
        assert app.run('relay run', 'state', verbosity=2).text == 'state at 2'

    def test_what_it_refuses_is_its_result(self, app):
        assert app.run('rela run').code == 2

    async def test_not_inside_a_running_loop(self, app):
        with pytest.raises(RuntimeError, match=r'runs an event loop of its own; inside one, open a session'):
            app.run('relay run')


class _Hangar:
    """A fake state for buying ships: what a fleet holds, the credits, and how each purchase was answered."""

    def __init__(self) -> None:
        self.ships: list[str] = []
        self.credits = 2000


def _buy(command, ctx):
    """Buy a ship, asked first: it names the price, and nothing is bought until the answer is yes."""
    hangar = ctx.state

    def bought() -> str:
        hangar.ships.append(command.hull)
        hangar.credits -= 1200
        return f'{command.fleet} bought a {command.hull}'

    return parsed.Ask(f'Buy a {command.hull} for 1,200 credits?', bought)


def _buy_twice(command, ctx):
    """Asked twice: the price, then the crew."""
    hangar = ctx.state

    async def crewed() -> str:
        await asyncio.sleep(0)
        hangar.ships.append(command.hull)
        return 'bought and crewed'

    return parsed.Ask('Buy it?', lambda: parsed.Ask('Crew it too?', crewed))


class TestAskingFirst:
    @pytest.fixture
    def shop(self, app) -> App:
        app.on(farlandia.FleetBuyShip, _buy)
        return app

    async def test_unanswered_nothing_is_done(self, shop):
        hangar = _Hangar()
        async with shop.open(hangar) as session:
            found = await session.run('fleet f1 buy ship hauler')
        assert found == parsed.Result(
            'fleet f1 buy ship hauler',
            'fleet {fleet} buy ship {hull}',
            asks='Buy a hauler for 1,200 credits?',
            text='Buy a hauler for 1,200 credits?',
        )
        assert (found.ok, found.done, found.code) == (True, False, 0)
        assert hangar.ships == []

    @pytest.mark.parametrize(
        ('line', 'yes'), [('fleet f1 buy ship hauler --yes', False), ('fleet f1 buy ship hauler', True)]
    )
    async def test_yes_answers_it(self, shop, line, yes):
        hangar = _Hangar()
        async with shop.open(hangar) as session:
            found = await session.run(line, yes=yes)
        assert (found.ok, found.done, found.asks, found.text) == (True, True, None, 'f1 bought a hauler')
        assert (hangar.ships, hangar.credits) == (['hauler'], 800)

    @pytest.mark.parametrize('said', [True, False])
    async def test_the_session_s_answer(self, shop, said):
        asked: list[str] = []

        def answer(question: str) -> bool:
            asked.append(question)
            return said

        hangar = _Hangar()
        async with shop.open(hangar, answer=answer) as session:
            found = await session.run('fleet f1 buy ship hauler')
        assert asked == ['Buy a hauler for 1,200 credits?']
        assert found.done is said
        assert hangar.ships == (['hauler'] if said else [])
        assert found.asks == (None if said else 'Buy a hauler for 1,200 credits?')

    async def test_an_async_answer(self, shop):
        async def answer(question: str) -> bool:
            await asyncio.sleep(0)
            return True

        hangar = _Hangar()
        async with shop.open(hangar, answer=answer) as session:
            assert (await session.run('fleet f1 buy ship hauler')).done
        assert hangar.ships == ['hauler']

    async def test_yes_asks_no_one(self, shop):
        def answer(question: str) -> bool:
            raise AssertionError(question)

        async with shop.open(_Hangar(), answer=answer) as session:
            assert (await session.run('fleet f1 buy ship hauler --yes')).done

    async def test_then_may_ask_again(self, app):
        app.on(farlandia.FleetBuyShip, _buy_twice)
        asked: list[str] = []
        hangar = _Hangar()
        async with app.open(hangar, answer=lambda question: asked.append(question) or len(asked) < 2) as session:
            declined = await session.run('fleet f1 buy ship hauler')
            bought = await session.run('fleet f1 buy ship hauler --yes')
        assert asked == ['Buy it?', 'Crew it too?']  # the first yes, the second no
        assert (declined.asks, declined.done) == ('Crew it too?', False)
        assert (bought.text, bought.done) == ('bought and crewed', True)
        assert hangar.ships == ['hauler']

    async def test_what_then_returns_is_checked(self, app):
        app.on(farlandia.FleetBuyShip, lambda command, ctx: parsed.Ask('Buy it?', lambda: 3))
        async with app.open() as session:
            found = await session.run('fleet f1 buy ship hauler --yes')
        assert (found.ok, found.code) == (False, 1)
        assert found.text.startswith("TypeError: FleetBuyShip's handler returned a int")

    async def test_any_command_may_ask(self, app):
        # `ASKS` says ahead of time that a command may ask; asking doesn't need it.
        assert not parsed.command.declaration(service.Run).asks
        app.on(service.Run, lambda command, ctx: parsed.Ask('Run it?', lambda: 'running'))
        async with app.open() as session:
            assert (await session.run('relay run')).asks == 'Run it?'
            assert (await session.run('relay run --yes')).text == 'running'

    async def test_call_gives_the_question_back(self, shop):
        hangar = _Hangar()
        async with shop.open(hangar) as session:
            asked = await session.call('fleet f1 buy ship hauler')
            assert isinstance(asked, parsed.Ask)
            assert asked.question == 'Buy a hauler for 1,200 credits?'
            assert await session.call('fleet f1 buy ship hauler', yes=True) == 'f1 bought a hauler'
        assert hangar.ships == ['hauler']

    def test_one_line_answered(self, shop):
        hangar = _Hangar()
        assert shop.run('fleet f1 buy ship hauler', hangar).asks is not None
        assert shop.run('fleet f1 buy ship hauler', hangar, yes=True).done
        assert shop.run('fleet f1 buy ship hauler', hangar, answer=lambda question: True).done
        assert hangar.ships == ['hauler', 'hauler']


class TestTheTerminalGameEndToEnd:
    # The fixture's tree run against a fake state: what's read, what's shown, and a purchase asked first.
    @pytest.fixture
    def game(self) -> App:
        found = App('farlandia')
        for category, resolver in farlandia.NAMES.items():
            found.names(category, resolver)
        found.mount('_support_farlandia')
        found.on(farlandia.FleetBuyShip, _buy)
        found.on(farlandia.FleetsShow, lambda command, ctx: farlandia.FleetView(fleet=command.fleet, docked=True))
        found.on(farlandia.FleetMine, lambda command, ctx: f'{command.fleet} mines' + (' (dry run)' * ctx.dry_run))
        return found

    async def test_a_session_of_several_lines(self, game):
        hangar = _Hangar()
        async with game.open(hangar) as session:
            mined = await session.run('fleet Prospector mine --for 1h')
            shown = await session.run('fleets show Hauler --json')
            asked = await session.run('fleet Prospector buy ship hauler')
            bought = await session.run('fleet Prospector buy ship hauler --yes')
            dry = await session.run('fleet Prospector mine --dry-run')
            wrong = await session.run('fleet Nobody mine')
        assert (mined.text, mined.done) == ('f1 mines', True)
        assert shown.to_json()['reply'] == {'fleet': 'f2', 'docked': True}
        assert (asked.asks, asked.done) == ('Buy a hauler for 1,200 credits?', False)
        assert (bought.text, bought.done) == ('f1 bought a hauler', True)
        assert (dry.text, dry.done) == ('f1 mines (dry run)', False)
        assert (wrong.ok, wrong.code) == (False, 2)
        assert (hangar.ships, hangar.credits) == (['hauler'], 800)  # bought once, on the yes


class _Log:
    """Hooks and a handler that write what they see to one log, in order."""

    def __init__(self) -> None:
        self.lines: list[tuple] = []

    def hook(self, name: str):
        def hooked(command, ctx, *found):
            self.lines.append((name, type(command).__name__, *found))

        return hooked

    def handler(self, command, ctx):
        self.lines.append(('handler', type(command).__name__))
        return 'ran'


class TestHooks:
    @pytest.fixture
    def log(self, app) -> _Log:
        found = _Log()
        app.on(service.Run, found.handler)
        app.on(service.Status, found.handler)
        return found

    async def _run(self, app: App, line: str, **given):
        async with app.open(**given) as session:
            return await session.run(line)

    async def test_in_their_stated_order(self, app, log):
        app.before(log.hook('app before'))
        app.before(log.hook('run before'), service.Run)
        app.after(log.hook('app after'))
        app.after(log.hook('run after'), service.Run)
        assert (await self._run(app, 'relay run')).text == 'ran'
        assert log.lines == [
            ('app before', 'Run'),
            ('run before', 'Run'),
            ('handler', 'Run'),
            ('run after', 'Run', 'ran'),
            ('app after', 'Run', 'ran'),
        ]

    async def test_each_scope_s_in_the_order_added(self, app, log):
        app.before(log.hook('first'))
        app.before(log.hook('second'))
        app.after(log.hook('third'))
        app.after(log.hook('fourth'))
        await self._run(app, 'relay run')
        assert [line[0] for line in log.lines] == ['first', 'second', 'handler', 'third', 'fourth']

    async def test_a_command_s_own_for_it_alone(self, app, log):
        app.before(log.hook('run before'), service.Run, farlandia.Log)
        await self._run(app, 'relay status')
        assert log.lines == [('handler', 'Status')]

    async def test_hooks_listed_as_they_run(self, app):
        def every(*_):
            return None

        def own(*_):
            return None

        for stage in (app.before, app.after, app.on_error):
            stage(every)
            stage(own, service.Run)
        assert app.hooks(service.Run) == ((every, own), (own, every), (own, every))
        assert app.hooks(service.Status) == ((every,), (every,), (every,))

    async def test_one_context_for_the_line(self, app):
        seen = []
        app.on(service.Run, lambda command, ctx: seen.append(ctx))
        app.before(lambda command, ctx: seen.append(ctx))
        app.after(lambda command, ctx, found: seen.append(ctx))
        await self._run(app, 'relay run --dry-run')
        assert len(seen) == 3
        assert seen[0] is seen[1] is seen[2]
        assert seen[0].dry_run  # hooks run on a dry run too, and see it

    async def test_after_sees_the_question_a_line_stopped_at(self, app, log):
        app.on(farlandia.FleetBuyShip, _buy)
        app.after(log.hook('after'))
        found = await self._run(app, 'fleet f1 buy ship hauler', state=_Hangar())
        ((stage, name, asked),) = log.lines
        assert (stage, name) == ('after', 'FleetBuyShip')
        assert asked.question == found.asks == 'Buy a hauler for 1,200 credits?'

    async def test_async_hooks_awaited(self, app, log):
        async def before(command, ctx):
            await asyncio.sleep(0)
            log.lines.append(('async before',))

        app.before(before)
        await self._run(app, 'relay run')
        assert log.lines == [('async before',), ('handler', 'Run')]

    @pytest.mark.parametrize('where', ['before', 'handler', 'answer', 'after'])
    async def test_a_failure_runs_the_on_error_hooks_then_goes_on(self, app, log, where):
        failed = KeyError(where)

        def fail(*_):
            raise failed

        app.on_error(log.hook('app on error'))
        app.on_error(log.hook('own on error'), service.Run)
        relay = _mount(app, 'relay')
        if where == 'before':
            app.before(fail)
        elif where == 'handler':
            relay.on(service.Run, fail)
        elif where == 'answer':
            relay.on(service.Run, lambda command, ctx: parsed.Ask('Run it?', lambda: 'ran'))
        else:
            app.after(fail)
        found = await self._run(app, 'relay run', answer=fail)
        assert (found.ok, found.code, found.exception) == (False, 1, failed)
        assert log.lines[-2:] == [('own on error', 'Run', failed), ('app on error', 'Run', failed)]
        assert (('handler', 'Run') in log.lines) is (where == 'after')  # a failure before it stops the handler

    async def test_a_failing_on_error_hook_s_error_goes_on(self, app):
        def broken(command, ctx):
            msg = 'handler'
            raise KeyError(msg)

        def worse(command, ctx, error):
            msg = 'hook'
            raise ValueError(msg)

        app.on(service.Run, broken)
        app.on_error(worse)
        async with app.open() as session:
            with pytest.raises(ValueError, match='hook') as caught:
                await session.call('relay run')
        assert isinstance(caught.value.__context__, KeyError)

    @pytest.mark.parametrize('line', ['rela run', 'relay run --help', 'relay validate-config'])
    async def test_none_run_where_no_handler_does(self, app, log, line):
        app.before(log.hook('before'))
        app.on_error(log.hook('on error'))
        await self._run(app, line)
        assert log.lines == []

    @pytest.mark.parametrize(
        ('stage', 'given', 'message'),
        [
            ('before', (3,), r'before\(3, …\): a hook is a callable'),
            (
                'after',
                (print, service.ServiceCommand),
                r'after\(…, .*ServiceCommand.*\): a command class, with a PHRASE',
            ),
            ('on_error', (print, 'run'), r"on_error\(…, 'run'\): a command class"),
        ],
    )
    def test_refused(self, app, stage, given, message):
        with pytest.raises(DeclarationError, match=message):
            getattr(app, stage)(*given)


class _Fleet:
    """A fake state: a fleet, docked or not, how often it was read, and whom to tell when it moves."""

    def __init__(self, *, docked: bool = False) -> None:
        self.docked = docked
        self.reads = 0
        self.on_change: Callable[[], None] | None = None

    def dock(self) -> None:
        self.docked = True
        if self.on_change is not None:
            self.on_change()

    def drift(self) -> None:
        """Dock, saying nothing: a state that moves without a signal."""
        self.docked = True


def _show(command, ctx):
    fleet = ctx.state
    fleet.reads += 1
    return farlandia.FleetView(fleet=command.fleet, docked=fleet.docked)


class TestWaiting:
    @pytest.fixture
    def shows(self, app) -> App:
        app.on(farlandia.FleetsShow, _show)
        return app

    async def test_met_at_once(self, shows):
        fleet = _Fleet(docked=True)
        async with shows.open(fleet) as session:
            found = await session.run('fleets show f1 --until docked=true')
        assert (found.ok, found.met, found.code, fleet.reads) == (True, True, 0, 1)
        assert found.to_json()['met'] is True
        assert 0 <= found.waited < 1  # it says how long it waited

    async def test_woken_by_a_change_not_a_poll(self, shows):
        fleet = _Fleet()
        async with shows.open(fleet, interval=None) as session:
            fleet.on_change = session.changed
            asyncio.get_running_loop().call_later(0.01, fleet.dock)
            found = await session.run('fleets show f1 --until docked=true --timeout 5s')
        assert (found.met, found.reply.docked, fleet.reads) == (True, True, 2)

    async def test_read_again_on_the_interval_without_one(self, shows):
        fleet = _Fleet()  # it moves, and says nothing
        async with shows.open(fleet, interval=0.01) as session:
            asyncio.get_running_loop().call_later(0.03, fleet.drift)
            found = await session.run('fleets show f1 --until docked=true --timeout 5s')
        assert found.met
        assert fleet.reads > 2

    async def test_past_the_bound_exit_7_with_the_last_reply(self, shows):
        fleet = _Fleet()
        async with shows.open(fleet, interval=0.01) as session:
            found = await session.run('fleets show f1 --until docked=true --timeout 0.05s')
        message = 'fleets show {fleet}: docked=true not met within 0.05s'
        assert (found.ok, found.done, found.met, found.code) == (False, True, False, 7)
        assert (found.reply, found.text) == (farlandia.FleetView(fleet='f1'), message)
        assert found.error == {'error': 'timeout', 'message': message}
        assert 0.05 <= found.waited < 1
        assert isinstance(found.exception, parsed.TimedOutError)
        assert fleet.reads > 1

    async def test_every_condition_named(self, shows):
        async with shows.open(_Fleet()) as session:
            found = await session.run('fleets show f1 --until docked=true --until fleet=f1 --timeout 0s')
        assert found.text == 'fleets show {fleet}: docked=true and fleet=f1 not met within 0s'

    async def test_no_interval_no_change_one_read(self, shows):
        fleet = _Fleet()
        async with shows.open(fleet, interval=None) as session:
            found = await session.run('fleets show f1 --until docked=true --timeout 0.05s')
        assert (found.met, found.code, fleet.reads) == (False, 7, 1)

    async def test_a_bound_of_nought_reads_once(self, shows):
        fleet = _Fleet()
        async with shows.open(fleet) as session:
            found = await session.run('fleets show f1 --until docked=true --timeout 0s')
        assert (found.met, found.code, fleet.reads) == (False, 7, 1)

    async def test_call_refuses_it_with_the_last_reply(self, shows):
        async with shows.open(_Fleet(), interval=None) as session:
            with pytest.raises(parsed.TimedOutError, match=r'docked=true not met within 0.05s') as caught:
                await session.call('fleets show f1 --until docked=true --timeout 0.05s')
        assert caught.value.reply == farlandia.FleetView(fleet='f1')
        assert 0.05 <= caught.value.waited < 1

    async def test_the_on_error_hooks_see_it(self, shows):
        seen: list[object] = []
        shows.after(lambda command, ctx, found: seen.append('after'))
        shows.on_error(lambda command, ctx, error: seen.append(type(error).__name__))
        async with shows.open(_Fleet()) as session:
            await session.run('fleets show f1 --until docked=true --timeout 0s')
        assert seen == ['TimedOutError']

    async def test_a_change_from_another_thread(self, shows):
        fleet = _Fleet()
        async with shows.open(fleet, interval=None) as session:
            fleet.on_change = session.changed
            mover = threading.Timer(0.01, fleet.dock)
            mover.start()
            found = await session.run('fleets show f1 --until docked=true --timeout 5s')
            mover.join()
        assert (found.met, fleet.reads) == (True, 2)

    async def test_a_change_during_a_read_isn_t_missed(self, app):
        fleet = _Fleet()

        def racing(command, ctx):
            found = _show(command, ctx)
            if fleet.reads == 1:
                fleet.docked = True
                ctx.session.changed()  # after the reply was made, before the wait waits
            return found

        app.on(farlandia.FleetsShow, racing)
        async with app.open(fleet, interval=None) as session:
            found = await session.run('fleets show f1 --until docked=true --timeout 5s')
        assert (found.met, fleet.reads) == (True, 2)

    async def test_hooks_once_around_the_wait(self, shows):
        seen: list[str] = []
        shows.before(lambda command, ctx: seen.append('before'))
        shows.after(lambda command, ctx, found: seen.append('after'))
        fleet = _Fleet()
        async with shows.open(fleet, interval=0.01) as session:
            asyncio.get_running_loop().call_later(0.02, fleet.drift)
            await session.run('fleets show f1 --until docked=true --timeout 5s')
        assert seen == ['before', 'after']
        assert fleet.reads > 1

    async def test_call_waits_too(self, shows):
        fleet = _Fleet()
        async with shows.open(fleet, interval=None) as session:
            fleet.on_change = session.changed
            asyncio.get_running_loop().call_later(0.01, fleet.dock)
            assert await session.call('fleets show f1 --until docked=true') == farlandia.FleetView(
                fleet='f1', docked=True
            )

    async def test_none_for_a_line_that_doesn_t_wait(self, shows):
        async with shows.open(_Fleet()) as session:
            found = await session.run('fleets show f1')
        assert (found.met, found.waited) == (None, None)
        assert found.to_json()['waited'] is None

    async def test_refused_before_anything_runs(self, app):
        fleet = _Fleet()
        app.on(farlandia.FleetsShow, _show)
        async with app.open(fleet) as session:
            found = await session.run('fleets show f1 --until dockd=true')
        assert (found.ok, found.code, fleet.reads) == (False, 2, 0)

    async def test_a_waited_on_handler_returns_its_reply(self, app):
        app.on(farlandia.FleetsShow, lambda command, ctx: 'docked')
        async with app.open() as session:
            found = await session.run('fleets show f1 --until docked=true')
        assert (found.ok, found.code) == (False, 1)
        assert found.text == (
            "TypeError: FleetsShow's handler returned a str: a wait reads its REPLY (FleetView), so it returns one"
        )

    def test_a_change_with_nothing_open_is_nothing(self, app):
        session = app.open()
        session.changed()  # not yet open: nothing waits

    @pytest.mark.parametrize('interval', [0, -1, True, '1s'])
    def test_an_interval_is_a_positive_number_of_seconds(self, app, interval):
        with pytest.raises(ValueError, match=r'how often a wait reads again, a positive number of seconds, or None'):
            app.open(interval=interval)


class _Galaxy:
    """The terminal game's fixture as a fake state: fleets that take a while to dock, and whom to tell."""

    def __init__(self) -> None:
        self.docked: dict[str, bool] = {'f1': False}
        self.reads = 0
        self.on_change: Callable[[], None] | None = None

    def arrive(self, fleet: str) -> None:
        self.docked[fleet] = True
        if self.on_change is not None:
            self.on_change()


class TestTheTerminalGameWaiting:
    async def test_a_fleet_sent_to_dock_waited_on_until_it_does(self):
        game = App('farlandia')
        game.names('fleet', farlandia.NAMES['fleet'])
        game.mount('_support_farlandia')

        def dock(command, ctx):
            asyncio.get_running_loop().call_later(0.02, ctx.state.arrive, command.fleet)
            return f'{command.fleet} is on its way'

        def show(command, ctx):
            ctx.state.reads += 1
            return farlandia.FleetView(fleet=command.fleet, docked=ctx.state.docked[command.fleet])

        game.on(farlandia.FleetDock, dock)
        game.on(farlandia.FleetsShow, show)
        galaxy = _Galaxy()
        async with game.open(galaxy, interval=None) as session:  # no poll: only the change wakes it
            galaxy.on_change = session.changed
            sent = await session.run('fleet Prospector dock nearest')
            found = await session.run('fleets show Prospector --until docked=true --timeout 2m')
        assert sent.text == 'f1 is on its way'
        assert (found.met, found.to_json()['reply'], galaxy.reads) == (True, {'fleet': 'f1', 'docked': True}, 2)


class _Moving:
    """A fake state: a fleet that docks and leaves in turn, saying so each time."""

    def __init__(self) -> None:
        self.docked = False
        self.reads = 0
        self.on_change: Callable[[], None] | None = None

    def move(self) -> None:
        self.docked = not self.docked
        if self.on_change is not None:
            self.on_change()


class TestWatching:
    @pytest.fixture
    def shows(self, app) -> App:
        app.on(farlandia.FleetsShow, _show)
        return app

    async def _watch(self, app: App, line: str, state: object, moves: int = 0, *, interval: float | None = None):
        """The results of watching ``line``, while the state moves ``moves`` times, once each result is in."""
        found = []
        async with app.open(state, interval=interval) as session:
            state.on_change = session.changed
            async for result in session.watch(line):
                found.append(result)
                if len(found) <= moves:
                    asyncio.get_running_loop().call_soon(state.move)
        return found

    async def test_each_reply_as_it_changes_until_its_count(self, shows):
        found = await self._watch(shows, 'fleets show f1 --watch --count 3', _Moving(), moves=5)
        assert [result.reply.docked for result in found] == [False, True, False]
        assert all(result.ok and result.code == 0 and result.met is None for result in found)
        assert [type(result.waited) for result in found] == [float] * 3

    async def test_one_json_line_each(self, shows):
        found = await self._watch(shows, 'fleets show f1 --watch --count 2', _Moving(), moves=1)
        lines = [json.dumps(result.to_json()) for result in found]
        assert [json.loads(line)['reply'] for line in lines] == [
            {'fleet': 'f1', 'docked': False},
            {'fleet': 'f1', 'docked': True},
        ]

    async def test_only_a_change_is_given(self, shows):
        fleet = _Fleet()
        async with shows.open(fleet, interval=0.01) as session:  # reads again and again, the reply the same
            loop = asyncio.get_running_loop()
            loop.call_later(0.05, fleet.drift)
            found = [result async for result in session.watch('fleets show f1 --watch --count 2 --timeout 5s')]
        assert [result.reply.docked for result in found] == [False, True]
        assert fleet.reads > 2

    async def test_until_the_bound_without_conditions_is_an_end(self, shows):
        fleet = _Fleet()
        async with shows.open(fleet, interval=0.01) as session:
            found = [result async for result in session.watch('fleets show f1 --watch --timeout 0.05s')]
        assert [(result.ok, result.code) for result in found] == [(True, 0)]

    async def test_until_its_conditions(self, shows):
        found = await self._watch(shows, 'fleets show f1 --watch --until docked=true', _Moving(), moves=5)
        assert [(result.reply.docked, result.met) for result in found] == [(False, False), (True, True)]

    async def test_conditions_unmet_past_the_bound_exit_7(self, shows):
        fleet = _Fleet()
        async with shows.open(fleet, interval=0.01) as session:
            found = [
                result async for result in session.watch('fleets show f1 --watch --until docked=true --timeout 0.05s')
            ]
        assert [(result.ok, result.code) for result in found] == [(True, 0), (False, 7)]
        assert found[-1].reply == farlandia.FleetView(fleet='f1')

    async def test_cancelled_it_stops(self, shows):
        fleet = _Fleet()
        seen = []

        async def watch(session):
            async for result in session.watch('fleets show f1 --watch'):
                seen.append(result)  # noqa: PERF401 -- kept as each comes, so a cancel leaves what came before

        async with shows.open(fleet, interval=None) as session:
            task = asyncio.create_task(watch(session))
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert len(seen) == 1

    async def test_run_gives_the_last_and_call_its_reply(self, shows):
        async with shows.open(_Moving(), interval=None) as session:
            moving = session.state
            moving.on_change = session.changed
            asyncio.get_running_loop().call_later(0.01, moving.move)
            last = await session.run('fleets show f1 --watch --count 2')
            asyncio.get_running_loop().call_later(0.01, moving.move)
            reply = await session.call('fleets show f1 --watch --count 2')
        assert last.reply.docked is True
        assert reply == farlandia.FleetView(fleet='f1', docked=False)

    async def test_hooks_once_around_the_watch(self, shows):
        seen = []
        shows.before(lambda command, ctx: seen.append('before'))
        shows.after(lambda command, ctx, found: seen.append(('after', found.docked)))
        await self._watch(shows, 'fleets show f1 --watch --count 3', _Moving(), moves=5)
        assert seen == ['before', ('after', False)]

    async def test_a_line_that_doesn_t_watch_gives_its_one_result(self, shows):
        async with shows.open(_Fleet(docked=True)) as session:
            found = [result async for result in session.watch('fleets show f1 --until docked=true')]
            refused = [result async for result in session.watch('rela run')]
        assert [(result.met, result.code) for result in found] == [(True, 0)]
        assert [result.code for result in refused] == [2]

    async def test_the_terminal_game_s_fleet_as_it_moves(self):
        game = App('farlandia')
        game.names('fleet', farlandia.NAMES['fleet'])
        game.mount('_support_farlandia')
        game.on(farlandia.FleetsShow, _show)
        found = await self._watch(game, 'fleets show Prospector --watch --count 4', _Moving(), moves=10)
        assert [result.to_json()['reply'] for result in found] == [
            {'fleet': 'f1', 'docked': docked} for docked in (False, True, False, True)
        ]


class _Orders:
    """A fake state for a fleet's orders: what each chain sent, in order."""

    def __init__(self) -> None:
        self.sent: list[list[object]] = []


def _ordered(steps, ctx):
    """A chain's handler: the steps, sent as one order."""
    ctx.state.sent.append(steps)
    return f'{len(steps)} steps'


class TestChains:
    @pytest.fixture
    def game(self) -> App:
        found = App('farlandia')
        found.names('fleet', farlandia.NAMES['fleet'])
        found.mount('_support_farlandia')
        found.on_chain(farlandia.FleetCommand, _ordered)
        return found

    async def test_a_chain_runs_as_one_order(self, game):
        orders = _Orders()
        async with game.open(orders) as session:
            found = await session.run('fleet Prospector jump sol then move belt then mine')
        assert orders.sent == [
            [
                farlandia.FleetJump(fleet='f1', system='sol'),
                farlandia.FleetMove(fleet='f1', to='belt'),
                farlandia.FleetMine(fleet='f1'),
            ]
        ]
        assert (found.ok, found.text, found.command) == (
            True,
            '3 steps',
            'fleet {fleet} jump {system} then move {to} then mine',
        )

    async def test_each_step_s_names_where_the_fleet_will_be(self, game):
        for category in ('system', 'site', 'station'):
            game.names(category, farlandia.NAMES[category])
        orders = _Orders()
        async with game.open(orders) as session:
            found = await session.run('fleet Prospector jump sol then move "Sol Belt" then mine')
            refused = await session.run('fleet Prospector jump sol then move Vesta')
        assert orders.sent == [
            [
                farlandia.FleetJump(fleet='f1', system='sol'),
                farlandia.FleetMove(fleet='f1', to='sol-belt'),
                farlandia.FleetMine(fleet='f1'),
            ]
        ]
        assert found.ok
        assert (refused.code, refused.error and refused.error['message']) == (
            2,
            "fleet {fleet} move {to}: no site 'Vesta' for fleet 'Prospector', once at 'sol' `fleet <fleet> move <to>`",
        )

    async def test_a_chain_called_as_a_tool(self, game):
        for category in ('system', 'site', 'station'):
            game.names(category, farlandia.NAMES[category])
        call = {
            'fleet': 'f1',
            'steps': [{'step': 'jump', 'system': 'sol'}, {'step': 'move', 'to': 'sol-belt'}, {'step': 'mine'}],
        }
        steps = load_chain(game.mounts[0].tree, farlandia.FleetCommand, call)
        line = game.render(steps)
        assert line == 'fleet f1 jump sol then move sol-belt then mine'
        orders = _Orders()
        async with game.open(orders) as session:
            found = await session.run(line)
        assert (found.ok, orders.sent) == (True, [steps])

    async def test_a_lone_step_as_a_chain_of_one(self, game):
        orders = _Orders()
        async with game.open(orders) as session:
            await session.run('fleet f1 mine')
        assert orders.sent == [[farlandia.FleetMine(fleet='f1')]]

    async def test_a_step_s_own_handler_runs_it_alone(self, game):
        game.on(farlandia.FleetMine, lambda command, ctx: f'{command.fleet} mines')
        orders = _Orders()
        async with game.open(orders) as session:
            alone = await session.run('fleet f1 mine')
            chained = await session.run('fleet f1 mine then dock')
        assert alone.text == 'f1 mines'
        assert orders.sent == [[farlandia.FleetMine(fleet='f1'), farlandia.FleetDock(fleet='f1')]]
        assert chained.text == '2 steps'

    async def test_a_chain_s_context_says_its_steps(self, game):
        seen = []
        mount = game.mounts[0]  # its own, over the app's
        mount.on_chain(farlandia.FleetCommand, lambda steps, ctx: seen.append(ctx))
        async with game.open() as session:
            await session.run('fleet f1 jump sol then mine')
        (ctx,) = seen
        assert [step.command for step in ctx.reading.steps] == [farlandia.FleetJump, farlandia.FleetMine]
        assert ctx.line == 'fleet f1 jump sol then mine'

    async def test_a_chain_with_no_handler(self):
        game = App('farlandia')
        game.mount('_support_farlandia')
        async with game.open() as session:
            chained = await session.run('fleet f1 jump sol then mine')
            alone = await session.run('fleet f1 mine')
        assert chained.code == 1
        assert chained.text == (
            "LookupError: FleetCommand's chain has no handler in _support_farlandia at the root: bind one with "
            'app.on_chain'
        )
        assert alone.text.endswith("nor has FleetCommand's chain: bind one with app.on, or app.on_chain")

    async def test_hooks_of_the_chain_s_base(self, game):
        seen = []
        game.before(lambda steps, ctx: seen.append(('chain', len(steps))), farlandia.FleetCommand)
        game.before(lambda command, ctx: seen.append('mine alone'), farlandia.FleetMine)
        async with game.open(_Orders()) as session:
            await session.run('fleet f1 jump sol then mine')
        assert seen == [('chain', 2)]

    async def test_a_value_a_later_step_refuses(self, game):
        @parsed.parsed
        class Hold(farlandia.FleetCommand):
            PHRASE = 'fleet {fleet} hold {hours}'

            hours: int = parsed.Int(required=True, ge=1)

        game = App('farlandia')
        game.mount(Tree([farlandia.FleetMine, Hold]))
        game.on_chain(farlandia.FleetCommand, _ordered)
        async with game.open(_Orders()) as session:
            found = await session.run('fleet f1 mine then hold 0')
        assert (found.code, found.error['field']) == (4, 'hours')

    async def test_a_chain_s_reply_its_base_s(self, game):
        game.mounts[0].on_chain(farlandia.FleetCommand, lambda steps, ctx: farlandia.FleetView(fleet='f1'))
        async with game.open() as session:
            found = await session.run('fleet f1 mine then dock')
        assert found.code == 1
        assert found.text.startswith("TypeError: FleetCommand's handler returned a FleetView")

    @pytest.mark.parametrize(
        ('base', 'message'),
        [
            (farlandia.FleetMine, r"on_chain\(.*FleetMine.*, …\): a chain's base"),
            (farlandia.Log, r"on_chain\(.*Log.*, …\): a chain's base"),
            ('fleet', r"on_chain\('fleet', …\): a chain's base"),
        ],
    )
    def test_refused_unless_a_chain_s_base(self, game, base, message):
        with pytest.raises(DeclarationError, match=message):
            game.on_chain(base, _ordered)

    def test_bound_once(self, game):
        with pytest.raises(DeclarationError, match=r"FleetCommand has a chain's handler already: bind one once"):
            game.on_chain(farlandia.FleetCommand, _ordered)

    def test_a_mount_binds_only_a_chain_it_holds(self):
        relay = App('rio').mount('_support_service', under='relay')
        with pytest.raises(DeclarationError, match=r"has no step of FleetCommand's chain"):
            relay.on_chain(farlandia.FleetCommand, _ordered)

    def test_hooks_may_name_a_chain_s_base_but_no_other_base(self, game):
        game.after(print, farlandia.FleetCommand)
        with pytest.raises(DeclarationError, match=r"a command class, with a PHRASE, or a chain's base"):
            game.after(print, service.ServiceCommand)


@parsed.parsed
class Use(parsed.Command):
    """Make a fleet the subject: its bare verbs read under it."""

    PHRASE = 'use {fleet}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'fleet': farlandia.FLEET}

    fleet: str = parsed.Str(required=True)


def _use(command, ctx):
    ctx.session.use(f'fleet {command.fleet}')
    return f'orders now go to {command.fleet}'


def _mined(command, ctx):
    return f'{command.fleet} mines, read as {ctx.line!r}'


#: The terminal game's subject: a fleet, by its name.
_PROSPECTOR = ('fleet prospector',)


class TestSubjects:
    @pytest.fixture
    def game(self, app) -> App:
        app.names('detachment', farlandia.NAMES['detachment'])
        app.mount(Tree([Use]))
        app.on(Use, _use)
        app.on(farlandia.FleetMine, _mined)
        app.on_chain(farlandia.FleetCommand, _ordered)
        return app

    async def test_a_bare_line_reads_under_a_subject(self, game):
        async with game.open(subjects=_PROSPECTOR) as session:
            found = await session.run('mine')
        assert (found.ok, found.text) == (True, "f1 mines, read as 'fleet prospector mine'")
        assert (found.line, found.command) == ('fleet prospector mine', 'fleet {fleet} mine')  # the line as read

    async def test_the_line_as_typed_first(self, game):
        async with game.open(subjects=_PROSPECTOR) as session:
            assert (await session.run('fleet hauler mine')).text == "f2 mines, read as 'fleet hauler mine'"
        assert game.walk('relay status', subjects=_PROSPECTOR).command is service.Status  # a mount's words too

    def test_each_subject_in_turn(self, game):
        subjects = ('relay', 'ship s1', 'fleet prospector')
        assert game.read('run', subjects=subjects) == service.Run()
        assert game.read('fit', subjects=subjects) == farlandia.ShipFit(ship='s1')
        assert game.read('mine', subjects=subjects) == farlandia.FleetMine(fleet='f1')  # past those that don't go on
        assert game.subject_of('mine', subjects) == 'fleet prospector'
        assert game.subject_of('log', subjects) is None  # as typed

    def test_a_twin_s_subject(self, game):
        routed = game.walk('mine', subjects=('detachment scouts',))
        assert (routed.load(), routed.said) == (farlandia.FleetMine(fleet='d2'), 'detachment {detachment} mine')

    async def test_a_chain_under_a_subject(self, game):
        orders = _Orders()
        async with game.open(orders, subjects=_PROSPECTOR) as session:
            await session.run('jump sol then mine')
        assert orders.sent == [[farlandia.FleetJump(fleet='f1', system='sol'), farlandia.FleetMine(fleet='f1')]]

    async def test_a_line_no_subject_takes_is_read_as_typed(self, game):
        async with game.open(subjects=_PROSPECTOR) as session:
            found = await session.run('mien')
        assert (found.code, found.line) == (2, 'mien')
        assert found.text.startswith("no command 'mien'")

    async def test_a_refusal_says_the_line_read(self, game):
        async with game.open(subjects=_PROSPECTOR) as session:
            found = await session.run('mine --for soon')
        assert (found.code, found.line) == (2, 'fleet prospector mine --for soon')
        assert found.error is not None
        assert (found.error['line'], found.error['column']) == ('fleet prospector mine --for soon', 28)

    async def test_help_under_a_subject(self, game):
        async with game.open(subjects=_PROSPECTOR) as session:
            assert (await session.run('mine --help')).text == 'fleet <fleet> mine [--for <for>]'

    async def test_a_handler_makes_one_the_session_s(self, game):
        async with game.open() as session:
            assert (await session.run('use prospector')).text == 'orders now go to f1'
            assert session.subjects == ('fleet f1',)
            assert (await session.run('mine')).text == "f1 mines, read as 'fleet f1 mine'"
            session.use()
            assert (await session.run('mine')).code == 2  # none now

    def test_one_line_in_a_session_of_its_own(self, game):
        assert game.run('mine', subjects=_PROSPECTOR).text == "f1 mines, read as 'fleet prospector mine'"

    @pytest.mark.parametrize(
        ('subjects', 'message'),
        [
            (('flet prospector',), r"subject 'flet prospector': no command of farlandia begins with its words"),
            (('fleet prospector --yes',), r'a subject is words a line begins with, no flags'),
            (('',), r"subject '': a subject is words a line begins with"),
            (('fleet "open',), r"subject 'fleet \"open': the quote at column 7 is never closed"),
            ('fleet prospector', r'a sequence of subjects; one alone needs a trailing comma'),
        ],
    )
    def test_a_subject_is_words_a_command_begins_with(self, game, subjects, message):
        with pytest.raises(ValueError, match=message):
            game.open(subjects=subjects)
        with pytest.raises(ValueError, match=message):
            game.read('mine', subjects=subjects)

    async def test_and_so_is_one_used(self, game):
        async with game.open() as session:
            with pytest.raises(ValueError, match=r'no command of farlandia begins with its words'):
                session.use('flet prospector')
            assert session.subjects == ()

    def test_completing_a_bare_line(self, game):
        words = game.complete('', subjects=_PROSPECTOR).words
        assert words[:3] == ['fleet', 'detachment', 'log']  # the commands' first words, then the subject's
        assert words[-8:] == ['mine', 'dock', 'jump', 'move', 'retreat', 'run', 'sell', 'buy']
        assert game.complete('mi', subjects=_PROSPECTOR) == Completion(['mine'], 2)
        assert game.complete('dock ', subjects=_PROSPECTOR).words == ['nearest', 'then']
        assert game.complete('lo', subjects=_PROSPECTOR).words == ['log']

    async def test_the_session_completes_with_its_own(self, game):
        async with game.open(subjects=_PROSPECTOR) as session:
            assert session.complete('mi') == Completion(['mine'], 2)

    def test_kept_out_of_keys(self, game):
        assert command_key(game.read('mine', subjects=_PROSPECTOR)) == command_key(game.read('fleet f1 mine'))


@parsed.parsed
class Sketch(parsed.Command):
    """Draw a sketch: the client's own, with nothing said in its place."""

    PHRASE = 'sketch {n}'
    INTERACTIVE = True

    n: int = parsed.Int(required=True, ge=1)


@parsed.parsed
class Craft(parsed.Command):
    """A craft's orders, chained."""

    STEPS = True

    craft: str = parsed.Str(required=True)


@parsed.parsed
class CraftGo(Craft):
    """Send a craft on."""

    PHRASE = 'craft {craft} go'


@parsed.parsed
class CraftView(Craft):
    """Watch a craft: the client's own."""

    PHRASE = 'craft {craft} view'
    INTERACTIVE = True


_FIT_REFUSED = 'ship {ship} fit is for a person at a terminal: say `ships make <ship> add <part>` instead'


class TestATerminal:
    @pytest.fixture
    def fits(self, app) -> _Recorder:
        found = _Recorder()
        app.on(farlandia.ShipFit, found)
        return found

    async def _run(self, app: App, line: str, **given):
        async with app.open(**given) as session:
            return await session.run(line)

    async def test_none_by_default_so_a_command_for_a_person_is_refused(self, app, fits):
        found = await self._run(app, 'ship s1 fit')
        assert (found.command, found.ok, found.done, found.code) == ('ship {ship} fit', False, False, 3)
        assert found.text == _FIT_REFUSED
        assert found.error == {
            'error': 'refused',
            'message': _FIT_REFUSED,
            'line': 'ship s1 fit',
            'instead': 'ships make {ship} add {part}',
        }
        assert isinstance(found.exception, RefusedError)
        assert fits.calls == []

    async def test_at_a_terminal_it_runs(self, app, fits):
        found = await self._run(app, 'ship s1 fit', terminal=True)
        assert (found.ok, found.done) == (True, True)
        ((command, ctx),) = fits.calls
        assert command == farlandia.ShipFit(ship='s1')
        assert ctx.terminal is True

    async def test_help_still_answers(self, app, fits):
        found = await self._run(app, 'ship s1 fit --help')
        assert (found.ok, found.text) == (True, 'ship <ship> fit')

    async def test_a_dry_run_is_refused_too(self, app, fits):
        assert (await self._run(app, 'ship s1 fit --dry-run')).code == 3
        assert fits.calls == []

    async def test_before_its_values_are_loaded_or_any_hook_runs(self):
        log = _Log()
        sketches = App('sketches')
        sketches.mount(Tree([Sketch]))
        sketches.on(Sketch, log.handler)
        sketches.before(log.hook('before'))
        sketches.on_error(log.hook('on error'))
        found = await self._run(sketches, 'sketch 0')
        assert (found.code, found.text) == (3, 'sketch {n} is for a person at a terminal')  # nothing in its place
        assert 'instead' not in found.error
        assert log.lines == []
        assert (await self._run(sketches, 'sketch 0', terminal=True)).code == 4  # at one, its value is refused

    async def test_call_raises_it(self, app, fits):
        async with app.open() as session:
            with pytest.raises(RefusedError, match=r'ship \{ship\} fit is for a person at a terminal: say'):
                await session.call('ship s1 fit')
        assert fits.calls == []

    def test_one_line_with_or_without(self, app, fits):
        assert app.run('ship s1 fit').code == 3
        assert app.run('ship s1 fit', terminal=True).ok

    async def test_what_s_said_in_its_place_as_the_mount_that_holds_it_says_it(self):
        split = App('split')
        split.mount(Tree([farlandia.ShipFit]))
        split.mount(Tree([farlandia.ShipsMakeAdd]), under='farm')
        found = await self._run(split, 'ship s1 fit')
        assert found.text.endswith('say `farm ships make <ship> add <part>` instead')
        assert found.error['instead'] == 'farm ships make {ship} add {part}'

    async def test_what_s_said_in_its_place_by_its_phrase_where_no_mount_holds_it(self):
        alone = App('alone')
        alone.mount(Tree([farlandia.ShipFit]), under='game')
        found = await self._run(alone, 'game ship s1 fit')
        assert found.text == (
            'game ship {ship} fit is for a person at a terminal: say `ships make <ship> add <part>` instead'
        )
        assert found.error['instead'] == 'ships make {ship} add {part}'

    async def test_a_chain_with_a_step_for_a_person(self):
        crafts = App('crafts')
        crafts.mount(Tree([CraftGo, CraftView]))
        crafts.on_chain(Craft, lambda steps, ctx: ' then '.join(type(step).__name__ for step in steps))
        found = await self._run(crafts, 'craft c1 go then view')
        assert (found.code, found.text) == (3, 'craft {craft} view is for a person at a terminal')
        assert found.error['line'] == 'craft c1 go then view'
        assert (await self._run(crafts, 'craft c1 go then view', terminal=True)).text == 'CraftGo then CraftView'
        assert (await self._run(crafts, 'craft c1 go then go')).ok

    @pytest.mark.parametrize('terminal', [1, 'yes', None])
    def test_true_or_false(self, app, terminal):
        with pytest.raises(TypeError, match=r'terminal=.*: whether a person is at a terminal, True or False'):
            app.open(terminal=terminal)
