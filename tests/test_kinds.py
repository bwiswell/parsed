"""Tests for ``parsed/kinds.py``: kinds, declared as plain data, and each seared type's default."""

from __future__ import annotations

import enum
import uuid

import pytest
import seared

import parsed
from parsed.errors import DeclarationError
from parsed.kinds import (
    NOT_LITERAL,
    Choice,
    Duration,
    Kind,
    Moment,
    Name,
    Named,
    Number,
    Pairs,
    Switch,
    Word,
    default_kind,
    span,
    spell_span,
)


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

    def test_a_scope_that_follows_its_chain(self):
        found = Name('station', scope='fleet', follows=True)
        assert found.follows
        assert not Name('station', scope='fleet').follows
        assert found != Name('station', scope='fleet')  # it reads differently in a chain

    def test_follows_is_keyword_only(self):
        with pytest.raises(TypeError):
            Name('station', 'fleet', True)  # noqa: FBT003  # ty: ignore[too-many-positional-arguments] -- refused

    def test_follows_needs_a_scope(self):
        with pytest.raises(DeclarationError, match=r"follows=True\): it follows its scope's place along a chain, so"):
            Name('station', follows=True)

    def test_follows_true_or_false(self):
        with pytest.raises(DeclarationError, match=r"Name\('station', follows='yes'\): True or False"):
            Name('station', scope='fleet', follows='yes')  # ty: ignore[invalid-argument-type] -- what's refused


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


class TestLiteralWords:
    def test_read_before_the_form_case_aside(self):
        share = Number(suffix='%', words={'off': None, 'half': 50.0})
        assert share.read('off', seared.Float()) is None
        assert share.read('OFF', seared.Float()) is None
        assert share.read('half', seared.Float()) == 50.0
        assert share.read('30%', seared.Float()) == 30.0

    def test_a_quoted_word_is_never_one(self):
        with pytest.raises(ValueError, match=r"'off' is not a number"):
            Number(words={'off': None}).read('off', seared.Float(), quoted=True)

    def test_literal_gives_the_value_or_not_one(self):
        kind = Word(words={'nearest': None})
        assert kind.literal('Nearest') is None
        assert kind.literal('vesta') is NOT_LITERAL

    @pytest.mark.parametrize('word', ['Off', 'off now', '', '-off', 3])
    def test_a_literal_is_one_lowercase_word(self, word):
        with pytest.raises(DeclarationError, match=r'Number\(words=…\): .* is no literal word'):
            Number(words={word: None})

    def test_kept_where_they_can_t_change(self):
        given = {'off': None}
        kind = Number(words=given)
        given['on'] = 1
        assert dict(kind.words) == {'off': None}
        with pytest.raises(TypeError):
            kind.words['on'] = 1  # ty: ignore[invalid-assignment]

    def test_compared_by_value_and_hashed_without_them(self):
        assert Number(words={'off': None}) == Number(words={'off': None})
        assert Number(words={'off': None}) != Number()
        assert hash(Number(words={'off': None})) == hash(Number())


class TestSuffix:
    def test_it_may_follow_the_number(self):
        assert Number(suffix='%').read('30%', seared.Float()) == 30.0
        assert Number(suffix='%').read('1,000%', seared.Int()) == 1000
        assert Number(suffix='%').read('30', seared.Float()) == 30.0

    def test_only_its_own(self):
        with pytest.raises(ValueError, match=r"'30x' is not a number"):
            Number(suffix='%').read('30x', seared.Float())


class TestNamed:
    def test_name_and_pairs_are_named(self):
        assert isinstance(Name('fleet'), Named)
        assert isinstance(Pairs('variable', scope='routine'), Named)
        assert Pairs('variable', scope='routine').scope == 'routine'

    def test_pairs_check_their_category_and_scope_as_a_name_does(self):
        with pytest.raises(DeclarationError, match=r'Pairs\(\'a b\'\): a category is a name'):
            Pairs('a b')
        with pytest.raises(DeclarationError, match=r"Pairs\('variable', scope='the routine'\): a scope is the name"):
            Pairs('variable', scope='the routine')

    def test_a_name_s_form_is_the_word_as_typed(self):
        assert Name('fleet').form('Prospector', seared.Str()) == 'Prospector'


class TestOffers:
    # What completion offers for a kind besides its literal words.
    @pytest.mark.parametrize(
        ('kind', 'field', 'offers'),
        [
            (Choice(), seared.Enum(enum=Colour), ('red', 'green', 'blue')),
            (Switch(), seared.Bool(), ('true', 'false')),
            (Duration(), seared.TimeDelta(), ('10m', '30m', '1h')),
            (Word(), seared.Str(), ()),
            (Number(), seared.Int(), ()),
            (Moment(), seared.Date(), ()),
            (Name('fleet'), seared.Str(), ()),  # a name's are its resolver's
        ],
    )
    def test_each_kind_s_own(self, kind, field, offers):
        assert kind.offers(field) == offers


