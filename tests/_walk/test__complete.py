"""Tests for ``parsed/_walk/_complete.py``: what may come next on a line being typed."""

from __future__ import annotations

from typing import ClassVar

import _support_farlandia as farlandia
import pytest

import parsed
from parsed._walk import Completion, beneath, goes, split
from parsed._walk._complete import being_typed
from parsed.command import Command
from parsed.tree import Tree


@pytest.fixture(scope='module')
def tree() -> Tree:
    return Tree.collect('_support_farlandia')


def _words(tree: Tree, text: str, names=None) -> list[str]:
    return tree.complete(text, names=names).words


class TestWhatComesNext:
    def test_the_first_words(self, tree):
        assert _words(tree, '') == ['fleet', 'detachment', 'log', 'say', 'fleets', 'ships', 'ship']

    def test_the_word_being_typed_case_aside(self, tree):
        assert tree.complete('FL') == Completion(words=['fleet', 'fleets'], replace=2)

    def test_the_literal_words_after_a_slot(self, tree):
        assert _words(tree, 'fleet f1 ') == ['mine', 'dock', 'jump', 'move', 'retreat', 'run', 'sell', 'buy']

    def test_a_whole_command_s_flags(self, tree):
        assert _words(tree, 'fleet f1 mine ') == ['then', '--for']  # a step: another may follow

    def test_flags_given_aren_t_offered_again(self, tree):
        assert _words(tree, 'fleets merge f1 ') == ['--into', '--quiet', '--yes']  # asked first, so --yes
        assert _words(tree, 'fleets merge f1 --quiet --yes ') == ['--into']

    def test_a_list_s_flag_again(self):
        tag = Tree([_command('tag', tags=parsed.Str(many=True, default_factory=list))])
        assert _words(tag, 'tag --tags a ') == ['--tags']

    def test_a_flag_being_typed(self, tree):
        assert tree.complete('fleet f1 mine --f') == Completion(words=['--for'], replace=3)

    def test_a_flag_typed_before_the_command_is_whole(self, tree):
        assert _words(tree, 'fleet f1 --') == ['--for', '--yes']

    def test_a_flag_s_values(self, tree):
        assert _words(tree, 'fleet f1 mine --for ') == ['10m', '30m', '1h']

    def test_a_slot_s_kind_s_offers(self, tree):
        assert _words(tree, 'fleets start ') == ['true', 'false']
        assert _words(tree, 'fleet f1 retreat ') == ['off']
        assert _words(tree, 'fleet f1 retreat O') == ['off']

    def test_an_enum_s_values(self):
        cls = _command('paint {colour}', colour=parsed.Enum(enum=farlandia.Colour, required=True))
        assert _words(Tree([cls]), 'paint ') == ['red', 'green']

    def test_a_literal_beside_a_slot(self, tree):
        assert _words(tree, 'fleet f1 jump ') == ['nearest']
        assert _words(tree, 'fleet f1 dock ') == ['nearest', 'then']

    def test_nothing_where_any_word_may_do(self, tree):
        assert _words(tree, 'log ') == []
        assert _words(tree, 'say hello ') == []

    def test_nothing_after_words_that_don_t_read(self, tree):
        assert _words(tree, 'frob ') == []
        assert _words(tree, 'fleet f1 frob ') == []


