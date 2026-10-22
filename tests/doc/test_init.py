"""Tests for ``parsed/doc/__init__.py``: the package's surface."""

import importlib

from parsed import doc
from parsed.doc import introspect, keys


def test_it_gathers_its_modules():
    # `json_schema` and `check` name the functions on the package, as seared's does, so their modules are imported
    # by their paths.
    assert doc.introspect_command is introspect.introspect_command
    assert doc.json_schema is importlib.import_module('parsed.doc.json_schema').json_schema
    assert doc.command_key is keys.command_key
    assert doc.check is importlib.import_module('parsed.doc.check').check
    assert set(doc.__all__) == {
        'CheckReport',
        'CommandDoc',
        'FlagDoc',
        'Problem',
        'SlotDoc',
        'check',
        'command_key',
        'introspect_command',
        'is_command_class',
        'json_schema',
    }
