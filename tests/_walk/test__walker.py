"""Tests for ``parsed/_walk/_walker.py``: a line's flags split off, its words walked, each field's words kept."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import ClassVar

import _support_farlandia as farlandia
import _support_rio as rio
import pytest

import parsed
from parsed.command import Command
from parsed.errors import ReadError
from parsed.tree import Flag, Tree
from parsed.wait import Condition, Wait


def _command(phrase: str, **fields: object) -> type[Command]:
    """A decorated command with ``phrase`` and ``fields``, each annotated as an ``object``."""
    namespace: dict[str, object] = {'PHRASE': phrase, '__annotations__': dict.fromkeys(fields, object)}
    namespace.update(fields)
    return parsed.parsed(type('Cmd', (Command,), namespace))


def _one(phrase: str, **fields: object) -> Tree:
    return Tree([_command(phrase, **fields)])


@pytest.fixture(scope='module')
def tree() -> Tree:
    return Tree.collect('_support_farlandia', '_support_rio')


class TestEveryFixture:
    # Each fixture command, read from a line to the instance, its names kept as typed.
    @pytest.mark.parametrize(
        ('line', 'expected'),
        [
            ('fleet prospector mine', farlandia.FleetMine(fleet='prospector')),
            ('detachment d2 mine --for 90s', farlandia.FleetMine(fleet='d2', for_=timedelta(seconds=90))),
            ('fleet f1 dock', farlandia.FleetDock(fleet='f1')),
            ('fleet f1 dock nearest', farlandia.FleetDock(fleet='f1')),
            ('fleet f1 dock vesta', farlandia.FleetDock(fleet='f1', station='vesta')),
            ('fleet f1 jump sol', farlandia.FleetJump(fleet='f1', system='sol')),
            ('fleet f1 jump nearest iron', farlandia.FleetJumpNearest(fleet='f1', ore='iron')),
            ('fleet f1 sell iron coal', farlandia.FleetSell(fleet='f1', goods=['iron', 'coal'])),
            ('log', farlandia.Log()),
            ('log 40', farlandia.Log(n=40)),
            ('say hello there', farlandia.Say(message='hello there')),
            ('fleet "Vruba\'a 1" buy ship hauler', farlandia.FleetBuyShip(fleet="Vruba'a 1", hull='hauler')),
            ('fleets merge f1 --into f2', farlandia.FleetsMerge(fleet='f1', into='f2')),
            ('fleets show f1', farlandia.FleetsShow(fleet='f1')),
            ('ships make s1 add drill', farlandia.ShipsMakeAdd(ship='s1', part='drill')),
            ('ship s1 fit', farlandia.ShipFit(ship='s1')),
            (
                'handheld connect dock r7 --host 10.0.0.2 --port 5085',
                rio.HandheldConnect(source='dock', reader_id='r7', host='10.0.0.2', port=5085),
            ),
        ],
    )
    def test_a_line_reads_to_its_instance(self, tree, line, expected):
        assert tree.read(line) == expected


class TestWords:
    def test_literals_match_case_aside_and_values_keep_theirs(self, tree):
        assert tree.read('FLEET Prospector Mine') == farlandia.FleetMine(fleet='Prospector')

    def test_a_literal_beats_a_slot(self, tree):
        assert tree.walk('fleet f1 jump nearest iron').command is farlandia.FleetJumpNearest
        assert tree.walk('fleet f1 jump nearer').command is farlandia.FleetJump

    def test_a_quoted_word_is_never_a_literal(self, tree):
        assert tree.read('fleet f1 jump "nearest"') == farlandia.FleetJump(fleet='f1', system='nearest')
        assert tree.read('fleet f1 dock "nearest"') == farlandia.FleetDock(fleet='f1', station='nearest')

    def test_a_renamed_slot_fills_its_field(self, tree):
        given = tree.walk('detachment d2 mine').given['fleet']
        assert (given.by.slot, given.field, given.value) == ('detachment', 'fleet', 'd2')

    def test_several_words_up_to_a_literal_after_them(self):
        sell = _one('sell {goods} now', goods=parsed.Str(many=True, required=True))
        assert sell.read('sell iron coal now').goods == ['iron', 'coal']
        assert sell.read('sell "now" now').goods == ['now']

    def test_the_rest_of_the_line_single_spaced(self, tree):
        assert tree.read('say hello   there  galaxy').message == 'hello there galaxy'

    def test_the_rest_of_the_line_into_a_list(self):
        note = _one('note {words**}', words=parsed.Str(many=True, required=True))
        assert note.read('note one two').words == ['one', 'two']

    def test_a_field_left_out_keeps_its_default(self, tree):
        reading = tree.walk('log')
        assert dict(reading.given) == {}
        assert reading.load() == farlandia.Log(n=20)


class TestWordForms:
    # Each kind's own words are `tests/test_kinds.py`'s; these pin the walk reading by them.
    def test_a_slot_s_word_read_by_its_kind(self, tree):
        reading = tree.walk('log 1,000')
        assert reading.data() == {'n': 1000}
        assert reading.load() == farlandia.Log(n=1000)

    def test_a_flag_s_word_read_by_its_kind(self, tree):
        assert tree.walk('fleet f1 mine --for 1h30m').data() == {'fleet': 'f1', 'for': 5400.0}
        assert tree.walk('handheld connect dock r7 --host h --port 5,085').given['port'].value == 5085

    def test_a_list_s_words_each_read(self):
        tag = _one('tag {ns}', ns=parsed.Int(many=True, required=True))
        assert tag.read('tag 1 2,000 3').ns == [1, 2000, 3]
        flagged = _one('tag', ns=parsed.Int(many=True, default_factory=list))
        assert flagged.read('tag --ns 1 --ns 2').ns == [1, 2]

    def test_the_rest_of_the_line_read_once(self, tree):
        assert tree.walk('say 1,000 ships').given['message'].value == '1,000 ships'

    def test_a_bool_said_as_a_word(self, tree):
        assert tree.read('fleets start FALSE') == farlandia.FleetsStart(on=False)

    @pytest.mark.parametrize(
        ('line', 'says'),
        [
            ('log many', r"log \{n\}: 'many' is not a whole number"),
            ('fleet f1 mine --for soon', r"--for: 'soon' is not a span of time: say 90s, 10m, 2h or 1h30m"),
            ('fleet f1 mine --for 90', r"--for: '90' is not a span of time"),
            ('fleets start maybe', r"fleets start \{on\}: 'maybe' is not true or false"),
            ('handheld connect dock r7 --host h --port 1,00', r"--port: '1,00' is not a whole number"),
        ],
    )
    def test_a_word_its_kind_can_t_read_says_where_it_stands(self, tree, line, says):
        with pytest.raises(ReadError, match=says):
            tree.walk(line)

    def test_a_kind_s_bounds_are_seared_s_to_check(self, tree):
        reading = tree.walk('log 0')
        assert reading.data() == {'n': 0}
        with pytest.raises(ReadError, match=r'log \{n\}: must be >= 1, got 0'):
            reading.load()

    def test_load_refuses_a_key_the_command_doesn_t_know(self, tree, monkeypatch):
        reading = tree.walk('log 40')
        monkeypatch.setattr(type(reading), 'data', lambda _: {'n': 40, 'lines': 3})
        with pytest.raises(ReadError, match=r'log \{n\}: unknown key') as caught:
            reading.load()
        assert (caught.value.kind, caught.value.field) == ('validation', None)


class _Recording:
    """A resolver that keeps what it was asked, around the fixture's own."""

    def __init__(self, inner):
        self.inner, self.asked = inner, []

    def lookup(self, word, scope):
        self.asked.append((word, scope))
        return self.inner.lookup(word, scope)

    def suggest(self, word, scope):
        return self.inner.suggest(word, scope)

    def options(self, scope):
        return self.inner.options(scope)

    def values(self, key, scope):
        return self.inner.values(key, scope)


