"""Tests for ``parsed/_walk/_render.py``: an instance back to the line that says it."""

from __future__ import annotations

from datetime import timedelta
from typing import ClassVar

import _support_farlandia as farlandia
import _support_protocol as protocol
import pytest

import parsed
from bench.tree import lines, tree
from parsed.command import Command
from parsed.errors import RenderError
from parsed.tree import Tree


@pytest.fixture(scope='module')
def fixtures() -> Tree:
    return Tree.collect('_support_farlandia', '_support_protocol')


def _command(phrase: str, **fields: object) -> type[Command]:
    namespace: dict[str, object] = {'PHRASE': phrase, '__annotations__': dict.fromkeys(fields, object)}
    namespace.update(fields)
    return parsed.parsed(type('Cmd', (Command,), namespace))


class TestLines:
    @pytest.mark.parametrize(
        ('command', 'line'),
        [
            (farlandia.FleetMine(fleet='f1'), 'fleet f1 mine'),
            (farlandia.FleetMine(fleet='f1', for_=timedelta(seconds=5400)), 'fleet f1 mine --for 1h30m'),
            (farlandia.FleetDock(fleet='f1'), 'fleet f1 dock'),
            (farlandia.FleetDock(fleet='f1', station='vesta'), 'fleet f1 dock vesta'),
            (farlandia.FleetJump(fleet='f1', system='sol'), 'fleet f1 jump sol'),
            (farlandia.FleetJumpNearest(fleet='f1', ore='iron'), 'fleet f1 jump nearest iron'),
            (farlandia.FleetSell(fleet='f1', goods=['iron', 'coal']), 'fleet f1 sell iron coal'),
            (farlandia.FleetRetreat(fleet='f1', share=30.0), 'fleet f1 retreat 30'),
            (farlandia.FleetRetreat(fleet='f1', share=None), 'fleet f1 retreat off'),
            (
                farlandia.FleetRun(fleet='f1', routine='mining', variables={'ore': 'iron'}),
                'fleet f1 run mining ore iron',
            ),
            (farlandia.FleetRun(fleet='f1', routine='mining'), 'fleet f1 run mining'),
            (farlandia.Log(), 'log'),
            (farlandia.Log(n=40), 'log 40'),
            (farlandia.Say(message='hello there'), 'say hello there'),
            (farlandia.FleetBuyShip(fleet='f1', hull='hauler'), 'fleet f1 buy ship hauler'),
            (farlandia.FleetsMerge(fleet='f1', into='f2'), 'fleets merge f1 --into f2'),
            (farlandia.FleetsMerge(fleet='f1', into='f2', quiet=True), 'fleets merge f1 --into f2 --quiet'),
            (farlandia.FleetsStart(on=False), 'fleets start false'),
            (farlandia.FleetsShow(fleet='f1'), 'fleets show f1'),
            (farlandia.ShipsMakeAdd(ship='s1', part='drill'), 'ships make s1 add drill'),
            (farlandia.ShipFit(ship='s1'), 'ship s1 fit'),
            (protocol.HandheldConnect(source='dock', reader_id='r7', host='h'), 'handheld connect dock r7 --host h'),
            (
                protocol.HandheldConnect(source='dock', reader_id='r7', host='h', port=5085, label='north dock'),
                'handheld connect dock r7 --host h --port 5085 --label "north dock"',
            ),
        ],
    )
    def test_an_instance_s_line(self, fixtures, command, line):
        assert fixtures.render(command) == line
        assert fixtures.read(line) == command


