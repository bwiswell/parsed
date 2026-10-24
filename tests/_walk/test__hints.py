"""Tests for ``parsed/_walk/_hints.py``: a command's usage, and what may have been meant."""

from __future__ import annotations

import enum

import _support_farlandia as farlandia
import _support_tooled as tooled
import pytest

import parsed
from parsed._walk._hints import close, either, label, passes, usage
from parsed.command import Command, declaration
from parsed.kinds import Choice, Duration, Name, Number, Word
from parsed.tree import Tree


class Mode(enum.Enum):
    VISUAL = 'visual'
    TEXT = 'text'


def _usage(cls: type[Command], at: int = 0, *, asks: bool = False) -> str:
    found = declaration(cls)
    fields = {spec.attr: spec.field for spec in cls.__seared_fields__}
    return usage(found.phrases[at], Tree([cls]).flags_of(cls).values(), fields, asks=asks)


def _command(phrase: str, **fields: object) -> type[Command]:
    namespace: dict[str, object] = {'PHRASE': phrase, '__annotations__': dict.fromkeys(fields, object)}
    namespace.update(fields)
    return parsed.parsed(type('Cmd', (Command,), namespace))


class TestUsage:
    @pytest.mark.parametrize(
        ('cls', 'at', 'said'),
        [
            (farlandia.FleetMine, 0, 'fleet <fleet> mine [--for <span>]'),
            (farlandia.FleetMine, 1, 'detachment <detachment> mine [--for <span>]'),
            (farlandia.FleetDock, 0, 'fleet <fleet> dock [<station>]'),
            (farlandia.FleetDock, 1, 'fleet <fleet> dock nearest'),
            (farlandia.FleetSell, 0, 'fleet <fleet> sell <goods> …'),
            (farlandia.Log, 0, 'log [<n>]'),
            (farlandia.Say, 0, 'say <message …>'),
            (farlandia.FleetsMerge, 0, 'fleets merge <fleet> --into <fleet> [--quiet]'),
        ],
    )
    def test_a_phrase_and_its_flags(self, cls, at, said):
        assert _usage(cls, at) == said

    def test_one_that_passes_a_line_on_says_its_flags_first(self):
        found = declaration(tooled.Do)
        flags = Tree([tooled.Do]).flags_of(tooled.Do).values()
        fields = {spec.attr: spec.field for spec in tooled.Do.__seared_fields__}
        said = usage(found.phrases[0], flags, fields, asks=True, passing=True)
        assert said == 'do [--policy <path>] [--pretty] [--select <select>] [--yes] <line …>'
        assert passes(found, found.phrases[0])
        assert not passes(declaration(farlandia.Say), declaration(farlandia.Say).phrases[0])  # a rest, not a Line

    def test_one_that_asks_ends_with_yes(self):
        assert _usage(farlandia.FleetsMerge, asks=True) == 'fleets merge <fleet> --into <fleet> [--quiet] [--yes]'
        assert _usage(farlandia.FleetBuyShip, asks=True) == 'fleet <fleet> buy ship <hull> [--yes]'

    def test_a_negated_switch_and_a_list_s_flag(self):
        cls = _command('tag', stop=parsed.Bool(default=True), tags=parsed.Str(many=True, default_factory=list))
        assert _usage(cls) == 'tag [--no-stop] [--tags <tags> …]'

    def test_a_required_list_s_flag_unbracketed(self):
        assert _usage(_command('wait', until=parsed.Str(many=True, required=True))) == 'wait --until <until> …'

    def test_an_optional_list_and_rest(self):
        assert _usage(_command('note {words**}', words=parsed.Str(default=''))) == 'note [<words …>]'
        assert _usage(_command('sell {goods}', goods=parsed.Str(many=True, default_factory=list))) == (
            'sell [<goods> …]'
        )


class TestLabel:
    def test_by_its_kind_else_the_flag_s_name(self):
        assert label(Duration(), parsed.TimeDelta(), 'for') == 'span'
        assert label(Name('good_in_deposit', label='ore'), parsed.Str(), 'ore') == 'ore'
        assert label(Word(), parsed.Str(), 'label') == 'label'

    def test_then_its_literal_words(self):
        assert label(Number(suffix='%', words={'off': None}), parsed.Float(), 'share') == 'n|off'
        assert label(Word(words={'here': 'h'}), parsed.Str(), 'at') == 'at|here'

    def test_a_choice_s_values(self):
        assert label(Choice(), parsed.Enum(enum=Mode), 'mode') == 'visual|text'

    def test_in_a_usage(self):
        cls = _command('tune', at=parsed.Float(default=0.0), mode=parsed.Str(default=''))
        assert _usage(cls) == 'tune [--at <n>] [--mode <mode>]'


class TestMeant:
    def test_close_words_closest_first(self):
        assert close('mien', ['buy', 'dock', 'mine', 'sell']) == ['mine']
        assert close('flet', ['fleet', 'fleets', 'log']) == ['fleet', 'fleets']
        assert close('xyz', ['buy', 'dock']) == []

    def test_at_most_three(self):
        assert len(close('ab', ['ab1', 'ab2', 'ab3', 'ab4'])) == 3

    @pytest.mark.parametrize(
        ('words', 'said'),
        [(['mine'], 'mine'), (['fleet', 'fleets'], 'fleet or fleets'), (['a', 'b', 'c'], 'a, b or c')],
    )
    def test_either(self, words, said):
        assert either(words) == said
