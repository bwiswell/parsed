"""Tests for ``parsed/_phrase/_binding.py``: how a command's phrases bind to its fields.

The binding runs inside ``declaration``, so most of these declare a command and read its declaration.
"""

from __future__ import annotations

from typing import ClassVar

import _support_farlandia as farlandia
import _support_rio as rio
import pytest

import parsed
from parsed._phrase import Bound, Place
from parsed.command import Command, declaration
from parsed.errors import DeclarationError


def _places(cls: type[Command], at: int = 0) -> list[tuple[str, str]]:
    return [(place.slot, place.field) for place in declaration(cls).phrases[at].places]


class TestPhrase:
    def test_each_slot_fills_the_field_it_names(self):
        found = declaration(farlandia.FleetBuyShip).phrases[0]
        assert [(p.slot, p.field, p.required) for p in found.places] == [
            ('fleet', 'fleet', True),
            ('hull', 'hull', True),
        ]
        assert not found.renames
        assert found.left_out == ()

    def test_every_other_field_is_a_flag(self):
        assert declaration(farlandia.FleetMine).flags == ('for_',)
        assert declaration(rio.HandheldConnect).flags == ('host', 'port', 'label')
        assert declaration(farlandia.FleetsShow).flags == ()

    def test_a_field_that_may_be_left_out_makes_an_optional_slot(self):
        (place,) = declaration(farlandia.Log).phrases[0].places
        assert not place.required

    def test_a_many_field_and_the_rest_of_the_line(self):
        goods = declaration(farlandia.FleetSell).phrases[0].places[1]
        assert (goods.many, goods.rest) == (True, False)
        (message,) = declaration(farlandia.Say).phrases[0].places
        assert (message.many, message.rest) == (False, True)

    def test_a_base_binds_nothing(self):
        found = declaration(farlandia.FleetCommand)
        assert found.phrases == ()
        assert found.flags == ()

    def test_a_slot_that_names_no_field_is_refused(self):
        @parsed.parsed
        class Mine(Command):
            PHRASE = 'fleet {flet} mine'

            fleet: str = parsed.Str(required=True)

        with pytest.raises(
            DeclarationError,
            match=r"Mine\.PHRASE 'fleet \{flet\} mine': \{flet\} names no field of .*Mine \(its fields: fleet\)",
        ):
            declaration(Mine)

    def test_a_phrase_that_doesn_t_read_names_the_class_and_the_phrase(self):
        @parsed.parsed
        class Mine(Command):
            PHRASE = 'Mine'

        with pytest.raises(DeclarationError, match=r"Mine\.PHRASE 'Mine': 'Mine' is not a word"):
            declaration(Mine)


class TestOrder:
    @pytest.mark.parametrize(
        ('field', 'why'),
        [
            (parsed.Int(default=20), 'may be left out'),
            (parsed.Str(many=True, required=True), 'takes several words'),
        ],
    )
    def test_followed_straight_by_a_slot_is_refused(self, field, why):
        @parsed.parsed
        class Show(Command):
            PHRASE = 'show {first} {second}'

            first: object = field
            second: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=rf'\{{first\}} {why}, so it is followed by a word or ends'):
            declaration(Show)

    def test_followed_by_a_word_or_last_is_fine(self):
        @parsed.parsed
        class Show(Command):
            PHRASE = 'show {first} of {second}'

            first: int = parsed.Int(default=1)
            second: list[str] = parsed.Str(many=True, required=True)

        assert _places(Show) == [('first', 'first'), ('second', 'second')]


