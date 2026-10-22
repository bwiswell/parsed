"""Tests for ``parsed/doc/__init__.py``: the package's surface."""

import importlib

from parsed import doc
from parsed.doc import introspect


def test_it_gathers_both_modules():
    # `json_schema` names the function on the package, as seared's does, so the module is imported by its path.
    assert doc.introspect_command is introspect.introspect_command
    assert doc.json_schema is importlib.import_module('parsed.doc.json_schema').json_schema
    assert set(doc.__all__) == {
        'CommandDoc',
        'FlagDoc',
        'SlotDoc',
        'introspect_command',
        'is_command_class',
        'json_schema',
    }