class TestDescribing:
    # What a field's words are, for help and pages: the kind's own, then its literal words.
    @pytest.mark.parametrize(
        ('kind', 'field', 'said'),
        [
            (Word(), seared.Str(), 'a word'),
            (Word(), seared.Path(), 'a path'),
            (Word(), seared.UUID(), 'a UUID'),
            (Number(), seared.Int(), 'a whole number'),
            (Number(), seared.Float(), 'a number'),
            (Number(suffix='%'), seared.Float(), 'a number, % after it or not'),
            (Switch(), seared.Bool(), 'true or false'),
            (Choice(), seared.Enum(enum=Colour), 'one of red, green or blue'),
            (Duration(), seared.TimeDelta(), 'a span of time, such as 90s, 10m or 1h30m'),
            (Moment(), seared.Date(), 'a date, such as 2026-10-21'),
            (Moment(), seared.Time(), 'a time, such as 14:30'),
            (Moment(), seared.DateTime(), 'a date and time, such as 2026-10-21T14:30'),
            (Name('station'), seared.Str(), 'a station'),
            (Name('station', scope='fleet'), seared.Str(), 'a station, within its fleet'),
            (Pairs('variable', scope='routine'), seared.Str(keyed=True), 'variable and value pairs'),
        ],
    )
    def test_each_kind_s_own(self, kind, field, said):
        assert kind.describe(field) == said

    def test_then_its_literal_words(self):
        share = Number(suffix='%', words={'off': None})
        assert share.describe(seared.Float(nullable=True)) == 'a number, % after it or not, or off'
        assert Word(words={'here': 'h', 'there': 't'}).describe(seared.Str()) == 'a word, or here or there'

    def test_a_kind_of_an_app_s_own_says_what_it_is(self):
        class Hex(Kind):
            def what(self, field):
                return 'a hex number, such as ff'

        assert Hex(words={'none': None}).describe(seared.Str()) == 'a hex number, such as ff, or none'


class TestWriting:
    # A wire value back to its words, which read to it again.
    @pytest.mark.parametrize(
        ('kind', 'field', 'value', 'words'),
        [
            (Word(), seared.Str(), "Vruba'a Belt 1", ["Vruba'a Belt 1"]),
            (Number(), seared.Int(), 1000, ['1000']),
            (Number(), seared.Float(), 30.0, ['30']),
            (Number(), seared.Float(), 0.1, ['0.1']),
            (Number(), seared.Float(), 1e20, ['1e+20']),
            (Number(), seared.Decimal(), '1234.50', ['1234.50']),
            (Number(suffix='%', words={'off': None}), seared.Float(nullable=True), None, ['off']),
            (Switch(), seared.Bool(), False, ['false']),
            (Choice(), seared.Enum(enum=Colour), 'green', ['green']),
            (Duration(), seared.TimeDelta(), 5400.0, ['1h30m']),
            (Duration(), seared.TimeDelta(), 90.5, ['1m30.5s']),
            (Duration(), seared.TimeDelta(), 0.0, ['0s']),
            (Duration(), seared.TimeDelta(), 7200, ['2h']),
            (Moment(), seared.Date(), '2026-10-21', ['2026-10-21']),
            (Name('fleet'), seared.Str(), 'f1', ['f1']),
            (
                Pairs('variable'),
                seared.Str(keyed=True),
                {'ore': 'iron', 'home': 'vesta'},
                ['ore', 'iron', 'home', 'vesta'],
            ),
        ],
    )
    def test_a_value_s_words(self, kind, field, value, words):
        assert kind.write(value, field) == words
        if not isinstance(kind, Pairs):
            assert kind.read(words[0], field) == value

    def test_a_literal_by_its_value_and_type(self):
        on = Number(words={'on': 1})
        assert on.write(1, seared.Int()) == ['on']
        assert on.write(value=True, field=seared.Int()) == ['True']  # `True == 1`, but `on` reads as `1`


def test_every_kind_is_a_kind():
    for kind in (Word(), Number(), Switch(), Choice(), Duration(), Moment(), Name('fleet')):
        assert isinstance(kind, Kind)


def test_exported():
    assert parsed.Kind is Kind
    assert parsed.Name is Name
    assert parsed.kinds.Word is Word


@pytest.mark.parametrize(
    ('seconds', 'said'),
    [(0.0, '0s'), (0.05, '0.05s'), (90.0, '1m30s'), (120.0, '2m'), (5400.0, '1h30m'), (3600.0, '1h')],
)
def test_a_span_spelled_as_it_reads(seconds, said):
    assert spell_span(seconds) == said
    assert span(said) == seconds
