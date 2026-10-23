"""Tests for ``parsed/doc/__init__.py``: the package's surface."""

import importlib

from parsed import doc
from parsed.doc import chains, introspect, keys


def test_it_gathers_its_modules():
    # `json_schema` and `check` name the functions on the package, as seared's does, so their modules are imported
    # by their paths.
    assert doc.introspect_command is introspect.introspect_command
    assert doc.json_schema is importlib.import_module('parsed.doc.json_schema').json_schema
    assert doc.command_key is keys.command_key
    assert doc.check is importlib.import_module('parsed.doc.check').check
    assert doc.chain_schema is chains.chain_schema
    assert doc.chain_keys is keys.chain_keys
    assert set(doc.__all__) == {
        'ChainDoc',
        'CheckReport',
        'CommandDoc',
        'FlagDoc',
        'Problem',
        'SlotDoc',
        'StepDoc',
        'chain_keys',
        'chain_schema',
        'check',
        'command_key',
        'dump_chain',
        'introspect_chain',
        'introspect_command',
        'is_command_class',
        'json_schema',
        'load_chain',
    }
