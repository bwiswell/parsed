"""Tests for ``parsed/_walk/__init__.py``: the subpackage's surface."""

import parsed.tree
from parsed import _walk
from parsed._walk import _walker, _words


def test_it_gathers_both_modules():
    assert _walk.split is _words.split
    assert _walk.walk is _walker.walk
    assert set(_walk.__all__) == {'RESERVED', 'Arity', 'Given', 'Reading', 'SlotKind', 'Token', 'split', 'walk'}


def test_the_tree_speaks_the_walk_s_terms():
    # The tree builds what the walk reads, so the names it gives are the walk's own.
    assert parsed.tree.RESERVED is _walk.RESERVED
    assert parsed.tree.Arity is _walk.Arity
    assert parsed.tree.SlotKind is _walk.SlotKind
    assert parsed.tree.Reading is _walk.Reading
