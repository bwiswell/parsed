"""Tests for ``parsed/reply.py``: what running a line comes to, and its exit code."""

from __future__ import annotations

import typing

import _support_farlandia as farlandia
import pytest

import parsed
from parsed.reply import CODES, Result


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
