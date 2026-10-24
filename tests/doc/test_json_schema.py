"""Tests for ``parsed/doc/json_schema.py``: a command's arguments, as a closed JSON Schema."""

from __future__ import annotations

import json

import _support_farlandia as farlandia
import _support_protocol as protocol
import pytest
from seared.doc import json_schema as seared_json_schema

from bench.tree import tree
from parsed.doc import json_schema


class TestSchema:
    def test_seared_s_load_schema_closed(self):
        found = json_schema(farlandia.FleetMine)
        seared = seared_json_schema(farlandia.FleetMine, mode='load', unknown='raise')
        assert found['unevaluatedProperties'] is False
        assert found['required'] == seared['required']
        assert set(found['properties']) == set(seared['properties']) == {'fleet', 'for'}

    def test_a_protocol_s_bounds_are_its_own(self):
        port = json_schema(protocol.HandheldConnect)['properties']['port']
        assert (port['minimum'], port['maximum'], port['default']) == (1, 65535, 5084)

    def test_its_keys_in_one_order(self):
        assert list(json_schema(farlandia.FleetBuyShip))[:6] == [
            '$schema',
            'title',
            'description',
            'x-phrase',
            'x-effect',
            'x-asks',
        ]

    def test_the_same_bytes_every_time(self):
        assert json.dumps(json_schema(farlandia.FleetDock)) == json.dumps(json_schema(farlandia.FleetDock))


class TestNames:
    def test_a_name_s_category_and_scope(self):
        props = json_schema(farlandia.FleetDock)['properties']
        assert props['fleet']['x-kind'] == 'fleet'
        assert (props['station']['x-kind'], props['station']['x-scope']) == ('station', 'fleet')

    def test_pairs_too(self):
        props = json_schema(farlandia.FleetRun)['properties']
        assert props['variables']['x-kind'] == 'variable'
        assert props['variables']['x-scope'] == 'routine'

    def test_a_field_of_another_kind_has_none(self):
        props = json_schema(farlandia.FleetMine)['properties']
        assert 'x-kind' not in props['for']


class TestTheCommandsOwn:
    def test_its_phrases(self):
        found = json_schema(farlandia.FleetMine)
        assert found['x-phrase'] == 'fleet {fleet} mine'
        assert found['x-extra-phrases'] == ['detachment {detachment} mine']
        assert 'x-extra-phrases' not in json_schema(farlandia.Say)

    @pytest.mark.parametrize(
        ('cls', 'key', 'value'),
        [
            (farlandia.Log, 'x-effect', 'read'),
            (farlandia.FleetBuyShip, 'x-asks', True),
            (farlandia.ShipFit, 'x-interactive', True),
            (farlandia.ShipFit, 'x-instead', 'ships make {ship} add {part}'),
            (farlandia.FleetsShow, 'x-reply', 'FleetView'),
        ],
    )
    def test_each_where_it_s_declared(self, cls, key, value):
        assert json_schema(cls)[key] == value

    def test_none_where_it_isn_t(self):
        found = json_schema(farlandia.ShipsMakeAdd)
        assert not {'x-asks', 'x-interactive', 'x-instead', 'x-reply'} & set(found)

    def test_not_a_command_is_refused(self):
        with pytest.raises(TypeError, match=r'json_schema\(\) takes a command class'):
            json_schema(farlandia.FleetView)


def test_a_tree_the_size_of_a_real_one():
    for cls in tree():
        assert json_schema(cls)['x-phrase'] == cls.PHRASE
