"""Tests for ``parsed/_phrase/__init__.py``: the subpackage's surface."""

from parsed import _phrase
from parsed._phrase import _binding, _grammar


def test_it_gathers_both_modules():
    assert _phrase.parse is _grammar.parse
    assert _phrase.bind is _binding.bind
    assert set(_phrase.__all__) == {'Binding', 'Bound', 'Phrase', 'Place', 'Slot', 'Word', 'bind', 'parse'}
