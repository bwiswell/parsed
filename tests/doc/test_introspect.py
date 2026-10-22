"""Tests for ``parsed/doc/introspect.py``: a command as data, beside seared's ``SchemaDoc``."""

from __future__ import annotations

import _support_farlandia as farlandia
import _support_rio as rio
import pytest
from seared.doc import SchemaDoc

import parsed
from bench.tree import tree
from parsed.command import Command
from parsed.doc import CommandDoc, FlagDoc, SlotDoc, introspect_command, is_command_class
from parsed.kinds import Duration, Pairs, Switch


class TestIsCommandClass:
    @pytest.mark.parametrize('cls', [farlandia.FleetMine, farlandia.Log, rio.HandheldConnect])
    def test_a_command(self, cls):
        assert is_command_class(cls)

    @pytest.mark.parametrize(
        'obj',
        [
            Command,
            farlandia.FleetCommand,
            farlandia.FleetView,
            rio.HandheldEndpoint,
            farlandia.FleetMine(fleet='f1'),
            3,
        ],
    )
    def test_not_a_command(self, obj):
        assert not is_command_class(obj)

    def test_an_undecorated_subclass_isn_t_one(self):
        class Undecorated(farlandia.FleetMine):
            pass

        assert not is_command_class(Undecorated)


class TestCommandDoc:
    def test_its_phrases_and_slots(self):
        found = introspect_command(farlandia.FleetMine)
        assert isinstance(found, CommandDoc)
        assert (found.phrase, found.extra_phrases) == ('fleet {fleet} mine', ('detachment {detachment} mine',))
        assert found.slots == (
            SlotDoc(name='fleet', field='fleet', kind=farlandia.FLEET, required=True, many=False, rest=False),
            SlotDoc(name='detachment', field='fleet', kind=farlandia.DETACHMENT, required=True, many=False, rest=False),
        )

    def test_its_flags(self):
        (found,) = introspect_command(farlandia.FleetMine).flags
        assert found == FlagDoc(
            name='for', field='for_', kind=Duration(), switch=False, negated=False, required=False, many=False
        )
        into, quiet = introspect_command(farlandia.FleetsMerge).flags
        assert (into.name, into.required, into.switch) == ('into', True, False)
        assert (quiet.name, quiet.switch, quiet.kind) == ('quiet', True, Switch())

    def test_its_kinds_and_its_schema(self):
        found = introspect_command(farlandia.FleetDock)
        assert found.kinds['station'] == parsed.Name('station', scope='fleet')
        assert isinstance(found.schema, SchemaDoc)
        assert [f.attr for f in found.schema.fields] == ['fleet', 'station']

    def test_several_words_and_the_rest_of_the_line(self):
        goods = introspect_command(farlandia.FleetSell).slots[1]
        assert (goods.many, goods.rest) == (True, False)
        variables = introspect_command(farlandia.FleetRun).slots[2]
        assert (variables.rest, variables.required, type(variables.kind)) == (True, False, Pairs)

    def test_its_constants(self):
        mine = introspect_command(farlandia.FleetMine)
        assert (mine.effect, mine.asks, mine.interactive, mine.polymorphic) == (parsed.Effect.WRITE, False, False, True)
        assert introspect_command(farlandia.FleetBuyShip).asks
        fit = introspect_command(farlandia.ShipFit)
        assert (fit.interactive, fit.instead) == (True, farlandia.ShipsMakeAdd)
        assert introspect_command(farlandia.FleetsShow).reply is farlandia.FleetView
        assert introspect_command(farlandia.ShipsMakeAdd).polymorphic is None

    def test_the_class_it_takes_its_fields_from(self):
        assert introspect_command(rio.HandheldConnect).fields_from == (rio.HandheldEndpoint,)
        assert introspect_command(farlandia.FleetMine).fields_from == ()  # its bases are commands

    def test_not_a_command_is_refused(self):
        with pytest.raises(TypeError, match=r'introspect_command\(\) takes a command class'):
            introspect_command(farlandia.FleetCommand)

    def test_a_tree_the_size_of_a_real_one(self):
        assert all(introspect_command(cls).phrase for cls in tree())