@parsed.parsed
class Board(Command):
    """A station boarded, scoped by a fleet given after it, or not at all."""

    PHRASE = 'board {station}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {
        'station': parsed.Name('station', scope='fleet'),
        'fleet': farlandia.FLEET,
    }

    station: str = parsed.Str(required=True)
    fleet: str | None = parsed.Str(default=None)


class TestNames:
    def test_a_name_reads_to_its_key(self, tree):
        assert tree.read('fleet Prospector mine', names=farlandia.NAMES) == farlandia.FleetMine(fleet='f1')
        assert tree.read('fleet f1 mine', names=farlandia.NAMES).fleet == 'f1'  # a key, as the resolver takes one

    def test_a_name_with_spaces_and_an_apostrophe(self, tree):
        found = tree.read('fleet f1 dock "Vruba\'a Belt 1"', names=farlandia.NAMES)
        assert found.station == 'vrubaa-belt-1'

    def test_scoped_by_another_field_s_key(self, tree):
        assert tree.read('fleet Hauler dock ceres', names=farlandia.NAMES).station == 'ceres'
        with pytest.raises(ReadError, match=r"no station 'vesta' for fleet 'Hauler'"):
            tree.read('fleet Hauler dock vesta', names=farlandia.NAMES)

    def test_a_scope_is_read_first_whatever_its_place(self):
        stations = _Recording(farlandia.NAMES['station'])
        names = {**farlandia.NAMES, 'station': stations}
        assert Tree([Board]).read('board ceres --fleet Hauler', names=names).station == 'ceres'
        assert stations.asked == [('ceres', 'f2')]  # the fleet's key, read before the station

    def test_a_scope_left_out_looks_across_them_all(self):
        stations = _Recording(farlandia.NAMES['station'])
        assert Tree([Board]).read('board vesta', names={'station': stations}).station == 'vesta'
        assert stations.asked == [('vesta', None)]

    def test_a_renamed_slot_reads_by_its_own_category(self, tree):
        assert tree.read('detachment Scouts mine', names=farlandia.NAMES) == farlandia.FleetMine(fleet='d2')
        with pytest.raises(ReadError, match=r"detachment \{detachment\} mine: no detachment 'Prospector'"):
            tree.read('detachment Prospector mine', names=farlandia.NAMES)

    def test_each_of_a_list_s_names(self, tree):
        assert tree.read('fleet f1 sell iron Coal', names=farlandia.NAMES).goods == ['iron', 'coal']

    def test_a_flag_s_name(self, tree):
        assert tree.read('fleets merge Prospector --into hauler', names=farlandia.NAMES).into == 'f2'

    def test_a_category_with_no_resolver_reads_as_typed(self, tree):
        found = tree.read('fleet Prospector dock Vesta', names={'fleet': farlandia.NAMES['fleet']})
        assert (found.fleet, found.station) == ('f1', 'Vesta')
        assert tree.read('fleet Prospector mine').fleet == 'Prospector'

    def test_a_word_no_name_answers_to(self, tree):
        found = _refusal(tree, 'fleets merge Prospector --into Haulr', names=farlandia.NAMES)
        assert str(found) == (
            "--into: no fleet 'Haulr'; did you mean Hauler? `fleets merge <fleet> --into <into> [--quiet]`"
        )
        assert (found.kind, found.column, found.word, found.field) == ('usage', 31, 'Haulr', 'into')
        assert found.suggestions == ('Hauler',)
        assert found.hint == 'fleets merge <fleet> --into <into> [--quiet]'

    def test_a_list_s_word_no_name_answers_to(self, tree):
        found = _refusal(tree, 'fleet f1 sell iron gold', names=farlandia.NAMES)
        assert (found.word, found.column, found.field) == ('gold', 19, 'goods')
        assert found.message.startswith("fleet {fleet} sell {goods}: no good 'gold'")


