"""Tests for ``parsed/errors.py``: one base for every error parsed raises."""

import parsed
from parsed.errors import DeclarationError, ParsedError


def test_exported():
    assert parsed.ParsedError is ParsedError
    assert parsed.DeclarationError is DeclarationError


def test_a_declaration_error_is_parsed_s_and_a_type_error():
    # A mistake in a class's definition is a TypeError in Python, so a caller
    # catching that still catches this one.
    assert issubclass(DeclarationError, ParsedError)
    assert issubclass(DeclarationError, TypeError)
