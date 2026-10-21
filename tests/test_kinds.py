"""Tests for ``parsed/kinds.py``: kinds, declared as plain data, and each seared type's default."""

from __future__ import annotations

import enum

import pytest
import seared

import parsed
from parsed.errors import DeclarationError
from parsed.kinds import Choice, Duration, Kind, Moment, Name, Number, Switch, Word, default_kind


class Colour(enum.Enum):
    RED = 'red'


@seared.seared
class Inner(seared.Seared):
    x: int = seared.Int(default=0)


class TestDefaults:
    @pytest.mark.parametrize(
        ('field', 'kind'),
        [
            (seared.Str(), Word()),
            (seared.Path(), Word()),
            (seared.UUID(), Word()),
            (seared.Int(), Number()),
            (seared.Float(), Number()),
            (seared.Decimal(), Number()),
            (seared.Bool(), Switch()),
            (seared.Enum(enum=Colour), Choice()),
            (seared.TimeDelta(), Duration()),
            (seared.Date(), Moment()),
            (seared.DateTime(), Moment()),
            (seared.Time(), Moment()),
            (seared.Str(many=True), Word()),
        ],
    )
    def test_each_word_form_by_seared_type(self, field, kind):
        assert default_kind(field) == kind

    @pytest.mark.parametrize(
        'field',
        [
            seared.T(Inner),
            seared.Union(variants={'inner': Inner}),
            seared.Tuple(seared.Int(), seared.Int()),
            seared.Bytes(),
            seared.Dict(),
            seared.Str(keyed=True),
        ],
    )
    def test_no_word_form(self, field):
        assert default_kind(field) is None

    def test_a_custom_field_with_no_seared_kind_has_none(self):
        class Plain(seared.Field):
            KIND = None

        assert default_kind(Plain()) is None


class TestName:
    def test_a_category_and_a_scope(self):
        found = Name('station', scope='fleet')
        assert (found.category, found.scope) == ('station', 'fleet')
        assert Name('fleet').scope is None

    def test_plain_data_compared_by_value(self):
        assert Name('fleet') == Name('fleet')
        assert Name('fleet') != Name('fleet', scope='system')
        assert len({Name('fleet'), Name('fleet')}) == 1

    @pytest.mark.parametrize('category', ['', 'a fleet', 'fleet-key', 3])
    def test_a_category_is_a_name(self, category):
        with pytest.raises(DeclarationError, match=r'a category is a name, such as fleet or station'):
            Name(category)

    @pytest.mark.parametrize('scope', ['', 'the fleet', 3])
    def test_a_scope_is_a_field_s_name(self, scope):
        with pytest.raises(DeclarationError, match=r'a scope is the name of another field'):
            Name('station', scope=scope)


def test_every_kind_is_a_kind():
    for kind in (Word(), Number(), Switch(), Choice(), Duration(), Moment(), Name('fleet')):
        assert isinstance(kind, Kind)


def test_exported():
    assert parsed.Kind is Kind
    assert parsed.Name is Name
    assert parsed.kinds.Word is Word
