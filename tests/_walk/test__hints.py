"""Tests for ``parsed/_walk/_hints.py``: a command's usage, and what may have been meant."""

from __future__ import annotations

import _support_farlandia as farlandia
import pytest

import parsed
from parsed._walk._hints import close, either, usage
from parsed.command import Command, declaration
from parsed.tree import Tree


def _usage(cls: type[Command], at: int = 0) -> str:
    found = declaration(cls)
    fields = {spec.attr: spec.field for spec in cls.__seared_fields__}
    return usage(found.phrases[at], Tree([cls]).flags_of(cls).values(), fields)


def _command(phrase: str, **fields: object) -> type[Command]:
    namespace: dict[str, object] = {'PHRASE': phrase, '__annotations__': dict.fromkeys(fields, object)}
    namespace.update(fields)
    return parsed.parsed(type('Cmd', (Command,), namespace))


class TestUsage:
    @pytest.mark.parametrize(
        ('cls', 'at', 'said'),
        [
            (farlandia.FleetMine, 0, 'fleet <fleet> mine [--for <for>]'),
            (farlandia.FleetMine, 1, 'detachment <detachment> mine [--for <for>]'),
            (farlandia.FleetDock, 0, 'fleet <fleet> dock [<station>]'),
            (farlandia.FleetDock, 1, 'fleet <fleet> dock nearest'),
            (farlandia.FleetSell, 0, 'fleet <fleet> sell <goods> …'),
            (farlandia.Log, 0, 'log [<n>]'),
            (farlandia.Say, 0, 'say <message …>'),
            (farlandia.FleetsMerge, 0, 'fleets merge <fleet> --into <into> [--quiet]'),
        ],
    )
    def test_a_phrase_and_its_flags(self, cls, at, said):
        assert _usage(cls, at) == said

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
