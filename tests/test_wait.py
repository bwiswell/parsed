"""Tests for ``parsed/wait.py``: ``--until`` conditions on a read's reply, and how long to wait."""

from __future__ import annotations

import enum

import _support_farlandia as farlandia
import pytest
import seared

import parsed
from parsed.wait import FLAGS, SWITCHES, TIMEOUT, Condition, Wait, problem


class Mode(enum.Enum):
    IDLE = 'idle'
    MINING = 'mining'


@parsed.parsed
class Ship(parsed.Parsed):
    name: str = seared.Str(required=True)
    fuel: float = seared.Float(default=0.0)


@parsed.parsed
class Board(parsed.Parsed):
    """A reply with a little of everything a path may step through."""

    fleet: str = seared.Str(required=True)
    docked: bool = seared.Bool(default=False)
    mode: Mode = seared.Enum(enum=Mode, default=Mode.IDLE)
    ships: list[Ship] = seared.T(Ship, many=True, default_factory=list)
    cargo: dict[str, float] = seared.Float(keyed=True, default_factory=dict)
    flagship: Ship | None = seared.T(Ship, default=None)


class TestConditions:
    @pytest.mark.parametrize(
        ('text', 'path', 'value'),
        [
            ('docked=true', ('docked',), True),
            ('fuel=40', ('fuel',), 40),
            ('mode=idle', ('mode',), 'idle'),  # not JSON, so a string
            ('mode="idle"', ('mode',), 'idle'),
            ('name=null', ('name',), None),
            ('ships.0.name=Frigate', ('ships', '0', 'name'), 'Frigate'),
            ('note=a=b', ('note',), 'a=b'),  # the first `=` splits it
            ('share="30%"', ('share',), '30%'),
            ('at=-4,-1.0', ('at',), '-4,-1.0'),
        ],
    )
    def test_read_from_path_and_value(self, text, path, value):
        assert Condition.parse(text) == Condition(path, value, text)

    @pytest.mark.parametrize('text', ['docked', 'docked.=true', '.docked=true', '=true'])
    def test_refused_unless_path_equals_value(self, text):
        with pytest.raises(ValueError, match=r'a condition is path=value, the path dotted'):
            Condition.parse(text)

    @pytest.mark.parametrize(
        ('text', 'met'),
        [
            ('docked=true', True),
            ('docked=1', False),  # a number is no boolean
            ('fuel=40', True),
            ('fuel=40.0', True),  # 40 is 40.0
            ('ships.1.name=Hauler', True),
            ('ships.2.name=Hauler', False),  # past the list's end
            ('ships.name=Hauler', False),  # a list needs its index
            ('cargo.iron=5', True),
            ('cargo={"iron": 5}', True),
            ('nowhere=1', False),
        ],
    )
    def test_met_where_the_wire_form_holds_the_value(self, text, met):
        wire = {'docked': True, 'fuel': 40.0, 'ships': [{'name': 'Frigate'}, {'name': 'Hauler'}], 'cargo': {'iron': 5}}
        assert Condition.parse(text).met(wire) is met

    def test_found_with_what_it_holds(self):
        assert Condition.parse('cargo.iron=0').find({'cargo': {'iron': 5}}) == (True, 5)
        assert Condition.parse('cargo.coal=0').find({'cargo': {'iron': 5}}) == (False, None)


class TestTheWait:
    def test_every_condition_met_on_the_reply_s_wire_form(self):
        wait = Wait((Condition.parse('docked=true'), Condition.parse('mode=mining')))
        assert wait.met(Board(fleet='f1', docked=True, mode=Mode.MINING))
        assert not wait.met(Board(fleet='f1', docked=True))

    def test_thirty_seconds_by_default(self):
        assert Wait(()).timeout == TIMEOUT == 30.0

    def test_its_flags(self):
        assert FLAGS == ('until', 'timeout', 'watch', 'count')
        assert {'watch'} == SWITCHES

    def test_a_watch_has_no_count_and_its_bound_by_default(self):
        found = Wait((), watch=True)
        assert (found.watch, found.count, found.timeout) == (True, None, TIMEOUT)


class TestPaths:
    @pytest.mark.parametrize(
        'path',
        ['docked', 'mode', 'ships.0.name', 'ships.3.fuel', 'cargo.iron', 'cargo.anything', 'flagship.name', 'ships'],
    )
    def test_a_path_the_reply_has(self, path):
        assert problem(Condition.parse(f'{path}=1'), Board) is None

    @pytest.mark.parametrize(
        ('path', 'says', 'near'),
        [
            ('dockd', "--until 'dockd' names no field of Board; did you mean 'docked'?", ['docked']),
            ('ships.0.nmae', "--until 'ships.0.nmae' names no field of Board; did you mean 'name'?", ['name']),
            ('ships.name', "--until 'ships.name' names no field of Board; 'ships' is a list: ships.0.name", []),
            (
                'zzz',
                "--until 'zzz' names no field of Board; the fields there: fleet, docked, mode, ships, cargo, flagship",
                ['fleet', 'docked', 'mode', 'ships', 'cargo', 'flagship'],
            ),
            ('docked.more', "--until 'docked.more' names no field of Board; 'docked' has no fields", []),
        ],
    )
    def test_a_path_it_hasn_t(self, path, says, near):
        assert problem(Condition.parse(f'{path}=1'), Board) == (says, near)

    def test_the_fixture_s_reply(self):
        assert problem(Condition.parse('docked=true'), farlandia.FleetView) is None
        assert problem(Condition.parse('docekd=true'), farlandia.FleetView) is not None
