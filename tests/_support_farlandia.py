"""Commands shaped like farlandia's hardest, written fresh: parsed's tests depend on no game.

It grows with each release that needs more of it. So far, the declarations, and the lines they read:

- a base carrying a field, an effect and kinds for the commands beneath it, and names read as the app's own;
- a fleet's command that a detachment says too, its slot by an alias (`fleet {fleet} mine`, `detachment {detachment}
  mine`);
- a station that may be left out (`dock {station}` beside `dock nearest`);
- a literal beside a slot, in two commands (`jump {system}`, `jump nearest {ore}`);
- a required flag and a switch, on a command that asks first (`fleets merge {fleet} --into …`);
- a `Bool` said as a word (`fleets start true`);
- an optional positional, a slot of several words, and the rest of the line;
- a read with a typed reply, which can wait (`--until docked=true`), a command that asks first, and an
  interactive command with the form an agent says instead;
- a share in percent, or off (`fleet {fleet} retreat {share}`), and a routine taken up with its variables, each
  read by the variable's own names (`fleet {fleet} run {routine} {variables**}`);
- lines that say a command, its `EXAMPLES`, with `<name>` placeholders and without;
- a fleet's orders as steps of a chain, joined by `then` (`fleet {fleet} jump {system} then move {to} then mine`), and
  the fleet's commands that aren't steps (`retreat`, `run`, `buy ship`);
- steps that move the chain on (`jump`, `move`, `dock`, and `jump nearest`, to somewhere the line doesn't say), and
  places looked for where the fleet will be (`move {to}`, `dock {station}`);
- the app's names, as resolvers over fixed tables (:class:`Table`, :class:`Variables`, :data:`NAMES`): fleets,
  detachments, goods, systems, and the sites and stations in the system of a fleet or a place (one with an
  apostrophe in its name), routines, and each routine's variables.
"""

import difflib
import enum

# At runtime: tooling evaluates a command's annotations (`typing.get_type_hints`).
from datetime import timedelta  # noqa: TC003
from typing import ClassVar, cast

import parsed

FLEET = parsed.Name('fleet')
DETACHMENT = parsed.Name('detachment')


class Colour(enum.Enum):
    """A hull's paint: an enum's values to offer."""

    RED = 'red'
    GREEN = 'green'


class Table:
    """A resolver over a fixed table, as an app's might be: a name, case aside, or a key, to its key.

    ``within`` narrows it by scope: each scope's value to the keys it holds. A scope it doesn't know holds nothing,
    and no scope looks across them all.
    """

    def __init__(self, names: dict[str, str], *, within: dict[str, set[str]] | None = None) -> None:
        self.names = names
        self.within = within

    def _keys(self, scope: str | None) -> dict[str, str]:
        held = None if self.within is None or scope is None else self.within.get(scope, set())
        return {name: key for name, key in self.names.items() if held is None or key in held}

    def lookup(self, word: str, scope: str | None) -> str | None:
        names = self._keys(scope)
        found = {name.lower(): key for name, key in names.items()}.get(word.lower())
        return found or (word if word in names.values() else None)

    def suggest(self, word: str, scope: str | None) -> list[str]:
        return difflib.get_close_matches(word, list(self._keys(scope)), n=3, cutoff=0.5)

    def options(self, scope: str | None) -> list[str]:
        return list(self._keys(scope))


class Variables(Table):
    """Each routine's variables, as a pairs resolver: the variables by routine, and each one's own names."""

    def __init__(self, routines: dict[str, dict[str, parsed.Resolver | None]]) -> None:
        variables = dict.fromkeys(variable for held in routines.values() for variable in held)  # in order
        super().__init__(
            {variable: variable for variable in variables}, within={r: set(v) for r, v in routines.items()}
        )
        self.routines = routines

    def values(self, key: str, scope: str | None) -> parsed.Resolver | None:
        held = [self.routines[scope]] if scope in self.routines else list(self.routines.values())
        return next((found[key] for found in held if key in found), None)


class Saying:
    """A resolver that says why a word names nothing, as an app's may: where to look. Else it reads as ``inner``.

    ``reason`` is its message, with the word and the scope put in: ``'no station {word!r} in reach of {scope}'``.
    """

    def __init__(self, inner: parsed.Resolver, reason: str) -> None:
        self.inner, self.reason = inner, reason

    def lookup(self, word: str, scope: str | None) -> str | None:
        found = self.inner.lookup(word, scope)
        if found is None:
            raise ValueError(self.reason.format(word=word, scope=scope))
        return found

    def suggest(self, word: str, scope: str | None) -> list[str]:
        return list(self.inner.suggest(word, scope))

    def options(self, scope: str | None) -> list[str]:
        return list(self.inner.options(scope))

    def values(self, key: str, scope: str | None) -> parsed.Resolver | None:
        return cast('parsed.names.PairsResolver', self.inner).values(key, scope)


