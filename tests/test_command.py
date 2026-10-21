"""Tests for ``parsed/command.py``: ``Command``, its constants, and ``declaration``."""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import ClassVar

import _support_farlandia as farlandia
import _support_rio as rio
import pytest
import seared

import parsed
from parsed.command import Command, Declaration, declaration
from parsed.effect import Effect
from parsed.errors import DeclarationError


class TestDefaults:
    def test_every_constant_but_phrase_is_optional_and_empty(self):
        # Nothing is required to use parsed alone; a command needs a phrase.
        assert Command.PHRASE is None
        assert Command.EXTRA_PHRASES == ()
        assert Command.EFFECT is None
        assert Command.ASKS is False
        assert Command.INTERACTIVE is False
        assert Command.POLYMORPHIC is None
        assert Command.INSTEAD is None
        assert Command.REPLY is None
        assert dict(Command.KINDS) == {}

    def test_the_base_declares_nothing(self):
        found = declaration(Command)
        assert found == Declaration(
            cls=Command,
            phrase=None,
            extra_phrases=(),
            effect=None,
            asks=False,
            interactive=False,
            polymorphic=None,
            instead=None,
            reply=None,
            kinds=MappingProxyType({}),
            field_kinds=MappingProxyType({}),
            phrases=(),
            flags=(),
        )
        assert not found.is_command

    def test_exported(self):
        assert parsed.Command is Command


class TestCommandOrBase:
    def test_a_phrase_makes_a_command(self):
        found = declaration(farlandia.FleetMine)
        assert found.is_command
        assert found.phrase == 'fleet {fleet} mine'

    def test_a_class_without_a_phrase_is_a_base(self):
        assert not declaration(farlandia.FleetCommand).is_command

    def test_the_fixture_declares(self):
        for cls in (
            farlandia.FleetMine,
            farlandia.FleetBuyShip,
            farlandia.FleetsShow,
            farlandia.ShipsMakeAdd,
            farlandia.ShipFit,
            rio.HandheldConnect,
        ):
            assert declaration(cls).is_command, cls.__name__


class TestInheritance:
    def test_a_base_s_effect_reaches_the_commands_beneath_it(self):
        assert declaration(farlandia.FleetMine).effect is Effect.WRITE

    def test_a_command_overrides_its_base_s(self):
        assert declaration(farlandia.FleetBuyShip).effect is Effect.ACTION

    def test_an_effect_name_normalises_to_its_member(self):
        @parsed.parsed
        class Named(Command):
            PHRASE = 'named'
            EFFECT = 'read'

        assert declaration(Named).effect is Effect.READ

    def test_any_constant_is_inherited_from_a_base_that_declares_it(self):
        class Asking(Command):
            ASKS = True
            EFFECT = Effect.ACTION

        @parsed.parsed
        class Sell(Asking):
            PHRASE = 'sell'

        found = declaration(Sell)
        assert found.asks is True
        assert found.effect is Effect.ACTION

    def test_a_base_s_field_reaches_the_commands_beneath_it(self):
        assert [spec.attr for spec in farlandia.FleetMine.__seared_fields__] == ['fleet', 'for_']


class TestKinds:
    FLEET = parsed.Name('fleet')
    DETACHMENT = parsed.Name('detachment')
    SHIP = parsed.Name('ship')

    def test_merged_along_the_mro(self):
        class Base(Command):
            KINDS: ClassVar[dict[object, object]] = {'fleet': TestKinds.FLEET}

        class Middle(Base):
            KINDS: ClassVar[dict[object, object]] = {'detachment': TestKinds.DETACHMENT}

        @parsed.parsed
        class Leaf(Middle):
            PHRASE = 'leaf'
            KINDS: ClassVar[dict[object, object]] = {'ship': TestKinds.SHIP}

            ship: str = parsed.Str(default='')

        assert dict(declaration(Leaf).kinds) == {
            'fleet': self.FLEET,
            'detachment': self.DETACHMENT,
            'ship': self.SHIP,
        }

    def test_a_subclass_s_entry_wins(self):
        other = parsed.Name('flagship')

        class Base(Command):
            KINDS: ClassVar[dict[object, object]] = {'fleet': TestKinds.FLEET}

        @parsed.parsed
        class Leaf(Base):
            PHRASE = 'leaf'
            KINDS: ClassVar[dict[object, object]] = {'fleet': other}

            fleet: str = parsed.Str(default='')

        assert declaration(Leaf).kinds['fleet'] is other

    def test_a_sibling_and_the_base_are_untouched(self):
        class Base(Command):
            KINDS: ClassVar[dict[object, object]] = {'fleet': TestKinds.FLEET}

        @parsed.parsed
        class One(Base):
            PHRASE = 'one'
            KINDS: ClassVar[dict[object, object]] = {'ship': TestKinds.SHIP}

            ship: str = parsed.Str(default='')

        @parsed.parsed
        class Two(Base):
            PHRASE = 'two'

        assert set(declaration(One).kinds) == {'fleet', 'ship'}
        assert set(declaration(Two).kinds) == {'fleet'}
        assert dict(Base.KINDS) == {'fleet': self.FLEET}
        assert dict(Command.KINDS) == {}

    def test_read_only(self):
        class Base(Command):
            KINDS: ClassVar[dict[object, object]] = {'fleet': TestKinds.FLEET}

        @parsed.parsed
        class Leaf(Base):
            PHRASE = 'leaf'

        with pytest.raises(TypeError):
            declaration(Leaf).kinds['ship'] = self.SHIP  # ty: ignore[invalid-assignment]