class TestExtraPhrases:
    def test_one_that_leaves_a_slot_out_keeps_its_default(self):
        found = declaration(farlandia.FleetDock).phrases
        assert [bound.phrase.text for bound in found] == ['fleet {fleet} dock {station}', 'fleet {fleet} dock nearest']
        assert found[1].left_out == ('station',)
        assert _places(farlandia.FleetDock, 1) == [('fleet', 'fleet')]

    def test_leaving_out_a_required_slot_is_refused(self):
        @parsed.parsed
        class Dock(Command):
            PHRASE = 'dock {station}'
            EXTRA_PHRASES = ('dock nearest',)

            station: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r'leaves out \{station\}, which is required'):
            declaration(Dock)

    def test_a_flag_of_phrase_s_can_t_be_a_slot_here(self):
        @parsed.parsed
        class Mine(Command):
            PHRASE = 'mine'
            EXTRA_PHRASES = ('mine {hours}',)

            hours: float = parsed.Float(default=1.0)

        with pytest.raises(
            DeclarationError, match=r"\{hours\} is a flag in PHRASE; an extra phrase takes only PHRASE's"
        ):
            declaration(Mine)

    def test_a_slot_is_the_rest_of_the_line_in_every_phrase_or_none(self):
        @parsed.parsed
        class Say(Command):
            PHRASE = 'say {message**}'
            EXTRA_PHRASES = ('shout {message}',)

            message: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r'\{message\} is the rest of the line in PHRASE'):
            declaration(Say)

    def test_another_wording_in_another_order(self):
        @parsed.parsed
        class Move(Command):
            PHRASE = 'move {fleet} to {site}'
            EXTRA_PHRASES = ('to {site} move {fleet}',)

            fleet: str = parsed.Str(required=True)
            site: str = parsed.Str(required=True)

        assert _places(Move, 1) == [('site', 'site'), ('fleet', 'fleet')]


class TestAliases:
    def test_a_slot_by_an_alias_fills_the_field_it_gives(self):
        found = declaration(farlandia.FleetMine).phrases[1]
        assert found.places == (Place(slot='detachment', field='fleet', required=True, many=False, rest=False),)
        assert found.renames
        assert found.places[0].renamed

    def test_given_by_a_base_and_merged(self):
        assert declaration(farlandia.FleetMine).aliases == {'detachment': 'fleet'}

    def test_phrase_may_say_one(self):
        @parsed.parsed
        class Rejoin(farlandia.FleetCommand):
            PHRASE = 'detachment {detachment} rejoin'

        assert _places(Rejoin) == [('detachment', 'fleet')]
        assert declaration(Rejoin).flags == ()

    def test_bound_by_name_so_an_optional_slot_may_be_left_out(self):
        @parsed.parsed
        class Dock(farlandia.FleetCommand):
            PHRASE = 'fleet {fleet} dock {station}'
            EXTRA_PHRASES = ('fleet {fleet} dock nearest', 'detachment {detachment} dock nearest')

            station: str | None = parsed.Str(default=None)

        assert _places(Dock, 2) == [('detachment', 'fleet')]
        assert declaration(Dock).phrases[2].left_out == ('station',)

    def test_in_any_order(self):
        class Base(Command):
            ALIASES: ClassVar[dict[str, str]] = {'detachment': 'fleet'}

        @parsed.parsed
        class Transfer(Base):
            PHRASE = 'fleet {fleet} transfer {ship}'
            EXTRA_PHRASES = ('transfer {ship} from {detachment}',)

            fleet: str = parsed.Str(required=True)
            ship: str = parsed.Str(required=True)

        assert _places(Transfer, 1) == [('ship', 'ship'), ('detachment', 'fleet')]

    def test_it_reads_by_its_own_kind_or_its_field_s(self):
        class Base(Command):
            ALIASES: ClassVar[dict[str, str]] = {'detachment': 'fleet', 'squadron': 'fleet'}
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'fleet': farlandia.FLEET, 'detachment': farlandia.DETACHMENT}

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'fleet {fleet} mine'
            EXTRA_PHRASES = ('detachment {detachment} mine', 'squadron {squadron} mine')

            fleet: str = parsed.Str(required=True)

        found = declaration(Mine)
        assert found.kind_of(found.phrases[1].places[0]) == farlandia.DETACHMENT
        assert found.kind_of(found.phrases[2].places[0]) == farlandia.FLEET  # no entry of its own: the field's

    def test_a_slot_that_s_neither_a_field_nor_an_alias(self):
        @parsed.parsed
        class Mine(farlandia.FleetCommand):
            PHRASE = 'fleet {fleet} mine'
            EXTRA_PHRASES = ('squadron {squadron} mine',)

        with pytest.raises(
            DeclarationError,
            match=r'\{squadron\} names no field of .*Mine \(its fields: fleet; its ALIASES: detachment\)',
        ):
            declaration(Mine)

    def test_an_alias_to_no_field(self):
        class Base(Command):
            ALIASES: ClassVar[dict[str, str]] = {'detachment': 'flet'}

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'detachment {detachment} mine'

            fleet: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r"ALIASES gives \{detachment\} to 'flet', which is no field"):
            declaration(Mine)

    def test_an_alias_that_s_a_field_already(self):
        class Base(Command):
            ALIASES: ClassVar[dict[str, str]] = {'detachment': 'fleet'}

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'fleet {fleet} mine'

            fleet: str = parsed.Str(required=True)
            detachment: str = parsed.Str(default='')

        with pytest.raises(DeclarationError, match=r"gives 'detachment' to 'fleet', but 'detachment' is a field"):
            declaration(Mine)

    def test_two_slots_for_one_field(self):
        @parsed.parsed
        class Mine(farlandia.FleetCommand):
            PHRASE = 'fleet {fleet} mine with {detachment}'

        with pytest.raises(DeclarationError, match=r'\{fleet\} and \{detachment\} both fill fleet'):
            declaration(Mine)

    def test_an_extra_phrase_s_alias_for_a_flag(self):
        class Base(Command):
            ALIASES: ClassVar[dict[str, str]] = {'span': 'hours'}

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'mine'
            EXTRA_PHRASES = ('mine {span}',)

            hours: float = parsed.Float(default=1.0)

        with pytest.raises(DeclarationError, match=r'\{span\}, for hours, is a flag in PHRASE'):
            declaration(Mine)

    @pytest.mark.parametrize(
        ('aliases', 'says'),
        [
            (['detachment'], r'a mapping of slot names to field names'),
            ({'a b': 'fleet'}, r"'a b' is not a slot name"),
            ({'detachment': 3}, r"\['detachment'\] = 3: the name of the field it fills"),
        ],
    )
    def test_what_aliases_may_be(self, aliases, says):
        class Base(Command):
            ALIASES = aliases

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'fleet {fleet} mine'

            fleet: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=says):
            declaration(Mine)


