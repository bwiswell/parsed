"""Tests for ``parsed/reply.py``: what running a line comes to, and its exit code."""

from __future__ import annotations

import typing

import _support_farlandia as farlandia
import pytest

import parsed
from parsed.reply import CODES, Result, terminal


class TestTheResult:
    def test_a_line_that_went_well(self):
        found = Result('fleets show f1', 'fleets show {fleet}', done=True, reply=farlandia.FleetView(fleet='f1'))
        assert (found.ok, found.code, found.error) == (True, 0, None)

    @pytest.mark.parametrize(('kind', 'code'), [('usage', 2), ('validation', 4), ('handler', 1), ('other', 1)])
    def test_its_exit_code_by_its_error(self, kind, code):
        assert Result('x', ok=False, error={'error': kind, 'message': 'wrong'}).code == code

    def test_the_codes_are_tooled_s(self):
        assert dict(CODES) == {'usage': 2, 'validation': 4, 'handler': 1}

    def test_its_exception_kept_but_not_compared(self):
        error = KeyError('nope')
        kept = Result('x', ok=False, exception=error)
        assert kept.exception is error
        assert kept == Result('x', ok=False)
        assert 'exception' not in repr(kept)


class TestAsJson:
    def test_every_key_always_there(self):
        assert Result('relay run', 'relay run', done=True).to_json() == {
            'command': 'relay run',
            'line': 'relay run',
            'ok': True,
            'done': True,
            'asks': None,
            'met': None,
            'reply': None,
            'text': None,
            'error': None,
        }

    def test_a_reply_dumped_as_seared_writes_it(self):
        reply = farlandia.FleetView(fleet='f1', docked=True)
        found = Result('fleets show f1', 'fleets show {fleet}', done=True, reply=reply, text=str(reply)).to_json()
        assert found['reply'] == {'fleet': 'f1', 'docked': True}
        assert found['text'] == "FleetView(fleet='f1', docked=True)"

    def test_an_error_as_data(self):
        error = {'error': 'handler', 'message': "KeyError: 'nope'"}
        assert Result('x', ok=False, error=error).to_json()['error'] == error


def test_its_annotations_resolve():
    # As the root's test pins for every class it exports: tooling evaluates them.
    assert 'reply' in typing.get_type_hints(Result)


def test_exported():
    assert parsed.Result is Result


class TestAsk:
    def test_a_question_and_what_acts_on_a_yes(self):
        then = lambda: 'bought'  # noqa: E731 -- what acts, named for the test
        asked = parsed.Ask('Buy a hauler for 1,200 credits?', then)
        assert (asked.question, asked.then) == ('Buy a hauler for 1,200 credits?', then)

    @pytest.mark.parametrize(
        ('question', 'then', 'message'),
        [
            ('', lambda: None, r"Ask\('', …\): a question is a sentence, for a person"),
            (3, lambda: None, r'Ask\(3, …\): a question is a sentence'),
            ('Buy it?', 'bought', r"Ask\('Buy it\?', 'bought'\): then is what acts on a yes, a callable of nothing"),
        ],
    )
    def test_refused_unless_it_s_a_question_and_a_callable(self, question, then, message):
        with pytest.raises(TypeError, match=message):
            parsed.Ask(question, then)

    def test_a_result_that_stopped_at_one(self):
        found = Result('fleet f1 buy ship hauler', 'fleet {fleet} buy ship {hull}', asks='Buy it?', text='Buy it?')
        assert (found.ok, found.done, found.code) == (True, False, 0)
        assert found.to_json()['asks'] == 'Buy it?'


class TestTerminal:
    @pytest.mark.parametrize(('said', 'yes'), [('y', True), (' YES ', True), ('n', False), ('', False), ('yep', False)])
    async def test_yes_for_y_or_yes(self, monkeypatch, said, yes):
        asked = []
        monkeypatch.setattr('builtins.input', lambda prompt: asked.append(prompt) or said)
        assert await terminal('Buy it?') is yes
        assert asked == ['Buy it? [y/N] ']

    async def test_no_at_the_end_of_input(self, monkeypatch):
        def ended(prompt):
            raise EOFError

        monkeypatch.setattr('builtins.input', ended)
        assert await terminal('Buy it?') is False