class TestDecoration:
    def test_an_undecorated_command_is_refused(self):
        class Plain(Command):
            PHRASE = 'plain'

        with pytest.raises(DeclarationError, match=r'Plain has a PHRASE but is not decorated'):
            declaration(Plain)

    def test_an_undecorated_base_with_fields_is_refused_by_name(self):
        # seared would silently drop the base's fields from the command.
        class Base(Command):
            fleet: str = parsed.Str(required=True)

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'mine {fleet}'

        with pytest.raises(DeclarationError, match=r'Base declares fields but is not decorated.*from .*Mine'):
            declaration(Mine)

    def test_an_undecorated_base_without_fields_is_fine(self):
        class Writes(Command):
            EFFECT = Effect.WRITE

        @parsed.parsed
        class Mine(Writes):
            PHRASE = 'mine'

        assert declaration(Mine).effect is Effect.WRITE

    def test_a_class_that_isn_t_a_command_is_refused(self):
        @seared.seared
        class Plain(seared.Seared):
            x: int = seared.Int(default=0)

        with pytest.raises(DeclarationError, match=r'is not a command: subclass parsed\.Command'):
            declaration(Plain)

    def test_a_non_class_is_refused(self):
        with pytest.raises(DeclarationError, match='is not a command'):
            declaration('fleet mine')  # ty: ignore[invalid-argument-type]


def _declared(**constants: object) -> type[Command]:
    """A decorated command class with ``constants`` set, a phrase unless they say otherwise."""
    namespace = {'PHRASE': 'go', **constants}
    return parsed.parsed(type('Declared', (Command,), namespace))


class TestRefusals:
    @pytest.mark.parametrize(
        ('constants', 'message'),
        [
            ({'PHRASE': ''}, r"Declared\.PHRASE = '': a phrase is a string of words"),
            ({'PHRASE': 3}, r'Declared\.PHRASE = 3: a phrase is a string of words'),
            ({'EXTRA_PHRASES': 'go on'}, r"EXTRA_PHRASES = 'go on': a tuple of phrases; one alone needs a trailing"),
            ({'EXTRA_PHRASES': ('go on', '')}, r'EXTRA_PHRASES = .*: a tuple of phrases, each a string of words'),
            ({'EXTRA_PHRASES': ('go on',), 'PHRASE': None}, r'has EXTRA_PHRASES but no PHRASE'),
            ({'EFFECT': 'reed'}, r"Declared\.EFFECT = 'reed': expected one of read, write, action"),
            ({'EFFECT': 1}, r'Declared\.EFFECT must be an Effect, an effect name or None, not int'),
            ({'ASKS': 'yes'}, r"Declared\.ASKS = 'yes': True or False"),
            ({'INTERACTIVE': 1}, r'Declared\.INTERACTIVE = 1: True or False'),
            ({'POLYMORPHIC': 'yes'}, r"Declared\.POLYMORPHIC = 'yes': True, False, or left out"),
            ({'REPLY': dict}, r'Declared\.REPLY = dict: a seared class'),
            ({'KINDS': ['fleet']}, r"Declared\.KINDS = \['fleet'\]: a mapping of field names to kinds"),
            ({'KINDS': {'a fleet': object()}}, r"Declared\.KINDS: 'a fleet' is not a field name"),
        ],
    )
    def test_each_is_refused_naming_the_class_and_the_constant(self, constants, message):
        cls = _declared(**constants)
        with pytest.raises(DeclarationError, match=message):
            declaration(cls)

    def test_a_bad_base_kinds_names_the_base(self):
        class Base(Command):
            KINDS: ClassVar[dict[object, object]] = {3: object()}

        @parsed.parsed
        class Leaf(Base):
            PHRASE = 'leaf'

        with pytest.raises(DeclarationError, match=r'Base\.KINDS: 3 is not a field name'):
            declaration(Leaf)

    def test_an_undecorated_reply_is_refused(self):
        class Unready(seared.Seared):
            x: int = seared.Int(default=0)

        with pytest.raises(DeclarationError, match=r'REPLY = .*Unready: a seared class'):
            declaration(_declared(REPLY=Unready))