#: The system each scope is in: a fleet, where it is; a system, itself; a site, its own.
SYSTEM_OF = {
    'f1': 'vruba',
    'd2': 'vruba',
    'f2': 'sol',
    'vruba': 'vruba',
    'sol': 'sol',
    'vesta': 'vruba',
    'vrubaa-belt-1': 'vruba',
    'vruba-rings': 'vruba',
    'ceres': 'sol',
    'sol-belt': 'sol',
}


def in_systems(held: dict[str, set[str]]) -> dict[str, set[str]]:
    """Each scope's keys, as a :class:`Table` narrows by them: those in its system, by each system's keys."""
    return {scope: held[system] for scope, system in SYSTEM_OF.items()}


GOODS = Table({'Iron': 'iron', 'Coal': 'coal'})
SYSTEMS = Table({'Vruba': 'vruba', 'Sol': 'sol'})
STATIONS = Table(
    {'Vesta': 'vesta', "Vruba'a Belt 1": 'vrubaa-belt-1', 'Ceres': 'ceres'},
    within=in_systems({'vruba': {'vesta', 'vrubaa-belt-1'}, 'sol': {'ceres'}}),
)
SITES = Table(
    {
        'Vesta': 'vesta',
        "Vruba'a Belt 1": 'vrubaa-belt-1',
        'Vruba Rings': 'vruba-rings',
        'Ceres': 'ceres',
        'Sol Belt': 'sol-belt',
    },
    within=in_systems({'vruba': {'vesta', 'vrubaa-belt-1', 'vruba-rings'}, 'sol': {'ceres', 'sol-belt'}}),
)

#: The app's names, by category, as a line is read with them.
NAMES: dict[str, parsed.Resolver] = {
    'fleet': Table({'Prospector': 'f1', 'Hauler': 'f2'}),
    'detachment': Table({'Scouts': 'd2'}),
    'good': GOODS,
    'system': SYSTEMS,
    'site': SITES,
    'station': STATIONS,
    'routine': Table({'Mining': 'mining', 'Patrol': 'patrol'}),
    'variable': Variables({'mining': {'ore': GOODS, 'home': STATIONS}, 'patrol': {'route': None}}),
}


@parsed.parsed
class FleetView(parsed.Parsed):
    """What a fleet's view returns: a reply."""

    fleet: str = parsed.Str(required=True, doc="the fleet's key")
    docked: bool = parsed.Bool(default=False, doc='whether it is docked')


@parsed.parsed
class FleetCommand(parsed.Command):
    """A base: the fleet every command beneath it acts on, their effect, how a fleet or a detachment is read, and
    the chain its orders are steps of.
    """

    EFFECT = parsed.Effect.WRITE
    STEPS = True
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'fleet': FLEET, 'detachment': DETACHMENT}
    ALIASES: ClassVar[dict[str, str]] = {'detachment': 'fleet'}

    fleet: str = parsed.Str(required=True, doc='the fleet')


@parsed.parsed
class FleetMine(FleetCommand):
    """Mine until the hold is full."""

    PHRASE = 'fleet {fleet} mine'
    EXTRA_PHRASES = ('detachment {detachment} mine',)
    POLYMORPHIC = True
    EXAMPLES = ('fleet <fleet> mine', 'fleet <fleet> mine --for <span>', 'fleet prospector mine --for 1h30m')

    for_: timedelta | None = parsed.TimeDelta(data_key='for', default=None, doc='stop after this long')


@parsed.parsed
class FleetDock(FleetCommand):
    """Dock at a station, or at the nearest."""

    PHRASE = 'fleet {fleet} dock {station}'
    EXTRA_PHRASES = ('fleet {fleet} dock nearest',)
    EXAMPLES = ('fleet <fleet> dock <station>', 'fleet <fleet> dock nearest')
    MOVES = 'station'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'station': parsed.Name('station', scope='fleet', follows=True)}

    station: str | None = parsed.Str(default=None, doc='the station; left out, the nearest')


@parsed.parsed
class FleetJump(FleetCommand):
    """Jump to a system."""

    PHRASE = 'fleet {fleet} jump {system}'
    MOVES = 'system'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'system': parsed.Name('system')}

    system: str = parsed.Str(required=True, doc='the system')


@parsed.parsed
class FleetJumpNearest(FleetCommand):
    """Jump to the nearest system with an ore."""

    PHRASE = 'fleet {fleet} jump nearest {ore}'
    MOVES = True
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'ore': parsed.Name('good')}

    ore: str = parsed.Str(required=True, doc='the ore')


