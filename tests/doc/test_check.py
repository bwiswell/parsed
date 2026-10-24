"""Tests for ``parsed/doc/check.py``: ``parsed check``, a conformance check of a package's commands."""

import enum
import importlib

import _support_check.examples as examples
import _support_farlandia as farlandia
import pytest
import seared

import parsed
from parsed.command import declaration
from parsed.doc import chain_schema, check, json_schema
from parsed.tree import Tree

# The package names the function `check`, so the module is imported by its path.
checking = importlib.import_module('parsed.doc.check')


class Colour(enum.Enum):
    RED = 'red'
    GREEN = 'green'


class TestTheFixtures:
    def test_every_one_passes(self):
        report = check(['_support_farlandia', '_support_protocol'])
        assert report.ok, report.problems
        assert (report.commands, report.schemas) == (17, 17)
        assert report.examples == 11
        assert report.round_trips > report.commands  # an instance with every field, where it isn't the other
        assert report.chains == 1  # the fleet's orders
        assert report.skipped == {}

    def test_the_report_as_data(self):
        report = check(['_support_protocol'])
        assert report.to_json() == {
            'targets': ['_support_protocol'],
            'ok': True,
            'commands': 1,
            'checked': {'round-trips': 2, 'examples': 0, 'schemas': 1, 'chains': 0},
            'skipped': {},
            'problems': [],
        }


class TestSeededFaults:
    def test_examples_that_rot(self):
        report = check(['_support_check.examples'])
        assert not report.ok
        found = [(p.check, p.command, p.line, p.message) for p in report.problems]
        assert found == [
            ('example', '_support_check.examples.Mine', 'mien <fleet>', "no command 'mien'; did you mean mine?"),
            ('example', '_support_check.examples.Mine', 'dig <site>', 'it reads as Dig, not Mine'),
            ('example', '_support_check.examples.Log', 'log 0', 'log <n>: must be >= 1, got 0'),
            (
                'example',
                '_support_check.examples.Look',
                'look <fleet> --until dockd=true',
                "--until 'dockd' names no field of Seen; did you mean 'docked'?",
            ),
        ]

    def test_a_round_trip_that_fails(self):
        (problem,) = check(['_support_check.round_trip']).problems
        assert (problem.check, problem.line) == ('round-trip', 'shout EXAMPLE')
        assert problem.message == "it reads back as Shout(word='EXAMPLE'), not Shout(word='example')"

    def test_a_tree_that_won_t_build(self):
        report = check(['_support_check.collision'])
        assert report.commands == 0
        (problem,) = report.problems
        assert (problem.check, problem.command) == ('tree', None)
        assert problem.message == "'dock {station}' (Dock) and 'dock {berth}' (Berth) read the same lines"

    def test_no_commands(self):
        (problem,) = check(['_support_check.empty']).problems
        assert problem.message == 'no commands in _support_check.empty'

    def test_a_schema_too_big(self):
        report = check(['_support_protocol'], max_schema_bytes=100)
        (problem,) = report.problems
        assert problem.check == 'schema'
        assert problem.message.startswith('it takes 668 bytes, over 100')

    def test_a_chain_whose_steps_share_their_words(self):
        report = check(['_support_check.chains'])
        assert (report.commands, report.chains) == (2, 1)
        (problem,) = report.problems  # each step's group round-trips: a ship's, and a boat's
        assert (problem.check, problem.command) == ('chain', '_support_check.chains.Vessel')
        assert problem.message.startswith(
            "its schema doesn't build: 'ship {vessel} go {to}' and 'boat {vessel} go {to}' are both tagged 'go'"
        )

    def test_a_chain_s_schema_too_big(self):
        (problem,) = check(['_support_farlandia'], max_chain_bytes=100).problems
        assert problem.check == 'chain'
        assert problem.message.startswith('its schema takes 2084 bytes, over 100')

    def test_a_target_that_doesn_t_import(self):
        with pytest.raises(ImportError):
            check(['_support_nowhere'])


class TestSkipped:
    def test_a_field_no_word_fits(self):
        report = check(['_support_check.skipped'])
        assert report.ok
        assert report.skipped == {'_support_check.skipped.Hail': ('sign',)}
        assert (report.round_trips, report.examples, report.schemas) == (0, 1, 1)  # its example and schema still