class TestInstead:
    def test_an_interactive_command_names_its_agent_form(self):
        found = declaration(farlandia.ShipFit)
        assert found.interactive
        assert found.instead is farlandia.ShipsMakeAdd

    def test_only_an_interactive_command_takes_one(self):
        with pytest.raises(DeclarationError, match=r'INSTEAD: it names what an agent says in place of an interactive'):
            declaration(_declared(INSTEAD=farlandia.ShipsMakeAdd))

    def test_not_itself(self):
        cls = _declared(INTERACTIVE=True)
        cls.INSTEAD = cls
        with pytest.raises(DeclarationError, match=r'INSTEAD names Declared itself'):
            declaration(cls)

    @pytest.mark.parametrize('target', [farlandia.FleetCommand, farlandia.FleetView, 'ships make'])
    def test_a_command_with_a_phrase(self, target):
        with pytest.raises(DeclarationError, match=r'INSTEAD = .*: a command class, with a PHRASE'):
            declaration(_declared(INTERACTIVE=True, INSTEAD=target))

    def test_not_another_interactive_one(self):
        with pytest.raises(DeclarationError, match=r'names ShipFit, which is interactive too'):
            declaration(_declared(INTERACTIVE=True, INSTEAD=farlandia.ShipFit))


class TestReply:
    def test_a_seared_class(self):
        assert declaration(farlandia.FleetsShow).reply is farlandia.FleetView


class TestTheCache:
    def test_read_once_and_kept_on_the_class(self):
        first = declaration(farlandia.FleetsShow)
        assert declaration(farlandia.FleetsShow) is first
        assert vars(farlandia.FleetsShow)['__parsed_declaration__'] is first

    def test_a_subclass_reads_its_own(self):
        base = declaration(farlandia.FleetMine)

        @parsed.parsed
        class Longer(farlandia.FleetMine):
            PHRASE = 'fleet {fleet} mine longer'

        assert declaration(Longer) is not base
        assert declaration(Longer).phrase == 'fleet {fleet} mine longer'


class TestARequestInherited:
    # A command can inherit a protocol's request class, so its fields and their
    # bounds are the protocol's own, not copied by hand.

    def test_its_fields_are_the_request_s(self):
        names = [spec.attr for spec in rio.HandheldConnect.__seared_fields__]
        assert names == ['source', 'reader_id', 'host', 'port', 'label']
        assert issubclass(rio.HandheldConnect, rio.HandheldEndpoint)

    def test_it_loads_and_keeps_the_request_s_bounds(self):
        found = rio.HandheldConnect.load({'source': 's1', 'reader_id': 'r1', 'host': 'h'}, unknown='raise')
        assert found.port == 5084
        with pytest.raises(seared.ValidationError, match=r'port: must be <= 65535'):
            rio.HandheldConnect.load({'source': 's1', 'reader_id': 'r1', 'host': 'h', 'port': 70000})

    def test_its_constants_are_not_fields(self):
        with pytest.raises(seared.ValidationError, match=r'PHRASE: unknown key'):
            rio.HandheldConnect.load({'source': 's1', 'reader_id': 'r1', 'host': 'h', 'PHRASE': 'x'}, unknown='raise')

    def test_it_declares(self):
        found = declaration(rio.HandheldConnect)
        assert found.is_command
        assert found.effect is Effect.WRITE


class TestFieldKinds:
    def test_every_field_has_one_its_entry_or_its_type_s(self):
        assert dict(declaration(farlandia.FleetMine).field_kinds) == {
            'fleet': parsed.Name('fleet'),  # from its base's KINDS
            'for_': parsed.kinds.Duration(),  # a TimeDelta's default
        }
        assert declaration(farlandia.FleetDock).field_kinds['station'] == parsed.Name('station', scope='fleet')
        assert declaration(farlandia.Log).field_kinds['n'] == parsed.kinds.Number()
        assert declaration(farlandia.Say).field_kinds['message'] == parsed.kinds.Word()

    def test_a_slot_reads_by_its_field_s_kind_or_its_own_when_renamed(self):
        found = declaration(farlandia.FleetMine)
        (fleet,) = found.phrases[0].places
        (detachment,) = found.phrases[1].places
        assert found.kind_of(fleet) == parsed.Name('fleet')
        assert found.kind_of(detachment) == parsed.Name('detachment')

    def test_a_base_has_none(self):
        assert dict(declaration(farlandia.FleetCommand).field_kinds) == {}

    def test_a_field_with_no_word_form_is_refused(self):
        @seared.seared
        class Inner(seared.Seared):
            x: int = seared.Int(default=0)

        @parsed.parsed
        class Configure(Command):
            PHRASE = 'configure'

            settings: Inner | None = parsed.T(Inner, default=None)

        with pytest.raises(DeclarationError, match=r'Configure\.settings is a T field, which has no word form'):
            declaration(Configure)

    def test_given_a_kind_it_s_fine(self):
        @seared.seared
        class Inner(seared.Seared):
            x: int = seared.Int(default=0)

        @parsed.parsed
        class Configure(Command):
            PHRASE = 'configure'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'settings': parsed.Name('preset')}

            settings: Inner | None = parsed.T(Inner, default=None)

        assert declaration(Configure).field_kinds['settings'] == parsed.Name('preset')

    def test_a_keyed_field_has_no_word_form_yet(self):
        @parsed.parsed
        class Set(Command):
            PHRASE = 'set'

            values: dict[str, str] = parsed.Str(keyed=True, default_factory=dict)

        with pytest.raises(DeclarationError, match=r'Set\.values is a Str field, which has no word form'):
            declaration(Set)

    def test_an_entry_that_isn_t_a_kind_is_refused_naming_where_it_s_declared(self):
        class Base(Command):
            KINDS: ClassVar[dict[str, object]] = {'fleet': 'fleet'}

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'mine {fleet}'

            fleet: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r"Base\.KINDS\['fleet'\] = 'fleet': a kind, such as parsed\.Name"):
            declaration(Mine)


