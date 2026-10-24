"""Tests for ``parsed/command.py``: ``Command``, its constants, and ``declaration``."""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import ClassVar

import _support_farlandia as farlandia
import _support_rio as rio
import _support_service as service
import pytest
import seared

import parsed
from parsed.command import Command, Declaration, declaration, is_chain_base
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
        assert dict(Command.SHORTS) == {}
        assert Command.EXAMPLES == ()
        assert Command.STEPS is False
        assert Command.MOVES is False

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
            examples=(),
            chain=None,
            moves=False,
            kinds=MappingProxyType({}),
            aliases=MappingProxyType({}),
            shorts=MappingProxyType({}),
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


class TestShorts:
    def test_merged_along_the_mro_by_field(self):
        assert dict(declaration(service.Run).shorts) == {'config': 'c'}  # from its base
        assert dict(declaration(service.ServiceCommand).shorts) == {'config': 'c'}

    def test_a_subclass_s_wins(self):
        @parsed.parsed
        class Loud(service.ServiceCommand):
            PHRASE = 'loud'
            SHORTS: ClassVar[dict[str, str]] = {'config': 'C'}

        assert dict(declaration(Loud).shorts) == {'config': 'C'}

    def test_a_base_s_for_a_field_said_by_a_slot_goes_unused(self):
        @parsed.parsed
        class Show(service.ServiceCommand):
            PHRASE = 'show {config}'

        assert dict(declaration(Show).shorts) == {}

    def test_none_unless_given(self):
        assert dict(declaration(farlandia.FleetMine).shorts) == {}

    @pytest.mark.parametrize(
        ('shorts', 'message'),
        [
            (['c'], r"Declared\.SHORTS = \['c'\]: a mapping of field names to short flags"),
            ({'a config': 'c'}, r"Declared\.SHORTS: 'a config' is not a field name"),
            ({'loud': 'cc'}, r"Declared\.SHORTS\['loud'\] = 'cc': a short flag is one letter, such as 'c' for -c"),
            ({'loud': '3'}, r"SHORTS\['loud'\] = '3': a short flag is one letter"),
            ({'loud': 'é'}, r"SHORTS\['loud'\] = 'é': a short flag is one letter"),
            ({'loud': 'h'}, r"Declared\.SHORTS\['loud'\]: -h is --help's, on every command"),
            ({'quiet': 'q'}, r"Declared\.SHORTS: 'quiet' is no field of Declared"),
            ({'who': 'w'}, r'Declared\.SHORTS: who is said by a slot of its phrase, so it has no flag for -w'),
            ({'loud': 'l', 'soft': 'l'}, r'Declared\.SHORTS: loud and soft are both -l'),
        ],
    )
    def test_refused(self, shorts, message):
        cls = _declared(
            PHRASE='hail {who}',
            SHORTS=shorts,
            __annotations__={'who': str, 'loud': bool, 'soft': bool},
            who=parsed.Str(required=True),
            loud=parsed.Bool(default=False),
            soft=parsed.Bool(default=False),
        )
        with pytest.raises(DeclarationError, match=message):
            declaration(cls)


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
            ({'EXAMPLES': 'go'}, r"Declared\.EXAMPLES = 'go': a tuple of lines; one alone needs a trailing comma"),
            ({'EXAMPLES': ('go', ' ')}, r'Declared\.EXAMPLES = .*: a tuple of lines, each a string of words'),
            ({'EXAMPLES': 3}, r'Declared\.EXAMPLES = 3: a tuple of lines, each a string of words'),
            ({'EXAMPLES': ('go',), 'PHRASE': None}, r'Declared has EXAMPLES but no PHRASE: a base says nothing'),
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


class TestExamples:
    def test_a_command_s_lines_kept(self):
        assert declaration(farlandia.Log).examples == ('log', 'log 40')

    def test_a_list_kept_as_a_tuple(self):
        assert declaration(_declared(EXAMPLES=['go'])).examples == ('go',)

    def test_inherited_as_any_constant_is(self):
        # Lines are read by `parsed check`, not here, as a declaration has no tree: it finds these saying Log.
        @parsed.parsed
        class Twin(farlandia.Log):
            PHRASE = 'tail {n}'

        assert declaration(Twin).examples == ('log', 'log 40')


class TestCanWait:
    @pytest.mark.parametrize(
        ('cls', 'waits'),
        [
            (farlandia.FleetsShow, True),  # a read with a REPLY
            (farlandia.Log, False),  # a read with no REPLY
            (farlandia.FleetMine, False),  # a write
            (farlandia.FleetCommand, False),  # a base
        ],
    )
    def test_a_read_with_a_reply(self, cls, waits):
        assert declaration(cls).can_wait is waits


