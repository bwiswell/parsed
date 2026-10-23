"""Tests for ``parsed/_walk/_route.py``: a line sent to the mount whose tree reads it, by its first words."""

from __future__ import annotations

from dataclasses import dataclass

import _support_farlandia as farlandia
import pytest

import parsed
from parsed._walk import Completion, Routes, split
from parsed.errors import DeclarationError, ReadError
from parsed.tree import Tree


@dataclass(frozen=True)
class Held:
    """A stand-in for an app's mount: a tree, and its label."""

    tree: Tree
    label: str


def _held(label: str, *targets: str, under: str = '') -> Held:
    return Held(Tree.collect(*targets, under=under), label)


@parsed.parsed
class Rio(parsed.Command):
    """A command whose word is where another tree is mounted."""

    PHRASE = 'rio'


@pytest.fixture(scope='module')
def farm() -> Held:
    return _held('farm', '_support_farlandia')


@pytest.fixture(scope='module')
def relay() -> Held:
    return _held('relay', '_support_service', under='relay')


@pytest.fixture(scope='module')
def gateway() -> Held:
    return _held('gateway', '_support_service', under='rio gateway')


@pytest.fixture(scope='module')
def routes(farm, relay, gateway) -> Routes[Held]:
    found: Routes[Held] = Routes()
    for held in (farm, relay, gateway):
        found.add(held)
    return found


class TestAdding:
    def test_a_prefix_then_each_first_word(self, routes, relay):
        assert list(routes.root.words['relay'].words) == ['run', 'validate-config', 'status']
        assert routes.root.words['relay'].words['run'].held is relay
        assert routes.root.words['relay'].held is None

    def test_two_mounts_may_share_a_prefix_if_no_word_begins_a_command_in_both(self):
        routes: Routes[Held] = Routes()
        routes.add(Held(Tree([farlandia.Log], under='look'), 'logs'))
        routes.add(Held(Tree([farlandia.Say], under='look'), 'talk'))
        assert routes.route('look say hello').label == 'talk'

    @pytest.mark.parametrize(
        ('held', 'message'),
        [
            (Held(Tree([farlandia.Log]), 'logs'), r"logs and farm both say 'log': a line would read two ways"),
            (
                Held(Tree([farlandia.Log], under='fleet'), 'logs'),
                r"logs is mounted where farm says 'fleet': a line would read two ways",
            ),
            (
                Held(Tree([farlandia.Log], under='rio gateway run'), 'logs'),
                r"logs is mounted where gateway says 'rio gateway run': a line would read two ways",
            ),
        ],
    )
    def test_a_line_that_would_read_two_ways_is_refused(self, routes, held, message):
        with pytest.raises(DeclarationError, match=message):
            routes.add(held)

    def test_a_first_word_where_others_are_mounted(self, gateway):
        routes: Routes[Held] = Routes()
        routes.add(gateway)
        with pytest.raises(DeclarationError, match=r"rio says 'rio', where gateway is mounted"):
            routes.add(Held(Tree([Rio]), 'rio'))

    def test_a_tree_with_no_commands(self):
        with pytest.raises(DeclarationError, match=r'empty has no commands to mount'):
            Routes().add(Held(Tree([], under='nothing'), 'empty'))

    def test_a_refused_mount_changes_nothing(self, farm):
        routes: Routes[Held] = Routes()
        routes.add(farm)
        before = list(routes.root.words)
        with pytest.raises(DeclarationError):
            routes.add(Held(Tree([farlandia.Say, farlandia.Log]), 'twice'))
        assert list(routes.root.words) == before


