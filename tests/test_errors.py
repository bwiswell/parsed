"""Tests for ``parsed/errors.py``: one base for every error parsed raises."""

import parsed
from parsed.errors import DeclarationError, ParsedError, ReadError, RefusedError, RenderError, TimedOutError


def test_exported():
    assert parsed.ParsedError is ParsedError
    assert parsed.DeclarationError is DeclarationError
    assert parsed.ReadError is ReadError


def test_a_declaration_error_is_parsed_s_and_a_type_error():
    # A mistake in a class's definition is a TypeError in Python, so a caller
    # catching that still catches this one.
    assert issubclass(DeclarationError, ParsedError)
    assert issubclass(DeclarationError, TypeError)


def test_a_read_error_is_parsed_s_and_a_value_error():
    # A line that doesn't read is a value Python can't read, so a caller catching
    # ValueError still catches this one.
    assert issubclass(ReadError, ParsedError)
    assert issubclass(ReadError, ValueError)


class TestReadError:
    def test_its_parts_default_to_none_but_the_line_s(self):
        found = ReadError('no command: the line has no words')
        assert str(found) == found.message == 'no command: the line has no words'
        assert (found.kind, found.line, found.column) == ('usage', '', 0)
        assert (found.word, found.field, found.hint, found.suggestions) == (None, None, None, ())

    def test_its_parts_as_given(self):
        found = ReadError(
            'log {n}: must be >= 1, got 0',
            kind='validation',
            line='log 0',
            column=4,
            word='0',
            field='n',
            hint='log [<n>]',
            suggestions=['1'],
        )
        assert (found.kind, found.column, found.word, found.field) == ('validation', 4, '0', 'n')
        assert found.suggestions == ('1',)

    def test_as_data_with_only_the_parts_it_has(self):
        assert ReadError('fleet: which fleet?', line='fleet', column=5, hint='fleet <fleet> …').to_json() == {
            'error': 'usage',
            'message': 'fleet: which fleet?',
            'line': 'fleet',
            'column': 5,
            'hint': 'fleet <fleet> …',
        }
        found = ReadError("no command 'flet'", line='flet', word='flet', suggestions=('fleet',)).to_json()
        assert (found['word'], found['suggestions']) == ('flet', ['fleet'])
        assert 'field' not in found


class TestRefusedError:
    def test_parsed_s(self):
        assert parsed.RefusedError is RefusedError
        assert issubclass(RefusedError, ParsedError)

    def test_its_parts(self):
        found = RefusedError('log is for a person at a terminal', line='log 3')
        assert str(found) == found.message == 'log is for a person at a terminal'
        assert (found.line, found.instead) == ('log 3', None)

    def test_as_data_with_what_s_said_in_its_place_where_there_s_one(self):
        message = 'ship {ship} fit is for a person at a terminal: say `ships make <ship> add <part>` instead'
        assert RefusedError(message, line='ship s1 fit', instead='ships make {ship} add {part}').to_json() == {
            'error': 'refused',
            'message': message,
            'line': 'ship s1 fit',
            'instead': 'ships make {ship} add {part}',
        }
        assert 'instead' not in RefusedError('log is for a person at a terminal', line='log').to_json()


def test_a_render_error_is_parsed_s_and_a_value_error():
    assert parsed.RenderError is RenderError
    assert issubclass(RenderError, ParsedError)
    assert issubclass(RenderError, ValueError)


def test_a_timed_out_error_is_parsed_s_and_a_timeout_error():
    # A wait that runs out is a TimeoutError in Python, so a caller catching that still catches this one.
    assert parsed.TimedOutError is TimedOutError
    assert issubclass(TimedOutError, ParsedError)
    assert issubclass(TimedOutError, TimeoutError)


def test_a_timed_out_error_carries_the_last_reply_and_the_time_waited():
    found = TimedOutError('fleets show {fleet}: docked=true not met within 30s', reply=3, waited=30.0)
    assert (str(found), found.message, found.reply, found.waited) == (
        'fleets show {fleet}: docked=true not met within 30s',
        'fleets show {fleet}: docked=true not met within 30s',
        3,
        30.0,
    )