class TestGeneratedExamples:
    @pytest.mark.parametrize(
        ('field', 'expected'),
        [
            (seared.Str(), 'example'),
            (seared.Str(max_length=1), 'a'),
            (seared.Str(min_length=10), 'e' * 10),
            (seared.Str(pattern='[0-9]+'), '1'),
            (seared.Int(), 1),
            (seared.Int(ge=5), 5),
            (seared.Int(gt=10), 11),
            (seared.Int(lt=0), -1),
            (seared.Float(le=0.5), 0.5),
            (seared.Float(gt=2), 2.5),
            (seared.Bool(default=False), True),
            (seared.Bool(default=True), False),
            (seared.Enum(enum=Colour), Colour.RED),
            (seared.Str(many=True), ['example']),
            (seared.Str(keyed=True), {'key': 'example'}),
        ],
    )
    def test_from_its_type_and_constraints(self, field, expected):
        assert checking._example(field) == expected

    @pytest.mark.parametrize('field', [seared.Str(pattern='[A-Z]{3}'), seared.Bytes()])
    def test_none_to_be_had(self, field):
        assert checking._example(field) is checking._UNMADE

    def test_a_kind_s_own_example_first(self):
        assert checking._example(seared.Str(many=True), 'fleet=f1') == ['fleet=f1']
        assert checking._example(seared.Str(), None) == 'example'  # none of its own

    def test_a_kind_of_an_app_s_own_with_its_example_round_trips(self):
        # tooled's `slot=value` words: a value made from the type alone ('example') wouldn't read.
        assert check(['_support_tooled']).ok

    def test_two_instances_one_with_its_required_fields(self):
        assert checking._instances(examples.Log) == ([examples.Log(), examples.Log(n=1)], [])
        assert checking._instances(examples.Mine) == (
            [examples.Mine(fleet='example')],
            [],
        )  # one: every field's required


class TestShape:
    @pytest.fixture
    def paint(self):
        @parsed.parsed
        class Paint(parsed.Command):
            PHRASE = 'paint {colour}'

            colour: Colour = parsed.Enum(enum=Colour, required=True)

        return declaration(Paint)

    def test_a_closed_object_of_enums_holds(self, paint):
        assert checking._shape(json_schema(paint.cls), paint) == []

    def test_an_open_object(self, paint):
        schema = json_schema(paint.cls)
        del schema['unevaluatedProperties']
        assert checking._shape(schema, paint) == [
            "it isn't a closed object: a decoder would give keys the command doesn't take"
        ]

    @pytest.mark.parametrize(
        ('values', 'fault'),
        [
            ([], 'an enum with no values'),
            ([['red']], 'an enum of values that are not JSON scalars'),
            (['red', 'red'], 'an enum with a value twice'),
        ],
    )
    def test_an_enum_a_decoder_can_t_hold(self, paint, values, fault):
        schema = json_schema(paint.cls)
        schema['properties']['colour']['enum'] = values
        assert checking._shape(schema, paint) == [f'/properties/colour: {fault}']

    def test_choices_with_no_enum(self, paint):
        schema = json_schema(paint.cls)
        del schema['properties']['colour']['enum']
        assert checking._shape(schema, paint) == [
            "colour is one of a field's choices, but its schema has no enum of them"
        ]


class TestChainShape:
    @pytest.fixture
    def schema(self):
        return chain_schema(Tree.collect('_support_farlandia'), farlandia.FleetCommand)

    def test_a_closed_object_of_closed_tagged_steps_holds(self, schema):
        assert checking._chain_shape(schema) == []

    def test_an_open_object(self, schema):
        del schema['unevaluatedProperties']
        assert checking._chain_shape(schema) == [
            "it isn't a closed object: a decoder would give keys the chain doesn't take"
        ]

    def test_a_step_open_or_untagged(self, schema):
        mine, dock, *_ = schema['properties']['steps']['items']['anyOf']
        del mine['unevaluatedProperties']
        dock['properties']['step'] = {'type': 'string'}
        assert checking._chain_shape(schema) == [
            "step 'mine' is not a closed object tagged by a const",
            'step None is not a closed object tagged by a const',
        ]
