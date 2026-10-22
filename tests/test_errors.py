"""Tests for ``parsed/errors.py``: one base for every error parsed raises."""

import parsed
from parsed.errors import DeclarationError, ParsedError, ReadError


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