class TestLiteralWords:
    def test_a_share_in_percent_or_off(self, tree):
        assert tree.read('fleet f1 retreat 30%').share == 30.0
        assert tree.read('fleet f1 retreat 30').share == 30.0
        assert tree.read('fleet f1 retreat OFF') == farlandia.FleetRetreat(fleet='f1', share=None)
        assert tree.walk('fleet f1 retreat off').data() == {'fleet': 'f1', 'share': None}

    def test_a_quoted_word_is_never_a_literal(self, tree):
        with pytest.raises(ReadError, match=r"retreat \{share\}: 'off' is not a number"):
            tree.walk('fleet f1 retreat "off"')

    def test_the_share_s_bounds_are_seared_s(self, tree):
        with pytest.raises(ReadError, match=r'retreat \{share\}: must be >= 5, got 2\.0'):
            tree.read('fleet f1 retreat 2%')

    def test_a_name_s_literal_comes_before_its_resolver(self):
        @parsed.parsed
        class Dock(Command):
            PHRASE = 'dock {station}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'station': parsed.Name('station', words={'here': None})}

            station: str | None = parsed.Str(required=True, nullable=True)

        docks = Tree([Dock])
        assert docks.read('dock here', names=farlandia.NAMES).station is None
        assert docks.read('dock Vesta', names=farlandia.NAMES).station == 'vesta'
        with pytest.raises(ReadError, match=r"no station 'here'"):  # quoted: a station's name, not the literal
            docks.read('dock "here"', names=farlandia.NAMES)


class TestPairs:
    def test_each_key_and_its_value_read_by_its_own_names(self, tree):
        found = tree.read('fleet Prospector run Mining ore Iron home "Vruba\'a Belt 1"', names=farlandia.NAMES)
        assert found == farlandia.FleetRun(
            fleet='f1', routine='mining', variables={'ore': 'iron', 'home': 'vrubaa-belt-1'}
        )

    def test_the_keys_scoped_by_the_routine(self):
        variables = _Recording(farlandia.NAMES['variable'])
        names = {**farlandia.NAMES, 'variable': variables}
        Tree.collect('_support_farlandia').read('fleet f1 run Mining ore iron', names=names)
        assert variables.asked == [('ore', 'mining')]

    def test_a_key_whose_values_read_as_typed(self, tree):
        assert tree.read('fleet f1 run patrol route North', names=farlandia.NAMES).variables == {'route': 'North'}

    def test_with_no_resolver_as_typed(self, tree):
        assert tree.read('fleet f1 run mining ore Iron').variables == {'ore': 'Iron'}

    def test_none_given(self, tree):
        assert tree.read('fleet f1 run mining', names=farlandia.NAMES).variables == {}

    @pytest.mark.parametrize(
        ('line', 'says', 'word'),
        [
            (
                'fleet f1 run mining ore iron hme vesta',
                r"no variable 'hme' for routine 'mining'; did you mean home\? `fleet <fleet> run <routine>",
                'hme',
            ),
            ('fleet f1 run mining home mars', r"run \{routine\} \{variables\*\*\}: no home 'mars'", 'mars'),
            ('fleet f1 run mining ore iron home', r"'home' and its value\? pairs come in twos", 'home'),
            ('fleet f1 run mining ore iron ore coal', r'ore is given twice', 'ore'),
        ],
    )
    def test_what_doesn_t_read(self, tree, line, says, word):
        found = _refusal(tree, line, names=farlandia.NAMES)
        assert re.search(says, str(found))
        assert (found.word, found.field) == (word, 'variables')

    def test_a_plain_resolver_for_pairs_is_a_mistake_in_the_app(self, tree):
        names = {**farlandia.NAMES, 'variable': farlandia.Table({'ore': 'ore'})}
        with pytest.raises(TypeError, match=r'the resolver for variable reads pairs, so it gives values'):
            tree.read('fleet f1 run mining ore iron', names=names)


class TestPlaceholders:
    # A `<name>` word stands for any value, so a line in help or an example reads with no real one.
    def test_any_value_read_by_no_kind(self, tree):
        reading = tree.walk('fleet <fleet> mine --for <for>', placeholders=True)
        assert reading.command is farlandia.FleetMine
        assert reading.data() == {'fleet': '<fleet>', 'for': '<for>'}

    def test_a_number_s_slot_and_a_pair_s_words(self, tree):
        assert tree.walk('log <n>', placeholders=True).data() == {'n': '<n>'}
        reading = tree.walk('fleet <fleet> run <routine> <variable> <value>', placeholders=True)
        assert reading.data()['variables'] == {'<variable>': '<value>'}

    def test_read_by_no_resolver(self, tree):
        stations = _Recording(farlandia.NAMES['station'])
        names = {**farlandia.NAMES, 'station': stations}
        assert tree.walk('fleet <fleet> dock <station>', names, placeholders=True).data()['station'] == '<station>'
        assert stations.asked == []

    def test_a_literal_still_reads_as_one(self, tree):
        assert tree.walk('fleet <fleet> dock nearest', placeholders=True).data() == {'fleet': '<fleet>'}

    def test_never_a_literal_word(self, tree):
        with pytest.raises(ReadError, match=r"no command 'fleet <fleet> <verb>'"):
            tree.walk('fleet <fleet> <verb>', placeholders=True)

    def test_only_when_asked(self, tree):
        with pytest.raises(ReadError, match=r"log \{n\}: '<n>' is not a whole number"):
            tree.walk('log <n>')

    def test_a_quoted_one_is_a_value(self, tree):
        with pytest.raises(ReadError, match=r"log \{n\}: '<n>' is not a whole number"):
            tree.walk('log "<n>"', placeholders=True)

    def test_its_reading_doesn_t_load(self, tree):
        with pytest.raises(ReadError):
            tree.walk('log <n>', placeholders=True).load()