class TestNames:
    def test_a_name_s_options(self, tree):
        assert _words(tree, 'fleet ', farlandia.NAMES) == ['Prospector', 'Hauler']
        assert _words(tree, 'fleets merge f1 --into ', farlandia.NAMES) == ['Prospector', 'Hauler']

    def test_scoped_by_the_scope_as_typed(self, tree):
        assert _words(tree, 'fleet Prospector dock ', farlandia.NAMES) == [
            'Vesta',
            '"Vruba\'a Belt 1"',
            'nearest',
            'then',
        ]
        assert _words(tree, 'fleet Hauler dock ', farlandia.NAMES) == ['Ceres', 'nearest', 'then']

    def test_a_scope_given_as_a_flag(self):
        assert _words(Tree([Board]), 'board --fleet Hauler ', farlandia.NAMES) == ['Ceres']

    def test_a_name_with_a_double_quote_offered_escaped(self, tree):
        names = {**farlandia.NAMES, 'fleet': farlandia.Table({'The "Q"': 'q'})}
        assert _words(tree, 'fleet ', names) == [r'"The \"Q\""']
        assert tree.read(r'fleet "The \"Q\"" mine', names=names).fleet == 'q'  # typed as offered, it reads

    def test_a_name_with_a_space_offered_quoted(self, tree):
        assert tree.complete('fleet Prospector dock vr', farlandia.NAMES) == Completion(
            words=['"Vruba\'a Belt 1"'], replace=2
        )

    def test_within_an_open_quote(self, tree):
        assert tree.complete('fleet Prospector dock "Vru', farlandia.NAMES) == Completion(
            words=['"Vruba\'a Belt 1"'], replace=4
        )

    def test_a_quoted_word_is_offered_no_literal(self, tree):
        assert _words(tree, 'fleet Prospector dock "', farlandia.NAMES) == ['Vesta', '"Vruba\'a Belt 1"']

    def test_another_of_a_list_s_names(self, tree):
        assert _words(tree, 'fleet f1 sell iron ', farlandia.NAMES) == ['Iron', 'Coal', 'then']

    def test_no_resolver_no_names(self, tree):
        assert _words(tree, 'fleet ') == []

    def test_a_scope_whose_resolver_says_why_as_one_that_names_nothing(self, tree):
        fleets = farlandia.Saying(farlandia.NAMES['fleet'], 'no fleet {word!r}')
        names = {**farlandia.NAMES, 'fleet': fleets}
        assert _words(tree, 'fleet Nobody dock ', names) == _words(tree, 'fleet Nobody dock ', farlandia.NAMES)
        assert _words(tree, 'fleet Hauler dock ', names) == ['Ceres', 'nearest', 'then']


class TestPairs:
    def test_the_keys_scoped_by_the_routine(self, tree):
        assert _words(tree, 'fleet f1 run mining ', farlandia.NAMES) == ['ore', 'home']
        assert _words(tree, 'fleet f1 run patrol ', farlandia.NAMES) == ['route']

    def test_a_key_s_values(self, tree):
        assert _words(tree, 'fleet f1 run mining ore ', farlandia.NAMES) == ['Iron', 'Coal']
        assert _words(tree, 'fleet f1 run mining ore iron home V', farlandia.NAMES) == ['Vesta', '"Vruba\'a Belt 1"']

    def test_a_key_given_isn_t_offered_again(self, tree):
        assert _words(tree, 'fleet f1 run mining ore iron ', farlandia.NAMES) == ['home']

    def test_a_key_whose_values_read_as_typed(self, tree):
        assert _words(tree, 'fleet f1 run patrol route ', farlandia.NAMES) == []

    def test_a_key_whose_resolver_says_why_as_one_that_names_nothing(self, tree):
        names = {**farlandia.NAMES, 'variable': farlandia.Saying(farlandia.NAMES['variable'], 'no variable {word!r}')}
        assert _words(tree, 'fleet f1 run mining hme ', names) == []
        assert _words(tree, 'fleet f1 run mining ore ', names) == ['Iron', 'Coal']


@parsed.parsed
class Run(Command):
    """A routine taken up, its variables in pairs, and its place in the list as a flag."""

    PHRASE = 'run {routine} {variables**}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {
        'routine': parsed.Name('routine'),
        'variables': parsed.kinds.Pairs('variable', scope='routine'),
    }

    routine: str = parsed.Str(required=True)
    variables: dict[str, str] = parsed.Str(keyed=True, default_factory=dict)
    at: int | None = parsed.Int(default=None, ge=1)


class TestFlagsAfterTheRest:
    # Flags may stand anywhere after the first word, so the rest of the line offers its command's too.
    def test_beside_a_pair_s_keys_and_values(self):
        run = Tree([Run])
        assert _words(run, 'run mining ', farlandia.NAMES) == ['ore', 'home', '--at']
        assert _words(run, 'run mining ore ', farlandia.NAMES) == ['Iron', 'Coal', '--at']
        assert _words(run, 'run mining ore iron ', farlandia.NAMES) == ['home', '--at']

    def test_not_once_given(self):
        assert _words(Tree([Run]), 'run mining --at 2 ore iron ', farlandia.NAMES) == ['home']

    def test_with_no_resolver_the_flags_alone(self):
        assert _words(Tree([Run]), 'run mining home ') == ['--at']

    def test_after_free_text(self):
        say = Tree([_command('say {message**}', message=parsed.Str(required=True), loud=parsed.Bool(default=False))])
        assert _words(say, 'say hello ') == ['--loud']
        assert say.complete('say hello --l') == Completion(words=['--loud'], replace=3)