class TestRouting:
    @pytest.mark.parametrize(
        ('line', 'label'),
        [
            ('fleet f1 mine', 'farm'),
            ('log', 'farm'),
            ('relay run', 'relay'),
            ('RELAY Run', 'relay'),  # case aside, as a tree reads a literal
            ('rio gateway status --config c.toml', 'gateway'),
            ('relay --yes run', 'relay'),  # parsed's own flags may stand among its words
            ('rio --json gateway run', 'gateway'),
        ],
    )
    def test_by_its_first_words(self, routes, line, label):
        assert routes.route(line).label == label

    @pytest.mark.parametrize(
        ('line', 'says', 'column', 'word', 'suggestions'),
        [
            ('', 'no command: the line has no words', 0, None, ['fleet', 'detachment', 'log']),
            ('--yes relay run', '--yes comes before a command: a flag follows the first word', 0, '--yes', []),
            ('rela run', "no command 'rela'; did you mean relay?", 0, 'rela', ['relay']),
            ('relay', 'relay: then what? run | validate-config | status', 5, None, ['run', 'validate-config']),
            ('rio', 'rio: then what? gateway', 3, None, ['gateway']),
            ('rio gateway', 'rio gateway: then what? run | validate-config | status', 11, None, ['run']),
            ('relay zzz', "no command 'relay zzz': run | validate-config | status", 6, 'zzz', ['run']),
            ('relay "run"', 'no command \'relay "run"\': run | validate-config | status', 6, '"run"', ['run']),
            ('rio --config c.toml gateway run', 'rio: then what? gateway', 4, '--config', ['gateway']),
            ('relay -- run', 'relay: then what? run | validate-config | status', 6, '--', ['run']),
        ],
    )
    def test_a_line_that_reaches_no_mount(self, routes, line, says, column, word, suggestions):
        with pytest.raises(ReadError) as caught:
            routes.route(line)
        found = caught.value
        assert str(found) == says
        assert (found.kind, found.line, found.column, found.word) == ('usage', line, column, word)
        assert list(found.suggestions[: len(suggestions)]) == suggestions

    def test_an_open_quote(self, routes):
        with pytest.raises(ReadError, match=r'the quote at column 7 is never closed'):
            routes.route('relay "run')


class TestCompleting:
    @pytest.mark.parametrize(
        ('text', 'expected'),
        [
            ('rel', (['relay'], 3)),
            ('r', (['relay', 'rio'], 1)),
            ('relay ', (['run', 'validate-config', 'status'], 0)),
            ('relay s', (['status'], 1)),
            ('rio ', (['gateway'], 0)),
            ('rio --yes g', (['gateway'], 1)),
            ('relay "s', ([], 2)),  # a quoted word is never a command's word
            ('relay zzz ', ([], 0)),
            ('rio --config ', ([], 0)),
        ],
    )
    def test_short_of_a_mount_its_words(self, routes, text, expected):
        assert routes.complete(text) == Completion(*expected)

    def test_every_first_word_at_the_root(self, routes):
        found = routes.complete('')
        assert isinstance(found, Completion)
        assert found.words[-2:] == ['relay', 'rio']

    @pytest.mark.parametrize(('text', 'label'), [('fleet ', 'farm'), ('fleet f', 'farm'), ('relay run --c', 'relay')])
    def test_past_its_first_word_the_mount_s(self, routes, text, label):
        found = routes.complete(text)
        assert not isinstance(found, Completion)
        assert found.label == label


class TestHowFarWordsGo:
    # For a session's subjects: whether a word begins a line, and how far words go.
    def test_a_word_that_begins_a_line(self, routes):
        assert routes.begins(split('fleet')[0])
        assert routes.begins(split('Relay')[0])  # case aside
        assert routes.begins(split('rio')[0])  # a prefix's first word
        assert not routes.begins(split('mine')[0])
        assert not routes.begins(split('"fleet"')[0])  # quoted, a value

    def test_how_far_words_go(self, routes, farm, relay):
        assert routes.reach(split('fleet f1 mine')) is farm  # its first word is the mount's
        assert routes.reach(split('relay run')) is relay
        assert routes.reach(split('rio')) is True  # along a prefix, short of a mount
        assert routes.reach(split('mine')) is False
        assert routes.reach(split('rio zzz')) is False