class TestWaits:
    # A read with a REPLY takes --until and --timeout, read and checked before anything runs.
    def test_a_condition_and_the_default_bound(self, tree):
        reading = tree.walk('fleets show f1 --until docked=true')
        assert reading.wait == Wait((Condition(path=('docked',), value=True, text='docked=true'),), 30.0)
        assert reading.data() == {'fleet': 'f1'}  # a wait's flags are no field's

    def test_several_conditions_and_a_bound(self, tree):
        reading = tree.walk('fleets show f1 --until docked=true --timeout 2m --until=fleet=f1')
        assert [condition.text for condition in reading.wait.until] == ['docked=true', 'fleet=f1']
        assert reading.wait.timeout == 120.0

    def test_none_without_until(self, tree):
        assert tree.walk('fleets show f1').wait is None
        assert tree.walk('fleet f1 mine').wait is None

    @pytest.mark.parametrize(
        ('line', 'says', 'word'),
        [
            (
                'fleets show f1 --until dockd=true',
                "--until 'dockd' names no field of FleetView; did you mean 'docked'?",
                'dockd=true',
            ),
            (
                'fleets show f1 --until docked',
                (
                    "--until: a condition is path=value, the path dotted (docked, cargo.iron), not 'docked' "
                    '`--until <path>=<value>`'
                ),
                'docked',
            ),
            (
                'fleets show f1 --timeout 2m',
                '--timeout bounds a wait or a watch: give --until or --watch too',
                '--timeout',
            ),
            ('fleets show f1 --count 3', '--count is how many replies a watch gives: give --watch too', '--count'),
            ('fleets show f1 --watch --count 0', "--count: '0' is not a number of replies: say 1 or more", '0'),
            ('fleets show f1 --watch --count lots', "--count: 'lots' is not a number of replies", 'lots'),
            ('fleets show f1 --watch --watch', '--watch is given twice', '--watch'),
            ('fleet f1 mine --watch', "fleet f1 mine can't wait: --watch is for a read", '--watch'),
            (
                'fleets show f1 --until docked=true --timeout 1m --timeout 2m',
                '--timeout is given twice',
                '--timeout',
            ),
            (
                'fleets show f1 --until docked=true --timeout soon',
                "--timeout: 'soon' is not a span of time: say 90s, 10m, 2h or 1h30m",
                'soon',
            ),
            (
                'fleet f1 mine --until docked=true',
                (
                    "fleet f1 mine can't wait: --until is for a read, a command that declares EFFECT = READ and a "
                    'REPLY `fleet <fleet> mine [--for <for>]`'
                ),
                '--until',
            ),
            ('log --timeout 2m', "log can't wait: --timeout is for a read", '--timeout'),
        ],
    )
    def test_refused_before_anything_runs(self, tree, line, says, word):
        found = _refusal(tree, line)
        assert str(found).startswith(says)
        assert found.word == word

    def test_a_path_s_near_names_as_suggestions(self, tree):
        assert _refusal(tree, 'fleets show f1 --until dockd=true').suggestions == ('docked',)

    def test_placeholders_stand_for_a_condition_and_a_bound(self, tree):
        reading = tree.walk('fleets show <fleet> --until <until> --timeout <timeout>', placeholders=True)
        assert reading.wait == Wait((), 30.0)
        assert tree.walk('fleets show <fleet> --watch --count <count>', placeholders=True).wait == Wait(
            (), None, watch=True
        )

    def test_a_watch_with_no_bound_of_its_own(self, tree):
        assert tree.walk('fleets show f1 --watch').wait == Wait((), None, watch=True)
        assert tree.walk('fleets show f1 --watch --count 1,000 --timeout 5m').wait == Wait(
            (), 300.0, watch=True, count=1000
        )

    def test_a_watch_until_its_conditions_has_their_bound(self, tree):
        found = tree.walk('fleets show f1 --watch --until docked=true').wait
        assert (found.watch, found.timeout, len(found.until)) == (True, 30.0, 1)


