"""Tests for ``parsed/kinds.py``: kinds, declared as plain data, and each seared type's default."""

from __future__ import annotations

import enum
import uuid

import pytest
import seared

import parsed
from parsed.errors import DeclarationError
from parsed.kinds import Choice, Duration, Kind, Moment, Name, Number, Switch, Word, default_kind


class Colour(enum.Enum):
    RED = 'red'
    GREEN = 'green'
    BLUE = 'blue'


class Size(enum.Enum):
    SMALL = 1
    LARGE = 2


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


_ID = str(uuid.UUID(int=7))


class TestReading:
    # Each word to the field's wire value: what seared's `load` takes, and a tool call would send.
    @pytest.mark.parametrize(
        ('kind', 'field', 'word', 'value'),
        [
            (Word(), seared.Str(), "Vruba'a Belt 1", "Vruba'a Belt 1"),
            (Word(), seared.Path(), 'logs/today', 'logs/today'),
            (Word(), seared.UUID(), _ID, _ID),
            (Number(), seared.Int(), '40', 40),
            (Number(), seared.Int(), '-3', -3),
            (Number(), seared.Int(), '1,000', 1000),
            (Number(), seared.Int(), '-12,500,000', -12_500_000),
            (Number(), seared.Float(), '1.5', 1.5),
            (Number(), seared.Float(), '30', 30.0),
            (Number(), seared.Float(), '1e3', 1000.0),
            (Number(), seared.Float(), '.5', 0.5),
            (Number(), seared.Float(), '12,500.25', 12500.25),
            (Number(), seared.Decimal(), '1,234.50', '1234.50'),
            (Switch(), seared.Bool(), 'true', True),
            (Switch(), seared.Bool(), 'False', False),
            (Choice(), seared.Enum(enum=Colour), 'green', 'green'),
            (Choice(), seared.Enum(enum=Colour), 'GREEN', 'green'),
            (Choice(), seared.Enum(enum=Size), '2', 2),
            (Duration(), seared.TimeDelta(), '90s', 90.0),
            (Duration(), seared.TimeDelta(), '10m', 600.0),
            (Duration(), seared.TimeDelta(), '2h', 7200.0),
            (Duration(), seared.TimeDelta(), '1h30m', 5400.0),
            (Duration(), seared.TimeDelta(), '1.5H', 5400.0),
            (Duration(), seared.TimeDelta(), '0s', 0.0),
            (Moment(), seared.Date(), '2026-10-21', '2026-10-21'),
            (Moment(), seared.Time(), '14:30', '14:30'),
            (Moment(), seared.DateTime(), '2026-10-21T14:30', '2026-10-21T14:30'),
            (Name('fleet'), seared.Str(), 'Prospector', 'Prospector'),
        ],
    )
    def test_a_word_to_its_wire_value(self, kind, field, word, value):
        found = kind.read(word, field)
        assert found == value
        assert type(found) is type(value)

    @pytest.mark.parametrize(
        ('kind', 'field', 'word', 'says'),
        [
            (Word(), seared.UUID(), 'nope', r"'nope' is not a UUID"),
            (Number(), seared.Int(), '4.0', r"'4.0' is not a whole number"),
            (Number(), seared.Int(), '1,00', r"'1,00' is not a whole number"),
            (Number(), seared.Int(), '1,0000', r"'1,0000' is not a whole number"),
            (Number(), seared.Int(), '', r"'' is not a whole number"),
            (Number(), seared.Float(), 'inf', r"'inf' is not a number"),
            (Number(), seared.Float(), 'nan', r"'nan' is not a number"),
            (Number(), seared.Float(), '1,5', r"'1,5' is not a number"),
            (Number(), seared.Decimal(), 'ten', r"'ten' is not a number"),
            (Switch(), seared.Bool(), 'yes', r"'yes' is not true or false"),
            (Choice(), seared.Enum(enum=Colour), 'teal', r"'teal' is not one of red, green or blue"),
            (Duration(), seared.TimeDelta(), '90', r"'90' is not a span of time: say 90s, 10m, 2h or 1h30m"),
            (Duration(), seared.TimeDelta(), '30m1h', r'is not a span of time'),
            (Duration(), seared.TimeDelta(), '', r'is not a span of time'),
            (Moment(), seared.Date(), 'tomorrow', r"'tomorrow' is not a date: say 2026-10-21"),
            (Moment(), seared.Time(), '25:00', r"'25:00' is not a time: say 14:30"),
            (Moment(), seared.DateTime(), 'now', r"'now' is not a date and time: say 2026-10-21T14:30"),
        ],
    )
    def test_a_word_it_can_t_read_says_what_one_should_be(self, kind, field, word, says):
        with pytest.raises(ValueError, match=says):
            kind.read(word, field)

    def test_the_base_reads_a_word_as_written(self):
        assert Kind().read('as typed', seared.Str()) == 'as typed'


def test_every_kind_is_a_kind():
    for kind in (Word(), Number(), Switch(), Choice(), Duration(), Moment(), Name('fleet')):
        assert isinstance(kind, Kind)


def test_exported():
    assert parsed.Kind is Kind
    assert parsed.Name is Name
    assert parsed.kinds.Word is Word
