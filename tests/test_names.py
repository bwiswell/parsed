"""Tests for ``parsed/names.py``: what an app gives for a category of its names."""

import _support_farlandia as farlandia

import parsed
from parsed.names import PairsResolver, Resolver


def test_exported():
    assert parsed.Resolver is Resolver


def test_a_resolver_is_any_object_with_its_three_methods():
    # A protocol, so an app's own class needs no base of parsed's: the fixture's table is one.
    table = farlandia.NAMES['station']
    assert not isinstance(table, parsed.Parsed)
    for method in ('lookup', 'suggest', 'options'):
        assert callable(getattr(table, method))
        assert method in vars(Resolver)


def test_the_fixture_s_table_reads_as_an_app_s_would():
    stations = farlandia.NAMES['station']
    assert stations.lookup('VESTA', 'f1') == 'vesta'
    assert stations.lookup('vesta', 'f2') is None  # out of the second fleet's reach
    assert stations.lookup('ceres', None) == 'ceres'  # no scope: across them all
    assert stations.options('f2') == ['Ceres']
    assert stations.suggest('Vsta', 'f1') == ['Vesta']


def test_a_pairs_resolver_is_a_resolver_that_gives_values():
    variables = farlandia.NAMES['variable']
    assert 'values' in vars(PairsResolver)
    assert Resolver in PairsResolver.__mro__
    assert variables.lookup('home', 'mining') == 'home'
    assert variables.values('ore', 'mining') is farlandia.GOODS
    assert variables.values('route', 'patrol') is None  # its values read as typed