class TestChains:
    # A chain's steps, joined by `then`: each a reading, the later ones read where the chain's shared part ends.
    def test_each_step_a_reading(self, tree):
        reading = tree.walk('fleet f1 jump sol then move belt then mine')
        assert [step.command for step in reading.steps] == [
            farlandia.FleetJump,
            farlandia.FleetMove,
            farlandia.FleetMine,
        ]
        assert [step.data() for step in reading.steps] == [
            {'fleet': 'f1', 'system': 'sol'},
            {'fleet': 'f1', 'to': 'belt'},  # the shared fleet, from the first step
            {'fleet': 'f1'},
        ]
        assert reading.chain is farlandia.FleetCommand
        assert reading.then == reading.steps[1:]

    def test_its_phrase(self, tree):
        reading = tree.walk('fleet f1 jump nearest iron then dock vesta then mine')
        assert reading.phrase == 'fleet {fleet} jump nearest {ore} then dock {station} then mine'

    def test_a_twin_s_steps_read_under_its_own_words(self, tree):
        reading = tree.walk('detachment d2 mine then mine')
        assert [step.data() for step in reading.steps] == [{'fleet': 'd2'}, {'fleet': 'd2'}]
        with pytest.raises(ReadError, match=r"no command 'detachment d2 mine then dock': mine"):
            tree.walk('detachment d2 mine then dock')  # a detachment's only step here is mine

    def test_each_step_s_own_flags(self, tree):
        reading = tree.walk('fleet f1 mine --for 90s then sell iron coal --yes')
        assert [step.data() for step in reading.steps] == [
            {'fleet': 'f1', 'for': 90.0},
            {'fleet': 'f1', 'goods': ['iron', 'coal']},
        ]
        assert reading.own == {'yes'}  # parsed's own, for the whole line

    def test_names_by_their_resolvers_in_every_step(self, tree):
        reading = tree.walk('fleet Prospector mine then dock vesta', names=farlandia.NAMES)
        assert [step.data() for step in reading.steps] == [{'fleet': 'f1'}, {'fleet': 'f1', 'station': 'vesta'}]

    def test_a_line_of_one_step(self, tree):
        reading = tree.walk('fleet f1 mine')
        assert (reading.chain, reading.then, reading.steps) == (farlandia.FleetCommand, (), (reading,))

    @pytest.mark.parametrize(
        ('line', 'expected'),
        [
            ('say hello then goodbye', farlandia.Say(message='hello then goodbye')),  # not a step: one command
            ('fleets merge f1 --into then', farlandia.FleetsMerge(fleet='f1', into='then')),  # a flag's value
        ],
    )
    def test_then_that_joins_nothing_is_a_word(self, tree, line, expected):
        assert tree.read(line) == expected

    @pytest.mark.parametrize(
        ('line', 'says', 'word'),
        [
            ('fleet f1 mine then', '`then` needs a step on each side: dock then sell', 'then'),
            ('then fleet f1 mine', '`then` needs a step on each side', 'then'),
            ('fleet f1 mine then then dock', '`then` needs a step on each side', 'then'),
            ('fleet f1 retreat 30% then mine', "`then` joins steps: 'fleet f1 retreat 30%' is not one", 'then'),
            (
                'fleet f1 mine then retreat 30%',
                "`then` joins steps: 'retreat 30%' is not one of FleetCommand's",
                'retreat',
            ),
            ('fleet f1 jump then mine', 'fleet f1 jump: which system? `fleet f1 jump <system>`', None),
            (
                'fleet f1 jump sol then move',
                'fleet f1 jump sol then move: which to? `fleet f1 jump sol then move <to>`',
                None,
            ),
            ('fleet f1 jump sol then mov belt', "no command 'fleet f1 jump sol then mov'; did you mean move?", 'mov'),
            (
                'fleets show f1 --until docked=true then mine',
                "`then` joins steps: 'fleets show f1 --until docked=true' is not one",
                'then',
            ),
        ],
    )
    def test_refused(self, tree, line, says, word):
        found = _refusal(tree, line)
        assert str(found).startswith(says)
        assert found.word == word

    def test_after_then_only_the_chain_s_steps(self, tree):
        found = _refusal(tree, 'fleet f1 mine then zzz')
        assert found.suggestions == ('mine', 'dock', 'jump', 'move', 'sell')


@parsed.parsed
class _Ship(Command):
    """A chain's base whose names a step's scope may follow or not: where a ship goes, and what it carries."""

    STEPS = True

    ship: str = parsed.Str(required=True)


@parsed.parsed
class _ShipWarp(_Ship):
    PHRASE = 'ship {ship} warp'
    MOVES = 'to'

    to: str = parsed.Str(required=True)  # a flag: --to


@parsed.parsed
class _ShipLoad(_Ship):
    PHRASE = 'ship {ship} load {good} at {site}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {
        'good': parsed.Name('good', scope='ship'),  # its hold: wherever it is
        'site': parsed.Name('site', scope='ship', follows=True),
    }

    good: str = parsed.Str(required=True)
    site: str = parsed.Str(required=True)


_SHIP_NAMES = {
    'good': farlandia.Table({'Iron': 'iron'}, within={'s1': {'iron'}}),
    'site': farlandia.Table({'Vesta': 'vesta', 'Ceres': 'ceres'}, within={'s1': {'vesta'}, 'sol': {'ceres'}}),
}