@parsed.parsed
class FleetMove(FleetCommand):
    """Move within the system, to a belt or a station."""

    PHRASE = 'fleet {fleet} move {to}'
    MOVES = 'to'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'to': parsed.Name('site', scope='fleet', follows=True)}

    to: str = parsed.Str(required=True, doc='where to')


@parsed.parsed
class FleetRetreat(FleetCommand):
    """Set the share of its hull at which a fleet retreats, or turn retreating off: a setting, not a step."""

    PHRASE = 'fleet {fleet} retreat {share}'
    STEPS = False
    EXAMPLES = ('fleet <fleet> retreat <share>%', 'fleet prospector retreat off')
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'share': parsed.kinds.Number(suffix='%', words={'off': None})}

    share: float | None = parsed.Float(
        required=True, nullable=True, ge=5, le=95, doc='the share, in percent; off, never'
    )


@parsed.parsed
class FleetRun(FleetCommand):
    """Take up a routine, its variables given."""

    PHRASE = 'fleet {fleet} run {routine} {variables**}'
    STEPS = False
    EXAMPLES = ('fleet <fleet> run <routine> <variable> <value>', 'fleet prospector run mining ore iron home vesta')
    KINDS: ClassVar[dict[str, parsed.Kind]] = {
        'routine': parsed.Name('routine'),
        'variables': parsed.kinds.Pairs('variable', scope='routine'),
    }

    routine: str = parsed.Str(required=True, doc='the routine')
    variables: dict[str, str] = parsed.Str(keyed=True, default_factory=dict, doc="the routine's variables")


@parsed.parsed
class FleetSell(FleetCommand):
    """Sell goods from the hold."""

    PHRASE = 'fleet {fleet} sell {goods}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'goods': parsed.Name('good')}

    goods: list[str] = parsed.Str(many=True, required=True, doc='the goods to sell')


@parsed.parsed
class Log(parsed.Command):
    """Show the log's last lines."""

    PHRASE = 'log {n}'
    EFFECT = parsed.Effect.READ
    EXAMPLES = ('log', 'log 40')

    n: int = parsed.Int(default=20, ge=1, doc='how many lines')


@parsed.parsed
class Say(parsed.Command):
    """Say something to the galaxy."""

    PHRASE = 'say {message**}'
    EFFECT = parsed.Effect.ACTION

    message: str = parsed.Str(required=True, doc='what to say')


@parsed.parsed
class FleetBuyShip(FleetCommand):
    """Buy a ship at the station the fleet is docked at, asked first: it names the price."""

    PHRASE = 'fleet {fleet} buy ship {hull}'
    EFFECT = parsed.Effect.ACTION
    ASKS = True
    STEPS = False
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'hull': parsed.Name('hull')}

    hull: str = parsed.Str(required=True, doc='the hull to buy')


@parsed.parsed
class FleetsMerge(parsed.Command):
    """Merge a fleet into another, asked first."""

    PHRASE = 'fleets merge {fleet}'
    EFFECT = parsed.Effect.WRITE
    ASKS = True
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'fleet': FLEET, 'into': FLEET}

    fleet: str = parsed.Str(required=True, doc='the fleet merged')
    into: str = parsed.Str(required=True, doc='the fleet it joins')
    quiet: bool = parsed.Bool(default=False, doc='without a report')


@parsed.parsed
class FleetsStart(parsed.Command):
    """Start every fleet, or stop them."""

    PHRASE = 'fleets start {on}'
    EFFECT = parsed.Effect.WRITE

    on: bool = parsed.Bool(required=True, doc='whether they start')


@parsed.parsed
class FleetsShow(parsed.Command):
    """Show a fleet."""

    PHRASE = 'fleets show {fleet}'
    EFFECT = parsed.Effect.READ
    REPLY = FleetView
    EXAMPLES = ('fleets show <fleet> --until docked=true', 'fleets show f1 --until docked=true --timeout 2m')
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'fleet': FLEET}

    fleet: str = parsed.Str(required=True, doc='the fleet')


@parsed.parsed
class ShipsMakeAdd(parsed.Command):
    """Fit a part to a ship, without the fit editor."""

    PHRASE = 'ships make {ship} add {part}'
    EFFECT = parsed.Effect.WRITE
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'ship': parsed.Name('ship'), 'part': parsed.Name('part')}

    ship: str = parsed.Str(required=True, doc='the ship')
    part: str = parsed.Str(required=True, doc='the part to fit')


@parsed.parsed
class ShipFit(parsed.Command):
    """Open the fit editor on a ship: the client's own."""

    PHRASE = 'ship {ship} fit'
    INTERACTIVE = True
    INSTEAD = ShipsMakeAdd
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'ship': parsed.Name('ship')}

    ship: str = parsed.Str(required=True, doc='the ship')
