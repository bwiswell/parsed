"""Tests for ``parsed/doc/chains.py``: a chain as one tool call, its doc and schema, its call to its steps and back."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import ClassVar

import _support_check.chains as seeded
import _support_farlandia as farlandia
import pytest
import seared

import parsed
from parsed.doc import (
    ChainDoc,
    chain_schema,
    dump_chain,
    introspect_chain,
    introspect_command,
    json_schema,
    load_chain,
)
from parsed.errors import DeclarationError
from parsed.tree import Tree


@pytest.fixture(scope='module')
def tree() -> Tree:
    return Tree.collect('_support_farlandia', '_support_rio')


def _chain(*steps: type) -> Tree:
    return Tree(list(steps))


@parsed.parsed
class _Ship(parsed.Command):
    """A ship's orders."""

    STEPS = True

    ship: str = parsed.Str(required=True)


@parsed.parsed
class _ShipLook(_Ship):
    PHRASE = 'ship {ship} look'
    EFFECT = parsed.Effect.READ


@parsed.parsed
class _ShipScrap(_Ship):
    PHRASE = 'ship {ship} scrap'
    EFFECT = parsed.Effect.ACTION
    ASKS = True


@parsed.parsed
class _ShipDrift(_Ship):
    PHRASE = 'ship {ship} drift'  # declares no effect


class TestIntrospectChain:
    def test_the_fixture_s_chain(self, tree):
        found = introspect_chain(tree, farlandia.FleetCommand)
        assert isinstance(found, ChainDoc)
        assert (found.base, found.shared, found.heads) == (
            farlandia.FleetCommand,
            ('fleet',),
            ('fleet {fleet}', 'detachment {detachment}'),  # a twin's shared part beside the fleet's
        )
        assert [(slot.name, slot.field) for slot in found.slots] == [('fleet', 'fleet'), ('detachment', 'fleet')]
        assert found.schema.cls is farlandia.FleetCommand

    def test_each_step_by_its_words(self, tree):
        found = introspect_chain(tree, farlandia.FleetCommand)
        assert [(step.tag, step.phrase) for step in found.steps] == [
            ('mine', 'mine'),
            ('dock', 'dock {station}'),
            ('jump', 'jump {system}'),
            ('jump nearest', 'jump nearest {ore}'),
            ('move', 'move {to}'),
            ('sell', 'sell {goods}'),
        ]
        assert found.steps[0].command == introspect_command(farlandia.FleetMine)

    def test_its_effect_the_strongest_and_whether_any_step_asks(self, tree):
        found = introspect_chain(tree, farlandia.FleetCommand)
        assert (found.effect, found.asks) == (parsed.Effect.WRITE, False)
        mixed = introspect_chain(_chain(_ShipLook, _ShipScrap), _Ship)
        assert (mixed.effect, mixed.asks) == (parsed.Effect.ACTION, True)

    def test_no_effect_where_a_step_declares_none(self):
        assert introspect_chain(_chain(_ShipLook, _ShipDrift), _Ship).effect is None  # never inferred

    @pytest.mark.parametrize('base', [farlandia.FleetMine, farlandia.Log, 'fleet'])
    def test_a_chain_s_base(self, tree, base):
        with pytest.raises(TypeError, match=r"introspect_chain\(\) takes a chain's base with steps"):
            introspect_chain(tree, base)

    def test_with_steps_in_the_tree(self):
        with pytest.raises(TypeError, match=r"a chain's base with steps among the tree's commands"):
            introspect_chain(Tree([farlandia.Log]), farlandia.FleetCommand)

    def test_steps_told_apart_by_their_words(self):
        with pytest.raises(
            DeclarationError, match=r"'ship \{vessel\} go \{to\}' and 'boat \{vessel\} go \{to\}' are both tagged 'go'"
        ):
            introspect_chain(Tree.collect('_support_check.chains'), seeded.Vessel)

    def test_a_step_says_words_after_the_shared_part(self):
        @parsed.parsed
        class Named(_Ship):
            PHRASE = 'name {ship} {name}'

            name: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r"'name \{ship\} \{name\}' says no words after its chain's shared"):
            introspect_chain(_chain(_ShipLook, Named), _Ship)

    def test_the_tag_s_key_is_no_step_s_field(self):
        @parsed.parsed
        class Stepped(_Ship):
            PHRASE = 'ship {ship} pace {step}'

            step: int = parsed.Int(required=True)

        with pytest.raises(
            DeclarationError, match=r"Stepped has a field on 'step', the key a chain's steps are tagged"
        ):
            introspect_chain(_chain(Stepped), _Ship)

    def test_nor_the_steps_key_a_shared_one(self):
        @parsed.parsed
        class Walk(parsed.Command):
            STEPS = True

            steps: int = parsed.Int(required=True)

        @parsed.parsed
        class WalkOn(Walk):
            PHRASE = 'walk {steps} on'

        with pytest.raises(DeclarationError, match=r"Walk has a field on 'steps', the key a chain's steps stand under"):
            introspect_chain(_chain(WalkOn), Walk)