class TestChainPlace:
    # A step that MOVES takes its chain on, and a later step's name whose scope follows it is looked for there.
    def test_each_step_s_names_where_the_fleet_will_be(self, tree):
        line = 'fleet Prospector jump sol then move "Sol Belt" then dock ceres then mine'
        reading = tree.walk(line, names=farlandia.NAMES)
        assert [step.data() for step in reading.steps] == [
            {'fleet': 'f1', 'system': 'sol'},
            {'fleet': 'f1', 'to': 'sol-belt'},  # in sol, not where the Prospector is now
            {'fleet': 'f1', 'station': 'ceres'},  # in the belt's system
            {'fleet': 'f1'},
        ]

    def test_where_a_fleet_is_until_a_step_moves_it(self, tree):
        assert tree.read('fleet Prospector dock vesta', names=farlandia.NAMES).station == 'vesta'
        found = tree.walk('fleet Prospector mine then dock vesta', names=farlandia.NAMES)  # mine stays put
        assert found.steps[1].data()['station'] == 'vesta'
        refused = _refusal(tree, 'fleet Prospector jump sol then dock vesta', names=farlandia.NAMES)
        assert str(refused) == (
            "fleet {fleet} dock {station}: no station 'vesta' for fleet 'Prospector', once at 'sol' "
            '`fleet <fleet> dock [<station>]`'
        )
        assert (refused.word, refused.field) == ('vesta', 'station')

    def test_a_step_that_doesn_t_move_leaves_it_where_it_was(self, tree):
        reading = tree.walk('fleet Prospector jump sol then mine then dock ceres', names=farlandia.NAMES)
        assert reading.steps[2].data()['station'] == 'ceres'

    @pytest.mark.parametrize(
        'line',
        [
            'fleet Prospector jump nearest iron then dock ceres',  # MOVES = True
            'fleet Prospector dock nearest then move "Sol Belt"',  # its MOVES field left out
        ],
    )
    def test_moved_somewhere_the_line_doesn_t_say_any_name(self, tree, line):
        assert len(tree.walk(line, names=farlandia.NAMES).steps) == 2  # looked for across every name

    def test_a_scope_that_doesn_t_follow_keeps_its_field_s(self):
        reading = Tree([_ShipWarp, _ShipLoad]).walk('ship s1 warp --to sol then load iron at ceres', _SHIP_NAMES)
        assert reading.steps[1].data() == {'ship': 's1', 'good': 'iron', 'site': 'ceres'}

    def test_a_place_a_flag_says(self):
        refused = _refusal(
            Tree([_ShipWarp, _ShipLoad]), 'ship s1 warp --to sol then load iron at vesta', names=_SHIP_NAMES
        )
        assert str(refused).startswith(
            "ship {ship} load {good} at {site}: no site 'vesta' for ship 's1', once at 'sol'"
        )

    def test_a_placeholder_says_no_place(self, tree):
        reading = tree.walk('fleet <fleet> jump <system> then dock ceres', farlandia.NAMES, placeholders=True)
        assert reading.steps[1].data()['station'] == 'ceres'


class TestFlags:
    def test_anywhere_after_the_first_word(self, tree):
        expected = farlandia.FleetsMerge(fleet='f1', into='f2')
        assert tree.read('fleets merge --into f2 f1') == expected
        assert tree.read('fleets --into f2 merge f1') == expected

    def test_a_value_after_an_equals_quoted_or_not(self, tree):
        assert tree.read('fleet f1 mine --for=90s').for_ == timedelta(seconds=90)
        found = tree.read('handheld connect dock r7 --host=h --label="north dock"')
        assert found.label == 'north dock'

    def test_a_switch_and_a_negated_one(self, tree):
        assert tree.read('fleets merge f1 --into f2 --quiet').quiet is True
        stop = _one('mine', stop=parsed.Bool(default=True))
        assert stop.read('mine --no-stop').stop is False

    def test_names_are_lowercased(self, tree):
        assert tree.read('fleet f1 mine --FOR 90s').for_ == timedelta(seconds=90)

    def test_a_value_the_tree_would_take_for_a_literal(self, tree):
        assert tree.read('fleets merge f1 --into merge').into == 'merge'

    def test_a_value_that_starts_with_one_dash(self):
        move = _one('move', by=parsed.Int(default=0))
        assert move.read('move --by -3').by == -3

    def test_a_list_s_flag_given_again_adds_to_it(self):
        tag = _one('tag', tags=parsed.Str(many=True, default_factory=list))
        assert tag.read('tag --tags a --tags b').tags == ['a', 'b']

    def test_two_dashes_end_the_flags(self, tree):
        assert tree.read('say -- use --force -- now').message == 'use --force -- now'

    def test_a_quoted_flag_is_a_word(self, tree):
        assert tree.read('say "--loud" now').message == '--loud now'

    def test_parsed_s_own_on_any_command(self, tree):
        reading = tree.walk('fleet f1 buy ship hauler --yes --json')
        assert reading.own == {'yes', 'json'}
        assert reading.data() == {'fleet': 'f1', 'hull': 'hauler'}
        assert tree.walk('log --help --dry-run').own == {'help', 'dry-run'}


class TestReading:
    def test_each_field_s_words_and_what_took_them(self, tree):
        reading = tree.walk('fleets merge f1 --into f2 --quiet')
        assert list(reading.given) == ['fleet', 'into', 'quiet']
        fleet, into, quiet = reading.given.values()
        assert (fleet.by.slot, [w.text for w in fleet.words], fleet.value) == ('fleet', ['f1'], 'f1')
        assert into.by == Flag(name='into', field='into', arity=parsed.tree.Arity.VALUE)
        assert ([w.raw for w in into.words], into.value) == (['--into', 'f2'], 'f2')
        assert ([w.start for w in quiet.words], quiet.value) == ([26], True)

    def test_a_value_after_an_equals_starts_after_it(self, tree):
        given = tree.walk('fleet f1 mine --for=90s').given['for_']
        assert [(w.text, w.start) for w in given.words] == [('--for=90s', 14), ('90s', 20)]

    def test_data_is_by_wire_name(self, tree):
        assert tree.walk('fleet f1 mine --for 90s').data() == {'fleet': 'f1', 'for': 90.0}

    def test_where_the_walk_ended(self, tree):
        reading = tree.walk('fleet f1 dock nearest')
        assert reading.command is farlandia.FleetDock
        assert reading.end.bound.phrase.text == 'fleet {fleet} dock nearest'

    def test_the_line_it_was_read_from(self, tree):
        assert tree.walk('  log 40 ').line == '  log 40 '