class TestScopes:
    def test_a_scope_names_another_field(self):
        assert declaration(farlandia.FleetDock).field_kinds['station'].scope == 'fleet'

    @pytest.mark.parametrize('scope', ['system', 'station'])
    def test_no_other_field_is_refused(self, scope):
        @parsed.parsed
        class Dock(Command):
            PHRASE = 'dock {fleet} {station}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'station': parsed.Name('station', scope=scope)}

            fleet: str = parsed.Str(required=True)
            station: str = parsed.Str(required=True)

        with pytest.raises(
            DeclarationError, match=rf"'station' is read as a station scoped by '{scope}', which is no other field"
        ):
            declaration(Dock)

    def test_a_renamed_slot_s_scope_too(self):
        class Base(Command):
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'detachment': parsed.Name('detachment', scope='system')}

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'fleet {fleet} mine'
            EXTRA_PHRASES = ('detachment {detachment} mine',)

            fleet: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r"'detachment' is read as a detachment scoped by 'system'"):
            declaration(Mine)

    def test_a_base_s_unused_entry_isn_t_held_to_it(self):
        class Base(Command):
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'station': parsed.Name('station', scope='system')}

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'mine {fleet}'

            fleet: str = parsed.Str(required=True)

        assert 'station' not in declaration(Mine).field_kinds


class TestAnnotations:
    # seared takes only a field with an annotation, and drops the rest without a word.

    @pytest.mark.parametrize(
        ('field', 'hint'),
        [
            (parsed.Float(default=1.0), 'float'),
            (parsed.Int(required=True), 'int'),
            (parsed.Str(default=None), 'str | None'),
            (parsed.Str(many=True, default_factory=list), 'list[str]'),
            (parsed.TimeDelta(default=None), 'timedelta | None'),
            (parsed.Dict(default_factory=dict), '<its type>'),
        ],
    )
    def test_a_field_without_one_is_refused_with_an_example(self, field, hint):
        cls = parsed.parsed(type('Mine', (Command,), {'__qualname__': 'Mine', 'PHRASE': 'mine', 'extra': field}))
        said = (
            r'Mine\.extra has no annotation, so seared leaves it out: add an annotation, such as '
            rf'extra: {re.escape(hint)} = …'
        )
        with pytest.raises(DeclarationError, match=said):
            declaration(cls)

    def test_a_slot_s_field_too_before_its_phrase_is_bound(self):
        @parsed.parsed
        class Mine(Command):
            PHRASE = 'mine {fleet}'

            fleet = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r'Mine\.fleet has no annotation'):
            declaration(Mine)

    def test_on_a_decorated_base_it_names_the_base(self):
        @parsed.parsed
        class Base(Command):
            fleet = parsed.Str(required=True)

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'mine'

        with pytest.raises(DeclarationError, match=r'Base\.fleet has no annotation, so seared leaves it out of .*Mine'):
            declaration(Mine)

    def test_on_an_inherited_request_class(self):
        @seared.seared
        class Request(seared.Seared):
            source: str = seared.Str(required=True)
            port = seared.Int(default=5084)

        @parsed.parsed
        class Connect(Command, Request):
            PHRASE = 'connect {source}'

        with pytest.raises(
            DeclarationError, match=r'Request\.port has no annotation, so seared leaves it out of .*Connect'
        ):
            declaration(Connect)

    def test_annotated_fields_are_fine(self):
        assert declaration(farlandia.FleetMine).flags == ('for_',)