class TestChainSchema:
    def test_its_shared_fields_and_its_steps(self, tree):
        schema = chain_schema(tree, farlandia.FleetCommand)
        assert list(schema) == [
            '$schema',
            'title',
            'description',
            'x-effect',
            'type',
            'properties',
            'required',
            'unevaluatedProperties',
        ]
        assert (schema['title'], schema['x-effect'], schema['type']) == ('FleetCommand', 'write', 'object')
        assert schema['properties']['fleet'] == json_schema(farlandia.FleetMine)['properties']['fleet']
        assert (schema['required'], schema['unevaluatedProperties']) == (['fleet', 'steps'], False)
        steps = schema['properties']['steps']
        assert (steps['type'], steps['minItems']) == ('array', 1)
        assert [branch['properties']['step'] for branch in steps['items']['anyOf']] == [
            {'const': tag} for tag in ('mine', 'dock', 'jump', 'jump nearest', 'move', 'sell')
        ]

    def test_a_step_s_branch_its_own_fields_closed(self, tree):
        branches = chain_schema(tree, farlandia.FleetCommand)['properties']['steps']['items']['anyOf']
        jump = branches[2]
        assert jump == {
            'description': 'Jump to a system.',
            'x-moves': 'system',
            'type': 'object',
            'properties': {
                'step': {'const': 'jump'},
                'system': {'type': 'string', 'description': 'the system', 'x-kind': 'system'},
            },
            'required': ['step', 'system'],
            'unevaluatedProperties': False,
        }
        assert all('fleet' not in branch['properties'] for branch in branches)  # given once, at the top

    def test_where_the_chain_moves_and_what_follows_it(self, tree):
        branches = chain_schema(tree, farlandia.FleetCommand)['properties']['steps']['items']['anyOf']
        assert [branch.get('x-moves') for branch in branches] == [None, 'station', 'system', True, 'to', None]
        assert branches[1]['properties']['station']['x-follows'] is True
        assert branches[4]['properties']['to']['x-follows'] is True
        assert 'x-follows' not in branches[5]['properties']['goods']

    def test_asking_first(self):
        schema = chain_schema(_chain(_ShipLook, _ShipScrap), _Ship)
        assert (schema['x-effect'], schema['x-asks']) == ('action', True)
        assert schema['properties']['steps']['items']['anyOf'][1]['x-asks'] is True

    def test_the_same_bytes_every_time(self, tree):
        first = json.dumps(chain_schema(tree, farlandia.FleetCommand))
        assert json.dumps(chain_schema(Tree.collect('_support_farlandia'), farlandia.FleetCommand)) == first

    def test_a_step_s_definitions_at_its_root(self):
        @parsed.parsed
        class Cargo(seared.Seared):
            good: str = seared.Str(required=True)

        @parsed.parsed
        class ShipLoad(_Ship):
            PHRASE = 'ship {ship} load'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'cargo': parsed.kinds.Word()}

            cargo: Cargo | None = seared.T(Cargo, default=None)

        schema = chain_schema(_chain(_ShipLook, ShipLoad), _Ship)
        assert list(schema['$defs']) == ['Cargo']
        assert schema['properties']['steps']['items']['anyOf'][1]['properties']['cargo']['$ref'] == '#/$defs/Cargo'