@parsed.parsed
class Send(Command):
    """Send on or not, by someone: a slot after a flag that has a short form."""

    PHRASE = 'send {on}'
    SHORTS: ClassVar[dict[str, str]] = {'by': 'b'}

    on: bool = parsed.Bool(required=True)
    by: str = parsed.Str(default='')


class TestShortFlags:
    def test_a_short_s_value_is_its_flag_s_not_a_slot_s(self):
        send = Tree([Send])
        assert _words(send, 'send -b ann ') == _words(send, 'send --by ann ') == ['true', 'false']


class TestFarlandiasCases:
    """farlandia's own completion cases (``tests/client/test_tree.py``), on this fixture's commands.

    Lifted: the first words, a node's words, a command's flags, a span's values, a literal beside a slot, ``--yes``
    for a command asked first, and a flag being typed; and, from a port of farlandia's tree, a routine's flags after
    its pairs. ``then`` is :class:`TestChains`'.
    """

    def test_completion_offers_words_slots_and_flags(self, tree):
        assert _words(tree, 'fleet f1 ') == ['mine', 'dock', 'jump', 'move', 'retreat', 'run', 'sell', 'buy']
        assert _words(tree, 'fleet f1 mine ') == ['then', '--for']  # a step: another may follow
        assert _words(tree, 'fleet f1 mine --for ') == ['10m', '30m', '1h']
        assert _words(tree, 'fleet f1 jump ') == ['nearest']
        assert _words(tree, 'fleet f1 dock ') == ['nearest', 'then']
        assert _words(tree, 'fleets merge f1 ') == ['--into', '--quiet', '--yes']
        assert tree.complete('fleets merge f1 --q') == Completion(words=['--quiet'], replace=3)


def test_a_completion_unpacks():
    words, replace = Tree.collect('_support_farlandia').complete('lo')
    assert (words, replace) == (['log'], 2)


def _command(phrase: str, **fields: object) -> type[Command]:
    namespace: dict[str, object] = {'PHRASE': phrase, '__annotations__': dict.fromkeys(fields, object)}
    namespace.update(fields)
    return parsed.parsed(type('Cmd', (Command,), namespace))


@parsed.parsed
class Board(Command):
    """A station boarded, scoped by a fleet given as a flag."""

    PHRASE = 'board {station}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {
        'station': parsed.Name('station', scope='fleet'),
        'fleet': farlandia.FLEET,
    }

    station: str = parsed.Str(required=True)
    fleet: str | None = parsed.Str(default=None)


@pytest.mark.parametrize(
    ('text', 'before', 'typing'),
    [
        ('', [], None),
        ('fleet f', ['fleet'], 'f'),
        ('fleet f1 ', ['fleet', 'f1'], None),
        ('fleet "Vruba', ['fleet'], 'Vruba'),  # an open quote holds the word being typed, spaces and all
    ],
)
def test_the_word_being_typed(text, before, typing):
    tokens, partial = being_typed(text)
    assert [token.text for token in tokens] == before
    assert (partial.text if partial else None) == typing


class TestWaits:
    def test_a_read_that_can_wait_offers_its_flags(self, tree):
        assert {'--until', '--timeout'} <= set(_words(tree, 'fleets show f1 --'))
        assert '--until' not in _words(tree, 'fleet f1 mine --')

    def test_until_again_but_the_bound_once(self, tree):
        offered = _words(tree, 'fleets show f1 --until docked=true --timeout 1m --')
        assert '--until' in offered
        assert '--timeout' not in offered

    def test_a_condition_on_each_of_the_reply_s_fields(self, tree):
        assert _words(tree, 'fleets show f1 --until ') == ['fleet=', 'docked=']
        assert _words(tree, 'fleets show f1 --until d') == ['docked=']

    def test_a_watch_and_its_count(self, tree):
        offered = _words(tree, 'fleets show f1 --')
        assert {'--watch', '--count'} <= set(offered)
        assert _words(tree, 'fleets show f1 --watch --count ') == ['1', '5', '10']
        assert '--watch' not in _words(tree, 'fleets show f1 --watch --')

    def test_a_few_bounds(self, tree):
        assert _words(tree, 'fleets show f1 --until docked=true --timeout ') == ['30s', '1m', '2m', '5m']


