"""Tests for ``parsed/tree.py``: the phrases compiled into one trie, the checks across commands, and reading."""

from __future__ import annotations

import math
from datetime import timedelta

import _support_farlandia as farlandia
import _support_rio as rio
import pytest

import parsed
from bench.tree import COMMANDS, tree
from parsed.command import Command
from parsed.errors import DeclarationError, ReadError
from parsed.tree import RESERVED, Arity, Flag, SlotKind, Tree, _declared, flag_name


def _command(phrase: str, **fields: object) -> type[Command]:
    """A decorated command with ``phrase`` and ``fields``, each annotated as an ``object``."""
    namespace: dict[str, object] = {'PHRASE': phrase, '__annotations__': dict.fromkeys(fields, object)}
    namespace.update(fields)
    return parsed.parsed(type('Cmd', (Command,), namespace))


@pytest.fixture(scope='module')
def fixtures() -> Tree:
    return Tree.collect('_support_farlandia', '_support_rio')


class TestCompiling:
    def test_every_command_of_the_targets_and_nothing_else(self, fixtures):
        names = {d.cls.__name__ for d in fixtures.commands}
        assert names == {
            'FleetMine',
            'FleetDock',
            'FleetJump',
            'FleetJumpNearest',
            'FleetRetreat',
            'FleetRun',
            'FleetSell',
            'FleetBuyShip',
            'FleetsMerge',
            'FleetsShow',
            'FleetsStart',
            'Log',
            'Say',
            'ShipsMakeAdd',
            'ShipFit',
            'HandheldConnect',
        }  # no base (FleetCommand), no reply (FleetView), no request (HandheldEndpoint)

    def test_first_words_at_the_root(self, fixtures):
        assert sorted(fixtures.root.words) == [
            'detachment',
            'fleet',
            'fleets',
            'handheld',
            'log',
            'say',
            'ship',
            'ships',
        ]
        assert fixtures.root.slot is None

    def test_a_slot_shared_by_the_commands_after_it(self, fixtures):
        fleet = fixtures.root.words['fleet'].slot
        assert fleet.kind is SlotKind.ONE
        assert sorted(fleet.node.words) == ['buy', 'dock', 'jump', 'mine', 'retreat', 'run', 'sell']

    def test_a_literal_beside_a_slot(self, fixtures):
        dock = fixtures.root.words['fleet'].slot.node.words['dock']
        assert dock.slot.kind is SlotKind.ONE  # {station}
        assert list(dock.words) == ['nearest']
        assert dock.words['nearest'].end.bound.phrase.text == 'fleet {fleet} dock nearest'

    def test_an_optional_slot_both_ways(self, fixtures):
        log = fixtures.root.words['log']
        assert log.end.places == ()  # `log`, n left at its default
        assert [p.slot for p in log.slot.node.end.places] == ['n']  # `log 40`

    def test_several_words_and_the_rest_of_the_line(self, fixtures):
        sell = fixtures.root.words['fleet'].slot.node.words['sell']
        assert sell.slot.kind is SlotKind.MANY
        assert fixtures.root.words['say'].slot.kind is SlotKind.REST

    def test_a_twin_compiled_at_its_own_words(self, fixtures):
        mine = fixtures.root.words['detachment'].slot.node.words['mine'].end
        assert mine.declaration.cls is farlandia.FleetMine
        assert [(p.slot, p.field) for p in mine.places] == [('detachment', 'fleet')]

    def test_collected_in_the_order_declared(self, fixtures):
        assert [found.cls.__name__ for found in fixtures.commands] == [
            'FleetMine',
            'FleetDock',
            'FleetJump',
            'FleetJumpNearest',
            'FleetRetreat',
            'FleetRun',
            'FleetSell',
            'Log',
            'Say',
            'FleetBuyShip',
            'FleetsMerge',
            'FleetsStart',
            'FleetsShow',
            'ShipsMakeAdd',
            'ShipFit',
            'HandheldConnect',  # the second target's, after the first's
        ]

    def test_so_a_node_s_words_come_as_declared(self, fixtures):
        after = fixtures.root.words['fleet'].slot.node
        assert list(after.words) == ['mine', 'dock', 'jump', 'retreat', 'run', 'sell', 'buy']

    def test_classes_given_keep_the_order_given(self):
        assert [found.cls for found in Tree([farlandia.Log, farlandia.FleetMine]).commands] == [
            farlandia.Log,
            farlandia.FleetMine,
        ]

    def test_a_class_made_by_type_comes_after_those_written(self):
        made = _command('made')
        assert _declared(farlandia.FleetMine) == (
            '_support_farlandia',
            farlandia.FleetMine.__firstlineno__,
            'FleetMine',
        )
        assert _declared(made)[1] == math.inf  # not its base's line

    def test_a_class_given_twice_counts_once(self):
        assert len(Tree([farlandia.Log, farlandia.Log]).commands) == 1

    def test_a_base_is_left_out(self):
        assert Tree([farlandia.FleetCommand, farlandia.FleetMine]).commands[0].cls is farlandia.FleetMine

    def test_a_command_that_doesn_t_declare_is_refused(self):
        with pytest.raises(DeclarationError, match=r'names no field'):
            Tree([_command('go {where}')])

    def test_a_tree_the_size_of_a_real_one(self):
        assert len(Tree(tree()).commands) == COMMANDS