class TestQuoting:
    @pytest.mark.parametrize(
        ('command', 'line'),
        [
            (farlandia.FleetDock(fleet='f1', station='nearest'), 'fleet f1 dock "nearest"'),  # a literal there
            (farlandia.FleetJump(fleet='f1', system='Nearest'), 'fleet f1 jump "Nearest"'),  # case aside
            (farlandia.FleetDock(fleet="Vruba'a Belt 1"), 'fleet "Vruba\'a Belt 1" dock'),  # a space
            (farlandia.FleetsShow(fleet=''), 'fleets show ""'),  # nothing at all
            (farlandia.Say(message='--loud now'), 'say "--loud" now'),  # a flag's spelling
            (farlandia.Say(message='hello  there'), 'say "hello  there"'),  # its own spacing
            (farlandia.FleetsMerge(fleet='f1', into='--x'), 'fleets merge f1 --into "--x"'),
        ],
    )
    def test_where_the_line_would_read_it_otherwise(self, fixtures, command, line):
        assert fixtures.render(command) == line
        assert fixtures.read(line) == command

    def test_a_word_up_to_a_literal_after_it(self):
        sell = Tree([_command('sell {goods} now', goods=parsed.Str(many=True, required=True))])
        cls = sell.commands[0].cls
        assert sell.render(cls(goods=['iron', 'now'])) == 'sell iron "now" now'

    def test_a_double_quote_can_t_be_said(self, fixtures):
        with pytest.raises(RenderError, match=r"can't be said on a line: a word can't hold a double quote"):
            fixtures.render(farlandia.Say(message='say "hi"'))


class TestPhrases:
    def test_the_first_that_can_say_it(self, fixtures):
        assert fixtures.render(farlandia.FleetDock(fleet='f1')) == 'fleet f1 dock'  # PHRASE, its station left out

    def test_with_names_the_twin_its_value_belongs_to(self, fixtures):
        assert fixtures.render(farlandia.FleetMine(fleet='d2'), names=farlandia.NAMES) == 'detachment d2 mine'
        assert fixtures.render(farlandia.FleetMine(fleet='f1'), names=farlandia.NAMES) == 'fleet f1 mine'
        assert fixtures.render(farlandia.FleetMine(fleet='d2')) == 'fleet d2 mine'  # loose: PHRASE

    def test_a_scoped_name_by_its_scope(self, fixtures):
        command = farlandia.FleetDock(fleet='f2', station='ceres')
        assert fixtures.render(command, names=farlandia.NAMES) == 'fleet f2 dock ceres'

    def test_none_that_can_say_it(self, fixtures):
        with pytest.raises(RenderError, match=r'no phrase of FleetMine says .*, with the names given'):
            fixtures.render(farlandia.FleetMine(fleet='nobody'), names=farlandia.NAMES)

    def test_a_resolver_that_says_why_as_one_that_names_nothing(self, fixtures):
        fleets = farlandia.Saying(farlandia.NAMES['fleet'], 'no fleet {word!r}: fleets list names them')
        names = {**farlandia.NAMES, 'fleet': fleets}
        assert fixtures.render(farlandia.FleetMine(fleet='f1'), names=names) == 'fleet f1 mine'
        with pytest.raises(RenderError, match=r'no phrase of FleetMine says .*, with the names given'):
            fixtures.render(farlandia.FleetMine(fleet='nobody'), names=names)

    def test_not_one_of_the_tree_s(self, fixtures):
        with pytest.raises(RenderError, match=r"FleetView is not one of the tree's commands"):
            fixtures.render(farlandia.FleetView(fleet='f1'))  # ty: ignore[invalid-argument-type]


class TestFlags:
    def test_a_negated_switch(self):
        stop = Tree([_command('mine', stop=parsed.Bool(default=True))])
        cls = stop.commands[0].cls
        assert stop.render(cls(stop=False)) == 'mine --no-stop'
        assert stop.render(cls()) == 'mine'

    def test_a_list_s_flag_once_for_each(self):
        tag = Tree([_command('tag', tags=parsed.Str(many=True, default_factory=list))])
        cls = tag.commands[0].cls
        assert tag.render(cls(tags=['a', 'b'])) == 'tag --tags a --tags b'


class TestRoundTrips:
    # A line read and rendered reads the same.
    @pytest.mark.parametrize(
        'line',
        [
            'fleet prospector mine --for 90s',
            'detachment d2 mine',
            'fleet f1 dock nearest',
            'fleet f1 run mining ore iron home "Vruba\'a Belt 1"',
            'say -- use --force',
            'fleets --into f2 merge f1',
            'FLEET F1 MINE --FOR 1H',
        ],
    )
    def test_a_line_read_and_rendered(self, fixtures, line):
        command = fixtures.read(line)
        assert fixtures.read(fixtures.render(command)) == command

    def test_a_tree_the_size_of_a_real_one(self):
        commands = tree()
        built = Tree(commands)
        for line in lines(commands):
            command = built.read(line)
            assert built.read(built.render(command)) == command