class TestSteps:
    @pytest.mark.parametrize(
        ('cls', 'chain'),
        [
            (farlandia.FleetMine, farlandia.FleetCommand),  # beneath the base that declares them
            (farlandia.FleetJumpNearest, farlandia.FleetCommand),
            (farlandia.FleetRetreat, None),  # a setting, which says it isn't one
            (farlandia.FleetCommand, None),  # the base itself
            (farlandia.Log, None),
        ],
    )
    def test_a_step_s_chain(self, cls, chain):
        assert declaration(cls).chain is chain

    def test_a_chain_s_base(self):
        assert is_chain_base(farlandia.FleetCommand)
        assert not is_chain_base(farlandia.FleetMine)
        assert not is_chain_base(farlandia.Log)
        assert not is_chain_base('fleet')

    def test_steps_declared_on_a_command_are_refused(self):
        with pytest.raises(
            DeclarationError, match=r"Declared declares STEPS = True on a command: it goes on a chain's"
        ):
            declaration(_declared(STEPS=True))

    def test_or_inherited_from_one(self):
        @parsed.parsed
        class Ordered(parsed.Command):
            PHRASE = 'order'
            STEPS = True

        @parsed.parsed
        class Reordered(Ordered):
            PHRASE = 'reorder'

        with pytest.raises(DeclarationError, match=r'Reordered, through .*Ordered, declares STEPS = True on a command'):
            declaration(Reordered)

    def test_steps_true_or_false(self):
        with pytest.raises(DeclarationError, match=r"Declared\.STEPS = 'yes': True or False"):
            declaration(_declared(STEPS='yes'))


class TestMoves:
    @pytest.mark.parametrize(
        ('cls', 'moves'),
        [
            (farlandia.FleetJump, 'system'),  # to where a field of its own says
            (farlandia.FleetDock, 'station'),
            (farlandia.FleetJumpNearest, True),  # to somewhere the line doesn't say
            (farlandia.FleetMine, False),  # nowhere
            (farlandia.Log, False),
        ],
    )
    def test_where_a_step_takes_its_chain(self, cls, moves):
        assert declaration(cls).moves == moves

    @pytest.mark.parametrize(
        ('constants', 'message'),
        [
            ({'MOVES': 'to'}, r'Declared\.MOVES says where a step takes its chain, and Declared is no step'),
            ({'MOVES': True}, r'and Declared is no step: declare STEPS on its chain'),
        ],
    )
    def test_only_a_step_moves(self, constants, message):
        with pytest.raises(DeclarationError, match=message):
            declaration(_declared(**constants))

    @pytest.mark.parametrize(
        ('moves', 'message'),
        [
            ('nowhere', r"Ordered\.MOVES = 'nowhere' names no field of .*Ordered$"),
            ('fleet', r"MOVES = 'fleet' names a field of FleetCommand's, which every step shares: name the field"),
            ('via', r"MOVES = 'via': via holds several values, and a chain is in one place"),
            (3, r"MOVES = 3: the field that says where the step takes its chain \('to'\), True for somewhere"),
        ],
    )
    def test_a_field_of_its_own_of_one_value(self, moves, message):
        @parsed.parsed
        class Ordered(farlandia.FleetCommand):
            PHRASE = 'fleet {fleet} go {to}'
            MOVES = moves

            to: str = parsed.Str(required=True)
            via: list[str] = parsed.Str(many=True, default_factory=list)

        with pytest.raises(DeclarationError, match=message):
            declaration(Ordered)

    def test_a_scope_that_follows_a_chain_is_on_a_step(self):
        @parsed.parsed
        class Docked(parsed.Command):
            PHRASE = 'docked {fleet} {station}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'station': parsed.Name('station', scope='fleet', follows=True)}

            fleet: str = parsed.Str(required=True)
            station: str = parsed.Str(required=True)

        with pytest.raises(
            DeclarationError, match=r"Docked: 'station' follows its scope along a chain, and .*Docked is no step"
        ):
            declaration(Docked)

    def test_and_its_scope_is_a_field_the_chain_shares(self):
        @parsed.parsed
        class Unloaded(farlandia.FleetCommand):
            PHRASE = 'fleet {fleet} unload {good} at {station}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'good': parsed.Name('good', scope='station', follows=True)}

            good: str = parsed.Str(required=True)
            station: str = parsed.Str(required=True)

        with pytest.raises(
            DeclarationError,
            match=r"'good' follows its scope along a chain, so its scope is a field the chain shares, which 'station'"
            r" isn't: FleetCommand's are fleet",
        ):
            declaration(Unloaded)


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
        assert declaration(farlandia.FleetDock).field_kinds['station'] == parsed.Name(
            'station', scope='fleet', follows=True
        )
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

    def test_a_keyed_field_reads_by_pairs(self):
        @parsed.parsed
        class Set(Command):
            PHRASE = 'set'

            values: dict[str, str] = parsed.Str(keyed=True, default_factory=dict)

        with pytest.raises(
            DeclarationError, match=r'Set\.values is keyed, so its words are pairs: give it parsed\.kinds'
        ):
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