#: The fixture's chain, as a tool call gives it, and its steps.
_CALL = {
    'fleet': 'f1',
    'steps': [
        {'step': 'jump', 'system': 'sol'},
        {'step': 'move', 'to': 'sol-belt'},
        {'step': 'mine', 'for': 5400.0},
    ],
}
_STEPS = [
    farlandia.FleetJump(fleet='f1', system='sol'),
    farlandia.FleetMove(fleet='f1', to='sol-belt'),
    farlandia.FleetMine(fleet='f1', for_=timedelta(hours=1, minutes=30)),
]


class TestLoadChain:
    def test_a_call_to_its_steps(self, tree):
        assert load_chain(tree, farlandia.FleetCommand, _CALL) == _STEPS

    @pytest.mark.parametrize(
        ('data', 'message'),
        [
            ({'fleet': 'f1'}, 'FleetCommand.steps: required key missing'),
            ({'fleet': 'f1', 'steps': []}, 'FleetCommand.steps: expected a list of steps, one at least'),
            ({'fleet': 'f1', 'steps': 'mine'}, "FleetCommand.steps: expected array, got 'mine'"),
            ({'fleet': 'f1', 'x': 1, 'steps': [{'step': 'mine'}]}, 'FleetCommand.x: unknown key'),
            ({'steps': [{'step': 'mine'}]}, 'FleetCommand.fleet: required key missing'),
            ({'fleet': 'f1', 'steps': ['mine']}, 'FleetCommand.steps[0]: expected object, got str'),
            ({'fleet': 'f1', 'steps': [{'system': 'sol'}]}, 'FleetCommand.steps[0].step: required key missing'),
            (
                {'fleet': 'f1', 'steps': [{'step': 'mine'}, {'step': 'fly'}]},
                "FleetCommand.steps[1].step: no step 'fly': one of mine, dock, jump, jump nearest, move, sell",
            ),
            ({'fleet': 'f1', 'steps': [{'step': 'jump'}]}, 'FleetCommand.steps[0].system: required key missing'),
            (
                {'fleet': 'f1', 'steps': [{'step': 'mine', 'fleet': 'f2'}]},
                "FleetCommand.steps[0].fleet: a chain's shared field, given once, at the top",
            ),
            (
                {'fleet': 'f1', 'steps': [{'step': 'mine', 'for': 'soon'}]},
                "FleetCommand.steps[0].for: cannot deserialize 'soon' as timedelta",
            ),
        ],
    )
    def test_refused_where_it_isn_t_one(self, tree, data, message):
        with pytest.raises(seared.ValidationError) as caught:
            load_chain(tree, farlandia.FleetCommand, data)
        assert str(caught.value) == message

    def test_an_object(self, tree):
        with pytest.raises(seared.ValidationError, match=r'FleetCommand: expected object, got list'):
            load_chain(tree, farlandia.FleetCommand, [])  # ty: ignore[invalid-argument-type] -- what's refused


class TestDumpChain:
    def test_its_steps_to_a_call(self):
        assert dump_chain(_STEPS) == _CALL

    def test_and_back(self, tree):
        steps = [farlandia.FleetMine(fleet='d2'), farlandia.FleetSell(fleet='d2', goods=['iron', 'coal'])]
        assert load_chain(tree, farlandia.FleetCommand, dump_chain(steps)) == steps

    @pytest.mark.parametrize(
        'steps',
        [[], [farlandia.Log()], [farlandia.FleetMine(fleet='f1'), farlandia.FleetsStart(on=True)]],
    )
    def test_one_chain_s_steps(self, steps):
        with pytest.raises(TypeError, match=r"dump_chain\(\) takes (a chain's|one chain's) steps"):
            dump_chain(steps)

    def test_sharing_its_fields_values(self):
        with pytest.raises(ValueError, match=r"a chain's steps share FleetCommand's fields: its steps' fleet differ"):
            dump_chain([farlandia.FleetMine(fleet='f1'), farlandia.FleetMine(fleet='f2')])