class TestChains:
    # A chain's steps on one line, joined by `then`: each after the first in its own words, read back to the steps.
    def test_its_steps_on_one_line(self, fixtures):
        steps = [
            farlandia.FleetJump(fleet='f1', system='sol'),
            farlandia.FleetMove(fleet='f1', to='sol-belt'),
            farlandia.FleetMine(fleet='f1', for_=timedelta(minutes=90)),
            farlandia.FleetSell(fleet='f1', goods=['iron', 'coal']),
        ]
        line = fixtures.render(steps)
        assert line == 'fleet f1 jump sol then move sol-belt then mine --for 1h30m then sell iron coal'
        assert [step.load() for step in fixtures.walk(line).steps] == steps

    def test_one_step_is_its_own_line(self, fixtures):
        assert fixtures.render([farlandia.FleetMine(fleet='f1')]) == 'fleet f1 mine'

    def test_a_twin_s_steps_under_its_own_words(self, fixtures):
        steps = [farlandia.FleetMine(fleet='d2'), farlandia.FleetMine(fleet='d2')]
        assert fixtures.render(steps, farlandia.NAMES) == 'detachment d2 mine then mine'

    def test_each_step_s_names_where_the_fleet_will_be(self, fixtures):
        steps = [farlandia.FleetJump(fleet='f1', system='sol'), farlandia.FleetDock(fleet='f1', station='ceres')]
        line = fixtures.render(steps, farlandia.NAMES)  # ceres isn't where the Prospector is, but where it will be
        assert [step.load() for step in fixtures.walk(line, farlandia.NAMES).steps] == steps
        with pytest.raises(RenderError, match=r'no phrase of FleetDock says'):
            fixtures.render([farlandia.FleetDock(fleet='f1', station='ceres')], farlandia.NAMES)

    def test_then_in_a_step_quoted(self, fixtures):
        assert fixtures.render(farlandia.FleetMove(fleet='f1', to='then')) == 'fleet f1 move "then"'
        line = fixtures.render([farlandia.FleetMine(fleet='f1'), farlandia.FleetSell(fleet='f1', goods=['Then'])])
        assert line == 'fleet f1 mine then sell "Then"'
        assert fixtures.render(farlandia.Say(message='hello then goodbye')) == 'say hello then goodbye'  # no step

    @pytest.mark.parametrize(
        ('steps', 'message'),
        [
            ([], r'a chain has a step at least'),
            ([farlandia.Log(), farlandia.Log()], r"Log\(n=20\) is no step: a chain's steps are the commands beneath"),
            (
                [farlandia.FleetMine(fleet='f1'), farlandia.FleetRetreat(fleet='f1', share=30.0)],
                r"step 2 of the chain, FleetRetreat\(.*\), is not a step of FleetCommand's chain",
            ),
            (
                [farlandia.FleetMine(fleet='f1'), farlandia.FleetMine(fleet='f2')],
                r"a chain's steps share FleetCommand's fields: fleet is 'f1' in its first step and 'f2' in step 2",
            ),
        ],
    )
    def test_refused(self, fixtures, steps, message):
        with pytest.raises(RenderError, match=message):
            fixtures.render(steps)

    def test_a_step_with_no_phrase_under_the_first_s_words(self, fixtures):
        steps = [farlandia.FleetMine(fleet='d2'), farlandia.FleetDock(fleet='d2')]
        with pytest.raises(RenderError, match=r"FleetDock has no phrase under 'detachment \{detachment\}', the chain"):
            fixtures.render(steps, farlandia.NAMES)


@parsed.parsed
class Retreat(Command):
    """A share, or off."""

    PHRASE = 'retreat {share}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'share': parsed.kinds.Number(suffix='%', words={'off': None})}

    share: float | None = parsed.Float(required=True, nullable=True)


def test_a_literal_word_for_its_value():
    retreat = Tree([Retreat])
    assert retreat.render(Retreat(share=None)) == 'retreat off'
    assert retreat.render(Retreat(share=12.5)) == 'retreat 12.5'