class TestForms:
    # What a kind's field and phrase must be for it: pairs and literal words.
    def test_pairs_said_as_the_rest_of_the_line(self):
        @parsed.parsed
        class Run(Command):
            PHRASE = 'run {routine} {variables**}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'variables': parsed.kinds.Pairs('variable', scope='routine')}

            routine: str = parsed.Str(required=True)
            variables: dict[str, str] = parsed.Str(keyed=True, default_factory=dict)

        assert declaration(Run).field_kinds['variables'] == parsed.kinds.Pairs('variable', scope='routine')

    def test_pairs_for_a_field_that_isn_t_keyed(self):
        @parsed.parsed
        class Run(Command):
            PHRASE = 'run {variables**}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'variables': parsed.kinds.Pairs('variable')}

            variables: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r"Run: 'variables' is read as Pairs, but variables is not keyed"):
            declaration(Run)

    def test_a_keyed_field_read_another_way(self):
        @parsed.parsed
        class Run(Command):
            PHRASE = 'run {variables**}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'variables': parsed.Name('variable')}

            variables: dict[str, str] = parsed.Str(keyed=True, default_factory=dict)

        with pytest.raises(DeclarationError, match=r'Run\.variables is keyed, so its words are pairs'):
            declaration(Run)

    @pytest.mark.parametrize('phrase', ['run', 'run {variables}'])
    def test_pairs_anywhere_but_the_rest_of_the_line(self, phrase):
        @parsed.parsed
        class Run(Command):
            PHRASE = phrase
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'variables': parsed.kinds.Pairs('variable')}

            variables: dict[str, str] = parsed.Str(keyed=True, default_factory=dict)

        with pytest.raises(DeclarationError, match=r'PHRASE says it as the rest of the line: \{variables\*\*\}'):
            declaration(Run)

    def test_a_literal_none_wants_a_nullable_field(self):
        @parsed.parsed
        class Retreat(Command):
            PHRASE = 'retreat {share}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'share': parsed.kinds.Number(words={'off': None})}

            share: float | None = parsed.Float(required=True)

        with pytest.raises(DeclarationError, match=r"'share' reads 'off' as None, which seared drops unless share is"):
            declaration(Retreat)

    def test_a_literal_none_on_a_nullable_field_is_fine(self):
        @parsed.parsed
        class Retreat(Command):
            PHRASE = 'retreat {share}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'share': parsed.kinds.Number(words={'off': None})}

            share: float | None = parsed.Float(required=True, nullable=True)

        assert declaration(Retreat).field_kinds['share'].words == {'off': None}


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

    def test_an_alias_s_scope_too(self):
        class Base(Command):
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'detachment': parsed.Name('detachment', scope='system')}
            ALIASES: ClassVar[dict[str, str]] = {'detachment': 'fleet'}

        @parsed.parsed
        class Mine(Base):
            PHRASE = 'fleet {fleet} mine'
            EXTRA_PHRASES = ('detachment {detachment} mine',)

            fleet: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r"'detachment' is read as a detachment scoped by 'system'"):
            declaration(Mine)

    def test_scopes_that_go_round_are_refused(self):
        @parsed.parsed
        class Swap(Command):
            PHRASE = 'swap {a} {b}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {
                'a': parsed.Name('x', scope='b'),
                'b': parsed.Name('y', scope='a'),
            }

            a: str = parsed.Str(required=True)
            b: str = parsed.Str(required=True)

        with pytest.raises(DeclarationError, match=r'Swap: its scopes go round, a by b by a: a scope is read before'):
            declaration(Swap)

    def test_a_chain_of_scopes_is_fine(self):
        @parsed.parsed
        class Dock(Command):
            PHRASE = 'dock {fleet} {station} {berth}'
            KINDS: ClassVar[dict[str, parsed.Kind]] = {
                'station': parsed.Name('station', scope='fleet'),
                'berth': parsed.Name('berth', scope='station'),
            }

            fleet: str = parsed.Str(required=True)
            station: str = parsed.Str(required=True)
            berth: str = parsed.Str(required=True)

        assert declaration(Dock).field_kinds['berth'].scope == 'station'

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