class TestPolymorphic:
    def test_undeclared_either_way(self):
        assert declaration(farlandia.FleetDock).polymorphic is None
        assert declaration(farlandia.FleetMine).polymorphic is True

    def test_true_wants_a_slot_by_an_alias(self):
        @parsed.parsed
        class Dock(Command):
            PHRASE = 'dock {station}'
            EXTRA_PHRASES = ('dock nearest',)
            POLYMORPHIC = True

            station: str | None = parsed.Str(default=None)

        with pytest.raises(DeclarationError, match=r'Dock\.POLYMORPHIC is True, but no phrase says a slot by an alias'):
            declaration(Dock)

    def test_false_refuses_one(self):
        @parsed.parsed
        class Mine(farlandia.FleetCommand):
            PHRASE = 'fleet {fleet} mine'
            EXTRA_PHRASES = ('detachment {detachment} mine',)
            POLYMORPHIC = False

        with pytest.raises(
            DeclarationError,
            match=r"POLYMORPHIC is False, but 'detachment \{detachment\} mine' says \{fleet\} as \{detachment\}",
        ):
            declaration(Mine)


class TestOwnKinds:
    def test_an_entry_that_names_nothing_is_a_typo(self):
        @parsed.parsed
        class Mine(Command):
            PHRASE = 'fleet {fleet} mine'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'flet': parsed.Name('fleet')}

            fleet: str = parsed.Str(required=True)

        with pytest.raises(
            DeclarationError,
            match=r"Mine\.KINDS names 'flet', which is no field of .*Mine and none of its ALIASES",
        ):
            declaration(Mine)

    def test_a_base_s_entries_may_go_unused(self):
        # FleetCommand's `detachment` serves FleetMine's alias; FleetBuyShip has none, and needn't.
        assert 'detachment' in declaration(farlandia.FleetBuyShip).kinds

    def test_an_entry_for_a_flag_is_fine(self):
        @parsed.parsed
        class Mine(Command):
            PHRASE = 'mine'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'hours': parsed.kinds.Number()}

            hours: float = parsed.Float(default=1.0)

        assert declaration(Mine).flags == ('hours',)


def test_bound_is_its_phrase_and_places():
    found = declaration(farlandia.Say).phrases[0]
    assert isinstance(found, Bound)
    assert found.phrase.text == 'say {message**}'