class TestAmbiguity:
    def test_two_phrases_that_read_the_same_lines(self):
        one = _command('go {where}', where=parsed.Str(required=True))
        two = _command('go {there}', there=parsed.Str(required=True))
        with pytest.raises(
            DeclarationError, match=r"'go \{where\}' \(.*Cmd\) and 'go \{there\}' \(.*Cmd\) read the same lines"
        ):
            Tree([one, two])

    def test_an_optional_slot_left_out_counts(self):
        log = _command('log {n}', n=parsed.Int(default=20))
        bare = _command('log')
        with pytest.raises(
            DeclarationError, match=r"'log \{n\}' \(.*left without \{n\}\) and 'log' \(.*\) read the same lines"
        ):
            Tree([log, bare])

    def test_one_command_s_other_wording_alike_its_phrase(self):
        @parsed.parsed
        class Move(Command):
            PHRASE = 'move {fleet}'
            EXTRA_PHRASES = ('move {fleet}',)

            fleet: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r'read the same lines'):
            Tree([Move])

    @pytest.mark.parametrize(
        ('other', 'said'),
        [
            (parsed.Str(required=True), 'one word'),
            (parsed.Str(many=True, required=True), 'several words'),
        ],
    )
    def test_two_kinds_of_slot_at_one_node(self, other, said):
        say = _command('say {message**}', message=parsed.Str(required=True))
        shout = _command('say {target} now', target=other)
        message = (
            r"after 'say', 'say \{message\*\*\}' \(.*\) takes the rest of the line and "
            rf"'say \{{target\}} now' \(.*\) takes {said}"
        )
        with pytest.raises(DeclarationError, match=message):
            Tree([say, shout])

    def test_a_literal_beats_a_slot_so_both_build(self):
        system = _command('jump {system}', system=parsed.Str(required=True))
        nearest = _command('jump nearest {ore}', ore=parsed.Str(required=True))
        found = Tree([system, nearest]).root.words['jump']
        assert found.slot.kind is SlotKind.ONE
        assert list(found.words) == ['nearest']


class TestFlags:
    def test_a_flag_is_its_wire_name(self, fixtures):
        assert fixtures.flags_of(farlandia.FleetMine) == {
            'for': Flag(name='for', field='for_', arity=Arity.VALUE),
        }
        assert set(fixtures.flags_of(rio.HandheldConnect)) == {'host', 'port', 'label'}

    def test_underscores_written_as_dashes(self):
        found = Tree([_command('cap', max_bytes=parsed.Int(default=0))])
        assert list(found.flags_of(found.commands[0].cls)) == ['max-bytes']

    def test_a_bool_is_a_switch_negated_when_it_defaults_true(self):
        found = Tree([_command('mine', loud=parsed.Bool(default=False), stop=parsed.Bool(default=True))])
        flags = found.flags_of(found.commands[0].cls)
        assert flags['loud'] == Flag(name='loud', field='loud', arity=Arity.SWITCH)
        assert flags['no-stop'] == Flag(name='no-stop', field='stop', arity=Arity.SWITCH, negated=True)

    def test_a_tree_wide_table(self, fixtures):
        assert fixtures.flags == {
            'for': Arity.VALUE,
            'into': Arity.VALUE,
            'quiet': Arity.SWITCH,
            'host': Arity.VALUE,
            'port': Arity.VALUE,
            'label': Arity.VALUE,
        }

    @pytest.mark.parametrize('attr', ['help', 'json', 'yes', 'dry_run'])
    def test_parsed_s_own_are_reserved(self, attr):
        with pytest.raises(DeclarationError, match=rf'--{flag_name(attr)} is a flag parsed takes for every command'):
            Tree([_command('mine', **{attr: parsed.Bool(default=False)})])
        assert flag_name(attr) in RESERVED

    def test_two_with_one_name_in_a_command(self):
        cmd = _command('mine', n=parsed.Int(default=1), count=parsed.Int(default=1, data_key='n'))
        with pytest.raises(DeclarationError, match=r'n and count are both --n'):
            Tree([cmd])

    def test_a_name_that_isn_t_lowercase_words(self):
        with pytest.raises(DeclarationError, match=r'its flag would be --Count; a flag is lowercase words'):
            Tree([_command('mine', Count=parsed.Int(default=1))])

    def test_one_name_one_arity_across_the_tree(self):
        switch = _command('mine', all=parsed.Bool(default=False))
        value = _command('sell', all=parsed.Str(default=''))
        with pytest.raises(DeclarationError, match=r'--all is a switch in .*Cmd but takes a value in .*Cmd'):
            Tree([switch, value])

    def test_one_name_one_arity_is_fine(self):
        found = Tree([_command('mine', n=parsed.Int(default=1)), _command('sell', n=parsed.Int(default=2))])
        assert found.flags == {'n': Arity.VALUE}

    def test_not_one_of_the_tree_s_commands(self, fixtures):
        with pytest.raises(KeyError):
            fixtures.flags_of(farlandia.FleetCommand)