class TestRefusals:
    @pytest.mark.parametrize(
        ('line', 'says'),
        [
            ('', r'no command: the line has no words'),
            ('--', r'no command: the line has no words'),
            ('frobnicate', r"no command 'frobnicate'"),
            ('fleet', r'fleet: which fleet\?'),
            ('fleet f1', r'fleet f1: then what\? mine \| dock \| jump \| move \| retreat \| run \| sell \| buy'),
            ('fleet f1 jump', r'fleet f1 jump: which system\?'),
            ('fleet f1 jump nearest', r'fleet f1 jump nearest: which ore\?'),
            ('fleet f1 progrms', r"no command 'fleet f1 progrms'"),
            ('log 40 50', r"log 40: '50' is left over"),
            ('fleet f1 dock nearest now', r"fleet f1 dock nearest: 'now' is left over"),
            ('--yes log', r'--yes comes before a command: a flag follows the first word'),
            ('say "hello', r'the quote at column 5 is never closed'),
            ('log --n 3', r'no command takes --n'),
            ('log --into f2', r'log takes no --into `log \[<n>\]`'),
            ('fleet f1 mine --into f2', r'fleet f1 mine takes no --into `fleet <fleet> mine \[--for <for>\]`'),
            ('fleets merge f1', r'fleets merge f1 needs --into `fleets merge f1 --into <into>`'),
            ('fleet f1 mine --for', r'--for needs a value'),
            ('fleet f1 mine --for --yes', r'--for needs a value'),
            ('fleet f1 mine --for -- 90', r'--for needs a value'),
            ('fleet f1 mine --for 1 --for 2', r'--for is given twice'),
            ('fleets merge f1 --into f2 --quiet=no', r'--quiet takes nothing after it'),
            ('fleets merge f1 --into f2 --quiet --quiet', r'--quiet is given twice'),
            ('log --yes=no', r'--yes takes nothing after it'),
            ('log --json --json', r'--json is given twice'),
        ],
    )
    def test_a_line_that_doesn_t_read_says_why(self, tree, line, says):
        with pytest.raises(ReadError, match=says):
            tree.walk(line)

    def test_several_words_need_one(self, tree):
        with pytest.raises(ReadError, match=r'fleet f1 sell: which goods\?'):
            tree.walk('fleet f1 sell')


def _refusal(tree: Tree, line: str, *, load: bool = False, names=None) -> ReadError:
    with pytest.raises(ReadError) as caught:
        tree.read(line, names=names) if load else tree.walk(line, names=names)
    return caught.value


class TestRefusalsAsData:
    # What each refusal says besides its message: where it stands, its hint and what may have been meant.
    @pytest.mark.parametrize(
        ('line', 'column', 'word'),
        [
            ('', 0, None),
            ('say "hello', 4, None),
            ('--yes log', 0, '--yes'),
            ('log --fro 3', 4, '--fro'),
            ('fleets merge f1 --into f2 --quiet=no', 26, '--quiet=no'),
            ('fleet f1 mien', 9, 'mien'),
            ('log 40 50', 7, '50'),
            ('fleet f1 jump', 13, None),
            ('fleet f1 mine --into f2', 14, '--into'),
            ('fleet f1 mine --for 1m --for 2m', 23, '--for'),
            ('fleets merge f1', 15, None),
        ],
    )
    def test_where_it_stands(self, tree, line, column, word):
        found = _refusal(tree, line)
        assert (found.line, found.column, found.word, found.kind) == (line, column, word, 'usage')

    @pytest.mark.parametrize(
        ('line', 'hint'),
        [
            ('say "hello', 'say "hello"'),
            ('fleet', 'fleet <fleet> …'),
            ('fleet f1 jump', 'fleet f1 jump <system>'),
            ('fleet f1 jump nearest', 'fleet f1 jump nearest <ore>'),
            ('log 40 50', 'log [<n>]'),
            ('log --into f2', 'log [<n>]'),
            ('fleet f1 mine --for', '--for <for>'),
            ('fleets merge f1 --quiet', 'fleets merge f1 --quiet --into <into>'),
            ('fleets merge', 'fleets merge <fleet> --into <into> [--quiet]'),  # one command past it: its usage
            ('ships make s1 add', 'ships make s1 add <part>'),
            ('fleet f1 sell', 'fleet f1 sell <goods> …'),
            (
                'handheld connect',
                'handheld connect <source> <reader_id> --host <host> [--port <port>] [--label <label>]',
            ),
        ],
    )
    def test_a_hint_says_how_to_say_it(self, tree, line, hint):
        found = _refusal(tree, line)
        assert found.hint == hint
        assert str(found).endswith(f' `{hint}`')

    def test_a_slot_after_an_optional_one_left_out(self):
        found = _one(
            'pick {x} then {y}', x=parsed.Str(default=None), y=parsed.Str(required=True), n=parsed.Int(default=1)
        )
        with pytest.raises(ReadError) as caught:
            found.walk('pick then')
        assert caught.value.hint == 'pick then <y> [--n <n>]'

    @pytest.mark.parametrize(
        ('line', 'suggestions'),
        [
            ('flet f1 mine', ('fleet', 'fleets')),
            ('fleet f1 mien', ('mine',)),
            ('fleet f1 xyz', ('mine', 'dock', 'jump', 'move', 'retreat', 'run', 'sell', 'buy')),
            ('fleet f1', ('mine', 'dock', 'jump', 'move', 'retreat', 'run', 'sell', 'buy')),
            ('log --fro 3', ('--for',)),
            ('log --jsno', ('--json',)),
        ],
    )
    def test_what_may_have_been_meant(self, tree, line, suggestions):
        assert _refusal(tree, line).suggestions == suggestions

    def test_did_you_mean_is_in_the_text_and_a_list_isn_t_doubled(self, tree):
        assert str(_refusal(tree, 'log --fro 3')) == 'no command takes --fro; did you mean --for?'
        assert (
            str(_refusal(tree, 'fleet f1 xyz'))
            == "no command 'fleet f1 xyz': mine | dock | jump | move | retreat | run | sell | buy"
        )

    def test_the_field_where_the_walk_knows_it(self, tree):
        assert _refusal(tree, 'log many').field == 'n'
        assert _refusal(tree, 'fleet f1 mine --for soon').field == 'for_'
        assert _refusal(tree, 'fleets merge f1').field == 'into'
        assert _refusal(tree, 'fleet').field is None

    def test_as_data(self, tree):
        assert _refusal(tree, 'fleet f1 jump').to_json() == {
            'error': 'usage',
            'message': 'fleet f1 jump: which system? `fleet f1 jump <system>`',
            'line': 'fleet f1 jump',
            'column': 13,
            'hint': 'fleet f1 jump <system>',
        }


