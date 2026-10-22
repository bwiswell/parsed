"""Tests for ``parsed/doc/keys.py``: a command's key for policy, slashed as a topic is."""

from __future__ import annotations

from datetime import timedelta

import _support_farlandia as farlandia
import _support_rio as rio
import pytest

from parsed.doc import command_key, introspect_command
from parsed.errors import RenderError


class TestCommandKey:
    @pytest.mark.parametrize(
        ('command', 'key'),
        [
            (farlandia.FleetMine(fleet='f1'), 'fleet/f1/mine'),
            (farlandia.FleetDock(fleet='f1'), 'fleet/f1/dock'),  # an optional slot at its default
            (farlandia.FleetDock(fleet='f1', station='vesta'), 'fleet/f1/dock/vesta'),
            (farlandia.FleetJumpNearest(fleet='f1', ore='iron'), 'fleet/f1/jump/nearest/iron'),
            (farlandia.FleetBuyShip(fleet='f1', hull='hauler'), 'fleet/f1/buy/ship/hauler'),
            (farlandia.Log(n=40), 'log/40'),
            (farlandia.FleetsStart(on=False), 'fleets/start/false'),
            (rio.HandheldConnect(source='dock', reader_id='r7', host='h'), 'handheld/connect/dock/r7'),
        ],
    )
    def test_its_words_and_its_slots_values(self, command, key):
        assert command_key(command) == key

    @pytest.mark.parametrize(
        ('command', 'key'),
        [
            (farlandia.FleetSell(fleet='f1', goods=['iron', 'coal']), 'fleet/f1/sell'),  # several words
            (farlandia.Say(message='hello there'), 'say'),  # the rest of the line
            (farlandia.FleetRun(fleet='f1', routine='mining', variables={'ore': 'iron'}), 'fleet/f1/run/mining'),
            (farlandia.FleetMine(fleet='f1', for_=timedelta(hours=1)), 'fleet/f1/mine'),  # a flag
            (farlandia.FleetsMerge(fleet='f1', into='f2', quiet=True), 'fleets/merge/f1'),
        ],
    )
    def test_its_body_left_out(self, command, key):
        assert command_key(command) == key

    def test_with_names_by_the_twin_its_value_belongs_to(self):
        assert command_key(farlandia.FleetMine(fleet='d2'), names=farlandia.NAMES) == 'detachment/d2/mine'
        assert command_key(farlandia.FleetMine(fleet='d2')) == 'fleet/d2/mine'  # loose: PHRASE

    def test_a_value_as_it_stands_its_safety_the_reader_s(self):
        assert command_key(farlandia.FleetsShow(fleet='a/b')) == 'fleets/show/a/b'

    def test_none_that_can_say_it(self):
        with pytest.raises(RenderError, match=r'no phrase of FleetMine says'):
            command_key(farlandia.FleetMine(fleet='nobody'), names=farlandia.NAMES)

    def test_not_a_command_s_instance(self):
        with pytest.raises(TypeError, match=r'command_key\(\) takes an instance of a command'):
            command_key(farlandia.FleetView(fleet='f1'))  # ty: ignore[invalid-argument-type]


class TestTemplates:
    def test_each_phrase_s(self):
        assert introspect_command(farlandia.FleetDock).keys == (
            'fleet/{fleet}/dock/{station}',
            'fleet/{fleet}/dock/nearest',
        )
        assert introspect_command(farlandia.FleetMine).keys == ('fleet/{fleet}/mine', 'detachment/{detachment}/mine')

    def test_the_body_left_out(self):
        assert introspect_command(farlandia.FleetSell).keys == ('fleet/{fleet}/sell',)
        assert introspect_command(farlandia.Say).keys == ('say',)