class TestReading:
    # The walk itself is tested in `tests/_walk/`; these pin the tree's two doors to it.
    def test_walk_says_what_a_line_says(self, fixtures):
        reading = fixtures.walk('fleet f1 mine --for 90s --yes')
        assert reading.command is farlandia.FleetMine
        assert reading.data() == {'fleet': 'f1', 'for': 90.0}
        assert reading.own == {'yes'}

    def test_walk_reads_placeholders_when_asked(self, fixtures):
        assert fixtures.walk('fleet <fleet> mine', placeholders=True).data() == {'fleet': '<fleet>'}

    def test_read_goes_on_to_the_instance(self, fixtures):
        assert fixtures.read('fleet f1 mine --for 90s') == farlandia.FleetMine(fleet='f1', for_=timedelta(seconds=90))

    def test_names_by_their_resolvers(self, fixtures):
        assert fixtures.walk('fleet Prospector mine', names=farlandia.NAMES).given['fleet'].value == 'f1'
        assert fixtures.read('fleet Prospector mine', names=farlandia.NAMES).fleet == 'f1'

    def test_complete_says_what_may_come_next(self, fixtures):
        assert fixtures.complete('fleet f1 mine --f') == (['--for'], 3)
        assert fixtures.complete('fleet ', names=farlandia.NAMES).words == ['Prospector', 'Hauler']

    def test_a_line_that_doesn_t_read(self, fixtures):
        with pytest.raises(ReadError, match=r'no command'):
            fixtures.read('frobnicate')

    def test_exported(self):
        assert parsed.Tree is Tree


@pytest.fixture(scope='module')
def farm() -> Tree:
    return Tree.collect('_support_farlandia', under='farm')


class TestUnder:
    # A tree under a prefix reads, completes and writes whole lines, and says the prefix in its refusals.
    def test_its_lines_begin_with_the_prefix(self, farm):
        assert farm.under == 'farm'
        assert farm.read('farm fleet f1 mine --for 90s') == farlandia.FleetMine(fleet='f1', for_=timedelta(seconds=90))
        assert farm.root.words.keys() == {'farm'}
        assert farm.top is farm.root.words['farm']

    def test_a_line_without_it_doesn_t_read(self, farm):
        with pytest.raises(ReadError, match=r"no command 'fleet': farm"):
            farm.read('fleet f1 mine')

    @pytest.mark.parametrize(
        ('line', 'says'),
        [
            ('farm', 'farm: then what? fleet | detachment | log'),
            ('farm flet f1 mine', "no command 'farm flet'; did you mean fleet or fleets?"),
            ('farm fleet f1 jump', 'farm fleet f1 jump: which system? `farm fleet f1 jump <system>`'),
            ('farm log 3 4', "farm log 3: '4' is left over `farm log [<n>]`"),
        ],
    )
    def test_its_refusals_and_hints_say_it(self, farm, line, says):
        with pytest.raises(ReadError) as caught:
            farm.read(line)
        assert str(caught.value).startswith(says)

    def test_completion_offers_it(self, farm):
        assert farm.complete('') == (['farm'], 0)
        assert farm.complete('farm fl').words == ['fleet', 'fleets']

    def test_a_line_written_back_begins_with_it(self, farm):
        assert farm.render(farlandia.FleetDock(fleet='f1', station='nearest')) == 'farm fleet f1 dock "nearest"'

    def test_several_words_spaced_once(self):
        found = Tree([farlandia.Log], under='  rio   relay ')
        assert found.under == 'rio relay'
        assert found.read('rio relay log 4') == farlandia.Log(n=4)

    def test_none_by_default(self, fixtures):
        assert fixtures.under == ''
        assert fixtures.top is fixtures.root

    @pytest.mark.parametrize(
        ('under', 'message'),
        [
            ('Farm', r"under='Farm': 'Farm' is not a word: a word is lowercase letters"),
            ('farm {fleet}', r"under='farm \{fleet\}': a prefix is words only; a slot belongs to a phrase"),
            (3, r'under=3: a prefix is a string of words'),
        ],
    )
    def test_refused_unless_it_s_words(self, under, message):
        with pytest.raises(DeclarationError, match=message):
            Tree([farlandia.Log], under=under)