class TestSearedsRefusals:
    # A value seared refuses comes back as the word that gave it.
    def test_a_slot_s_value(self, tree):
        found = _refusal(tree, 'log 0', load=True)
        assert str(found) == 'log {n}: must be >= 1, got 0'
        assert (found.kind, found.column, found.word, found.field) == ('validation', 4, '0', 'n')
        assert isinstance(found.__cause__, parsed.ValidationError)

    def test_a_flag_s_value(self, tree):
        found = _refusal(tree, 'handheld connect dock r7 --host h --port 70000', load=True)
        assert str(found) == '--port: must be <= 65535, got 70000'
        assert (found.column, found.word, found.field) == (41, '70000', 'port')

    def test_one_of_a_list_s_words(self):
        tag = _one('tag {ns}', ns=parsed.Int(many=True, required=True, ge=1))
        found = _refusal(tag, 'tag 3 2 0 4', load=True)
        assert (found.column, found.word) == (8, '0')

    def test_one_of_a_list_s_flags(self):
        tag = _one('tag', ns=parsed.Int(many=True, default_factory=list, ge=1))
        found = _refusal(tag, 'tag --ns 2 --ns 0', load=True)
        assert (found.column, found.word) == (16, '0')

    def test_the_rest_of_the_line_from_its_first_word(self):
        note = _one('note {text**}', text=parsed.Str(required=True, max_length=5))
        found = _refusal(note, 'note far too long', load=True)
        assert (found.column, found.word, found.field) == (5, 'far too long', 'text')
        assert found.message.startswith('note {text**}: ')

    def test_a_pattern(self):
        code = _one('code {c}', c=parsed.Str(required=True, pattern='[a-z]+'))
        found = _refusal(code, 'code AB1', load=True)
        assert (found.kind, found.word) == ('validation', 'AB1')


class TestFarlandiasCases:
    """farlandia's own reading cases (``tests/client/test_tree.py``), on this fixture's commands.

    Lifted: words, slots and flags anywhere after the first word; a slot of several words; a span of time and true or
    false; the refusals that are the walk's, with did-you-mean and a usage for a hint. Changed on purpose: ``--quiet
    yes`` reads ``yes`` as a word, since the tree knows ``--quiet`` is a switch; a flag the command doesn't take says
    so with the command's usage (``takes no --into `fleet <fleet> mine [--for <for>]```), and a required flag left out
    with the line it's missing from. Later: a share's ``off`` or percent (a kind of its own), names alone (names),
    chains and subjects, ``--help``, completion, schemas and ``render``.
    """

    def test_words_slots_and_flags_anywhere_after_the_first_word(self, tree):
        assert tree.read('fleets start true') == farlandia.FleetsStart(on=True)
        assert tree.read('fleets merge --into f2 f1') == farlandia.FleetsMerge(fleet='f1', into='f2')
        assert tree.read('fleets merge f1 --into f2 --quiet') == farlandia.FleetsMerge(
            fleet='f1', into='f2', quiet=True
        )
        assert tree.read('fleet f1 sell s1 s2 s3').goods == ['s1', 's2', 's3']

    @pytest.mark.parametrize(
        ('line', 'says'),
        [
            ('', 'no command'),
            ('fleet', 'which fleet'),
            ('fleet f1 progrms', "no command 'fleet f1 progrms'"),
            ('fleet f1 jump', 'which system'),
            ('fleet f1 mine --into f2', 'takes no --into `fleet <fleet> mine \\[--for <for>\\]`'),
            ('fleets merge f1', '--into'),
            ('fleet f1 mine --for 1h --for 2h', 'given twice'),
            ('fleet f1 mine --for', 'needs a value'),
            ('fleet f1 mine --for soon', 'not a span of time'),
            ('fleet f1', 'then what'),
            ('fleets start maybe', 'true or false'),
            ('fleet f1 dock nearest now', 'left over'),
        ],
    )
    def test_mistakes_say_how_to_say_it(self, tree, line, says):
        with pytest.raises(ReadError, match=says):
            tree.walk(line)

    def test_did_you_mean(self, tree):
        with pytest.raises(ReadError, match=r"no command 'fleet f1 mien'; did you mean mine\?"):
            tree.walk('fleet f1 mien')

    def test_a_switch_takes_no_word_so_the_word_is_left_over(self, tree):
        with pytest.raises(ReadError, match=r"fleets merge f1: 'yes' is left over"):
            tree.walk('fleets merge f1 --into f2 --quiet yes')