class TestChains:
    def test_then_after_a_step(self, tree):
        assert 'then' in _words(tree, 'fleet f1 jump sol ')
        assert 'then' not in _words(tree, 'fleet f1 retreat 30 ')  # not a step
        assert 'then' not in _words(tree, 'log ')

    def test_after_then_the_chain_s_steps(self, tree):
        assert _words(tree, 'fleet f1 jump sol then ') == ['mine', 'dock', 'jump', 'move', 'sell']
        assert tree.complete('fleet f1 jump sol then m') == Completion(['mine', 'move'], 1)

    def test_a_later_step_s_words_and_names(self, tree):
        assert _words(tree, 'fleet f1 jump sol then move belt ') == ['then']
        assert _words(tree, 'fleet Hauler jump sol then dock ', farlandia.NAMES) == ['Ceres', 'nearest', 'then']

    def test_nothing_after_steps_that_don_t_read(self, tree):
        assert _words(tree, 'fleet f1 jump then ') == []
        assert _words(tree, 'fleet f1 mine then zzz ') == []

    def test_then_as_a_word_of_a_command_that_isn_t_a_step(self, tree):
        assert _words(tree, 'say hello then ') == []


class TestChainPlace:
    # A later step's names, offered where the steps before it have moved the fleet.
    def test_where_the_fleet_will_be(self, tree):
        assert _words(tree, 'fleet Prospector dock ', farlandia.NAMES) == [
            'Vesta',
            '"Vruba\'a Belt 1"',
            'nearest',
            'then',
        ]
        assert _words(tree, 'fleet Prospector jump sol then dock ', farlandia.NAMES) == ['Ceres', 'nearest', 'then']
        line = 'fleet Prospector jump sol then move "Sol Belt" then move '
        assert _words(tree, line, farlandia.NAMES) == ['Ceres', '"Sol Belt"']

    def test_until_a_step_moves_it(self, tree):
        offered = _words(tree, 'fleet Prospector mine then dock ', farlandia.NAMES)
        assert offered == ['Vesta', '"Vruba\'a Belt 1"', 'nearest', 'then']

    def test_somewhere_the_line_doesn_t_say_every_name(self, tree):
        offered = _words(tree, 'fleet Prospector jump nearest iron then move ', farlandia.NAMES)
        assert offered == ['Vesta', '"Vruba\'a Belt 1"', '"Vruba Rings"', 'Ceres', '"Sol Belt"']


class TestBeneath:
    # For help short of a command: the commands a line's words may still say.
    def _phrases(self, tree: Tree, line: str) -> list[str] | None:
        ends = beneath(tree, split(line))
        return None if ends is None else list(dict.fromkeys(end.bound.phrase.text for end in ends))

    def test_every_command_beneath_in_the_tree_s_order(self, tree):
        jumps = ['fleet {fleet} jump nearest {ore}', 'fleet {fleet} jump {system}']
        assert self._phrases(tree, 'fleet f1 jump') == jumps
        every = {bound.phrase.text for found in tree.commands for bound in found.phrases}
        assert set(self._phrases(tree, '') or ()) == every  # every phrase, extra ones among them

    def test_its_own_where_it_says_a_command(self, tree):
        assert self._phrases(tree, 'log --help') == ['log {n}']  # with its slot and without, one phrase

    def test_flags_split_off_by_the_tree(self, tree):
        assert self._phrases(tree, 'fleet f1 mine --for soon --help') == ['fleet {fleet} mine']

    def test_none_where_a_word_goes_nowhere(self, tree):
        assert self._phrases(tree, 'flet') is None


class TestGoes:
    # Whether words go along a tree as far as they're given, read loosely: for a session's subjects.
    @pytest.mark.parametrize(
        ('words', 'goes_on'),
        [
            ('fleet prospector', True),  # a slot takes any word
            ('fleet prospector mine', True),
            ('detachment scouts dock', False),  # a detachment's only step here is mine
            ('fleet', True),
            ('flet', False),
            ('log 5 more', False),  # left over
        ],
    )
    def test_words_that_go_on(self, tree, words, goes_on):
        assert goes(tree, split(words)) is goes_on
