"""Tests for ``parsed/app.py``: an app's mounts, the handlers their commands run with, and the names it reads with."""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import _support_farlandia as farlandia
import _support_handlers as handlers
import _support_service as service
import pytest

import parsed
from parsed.app import App, Mount, Routed
from parsed.errors import DeclarationError, ReadError, RenderError
from parsed.tree import Tree


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
        assert ran(service.Run()) == 'ran Run(config=None)'
        assert app.handler(service.Run) is ran  # imported once
        assert _mount(app, 'gateway').handler(service.Run)(service.Run()) == 'status of Run(config=None)'

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
