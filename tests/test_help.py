"""Tests for ``parsed/help.py``: how a command is said and what it does, and what a line may still say."""

from __future__ import annotations

from typing import ClassVar

import _support_farlandia as farlandia
import _support_service as service
import pytest

import parsed
from parsed.help import Entry, cleaned, command, doc, listing, rows, summary
from parsed.tree import Tree


@pytest.fixture(scope='module')
def tree() -> Tree:
    return Tree.collect('_support_farlandia')


class TestACommand:
    def test_its_usage_doc_arguments_phrases_examples_and_notes(self, tree):
        assert command(tree, farlandia.FleetMine) == '\n\n'.join(
            [
                'fleet <fleet> mine [--for <for>]',
                'Mine until the hold is full.',
                '  <fleet>      the fleet\n  --for <for>  stop after this long',
                'Also said:\n  detachment <detachment> mine [--for <for>]',
                (
                    'Examples:\n  fleet <fleet> mine\n  fleet <fleet> mine --for <for>\n'
                    '  fleet prospector mine --for 1h30m'
                ),
                'It is a step: then joins another after it.',
            ]
        )

    def test_by_the_phrase_a_line_said(self, tree):
        said = command(tree, farlandia.FleetMine, phrase=1)
        assert said.splitlines()[0] == 'detachment <detachment> mine [--for <for>]'
        assert '  <detachment>  the fleet' in said.splitlines()  # the slot as the phrase says it
        assert 'Also said:\n  fleet <fleet> mine [--for <for>]' in said

    def test_a_short_form_beside_its_flag(self):
        run = Tree.collect('_support_service', under='relay')
        assert command(run, service.Run).splitlines()[-1] == (
            '  -c, --config <config>  the config file; left out, the service default'
        )

    def test_with_no_doc_what_its_words_are(self):
        @parsed.parsed
        class Tune(parsed.Command):
            PHRASE = 'tune {band}'
            SHORTS: ClassVar[dict[str, str]] = {'gain': 'g'}

            band: int = parsed.Int(required=True)
            gain: float = parsed.Float(default=0.0)
            loud: bool = parsed.Bool(default=False)
            hush: bool = parsed.Bool(default=True)

        assert command(Tree([Tune]), Tune).split('\n\n')[1].splitlines() == [
            '  <band>             a whole number',
            '  -g, --gain <gain>  a number',
            '  --loud             on when given',
            '  --no-hush          off when given',
        ]

    @pytest.mark.parametrize(
        ('cls', 'note'),
        [
            (farlandia.FleetBuyShip, 'It asks before it acts, and --yes answers it.'),
            (
                farlandia.FleetsShow,
                (
                    'It can wait on its reply: --until <path=value>, --timeout <span>, --watch, --count <n>; 30s at '
                    'most by default.'
                ),
            ),
            (farlandia.ShipFit, 'It is for a person at a terminal.'),
        ],
    )
    def test_what_it_asks_of_the_line(self, tree, cls, note):
        assert command(tree, cls).endswith(note)

    def test_one_that_asks_ends_its_usage_with_yes_and_says_what_it_does(self, tree):
        said = command(tree, farlandia.FleetsMerge).split('\n\n')
        assert said[0] == 'fleets merge <fleet> --into <into> [--quiet] [--yes]'
        assert said[2].splitlines()[-1] == '  --yes          answer each question it asks yes'

    def test_what_s_said_in_an_interactive_one_s_place(self, tree):
        said = command(tree, farlandia.ShipFit, instead='ships make <ship> add <part>')
        assert said.endswith('It is for a person at a terminal: say `ships make <ship> add <part>` instead.')

    def test_another_tree_s_command(self, tree):
        with pytest.raises(KeyError):
            command(tree, service.Run)


class TestAListing:
    def test_each_summary_in_a_column_after_the_widest(self):
        said = listing([Entry('relay run', 'Run it.'), Entry('relay validate-config', 'Check it.')])
        assert said == 'relay run              Run it.\nrelay validate-config  Check it.'

    def test_an_entry_with_none_alone(self):
        assert listing([Entry('relay …'), Entry('log', 'The log.')]) == 'relay …\nlog  The log.'
        assert listing([]) == ''

    def test_rows_indented(self):
        said = rows([('<fleet>', 'the fleet'), ('--for <for>', '')])
        assert said == ['  <fleet>      the fleet', '  --for <for>']


class TestDocstrings:
    def test_read_as_seared_s_pages_read_them(self):
        class Documented:
            """Read by :class:`~parsed.Tree`, as ``--help`` says.

            More, in a paragraph.
            """

        assert doc(Documented) == 'Read by `parsed.Tree`, as `--help` says.\n\nMore, in a paragraph.'
        assert summary(Documented) == 'Read by `parsed.Tree`, as `--help` says.'

    def test_none_for_none(self):
        class Bare:
            pass

        assert (doc(Bare), summary(Bare), cleaned('  ')) == (None, None, None)
