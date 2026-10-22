"""Commands shaped like farlandia's hardest, written fresh: parsed's tests depend on no game.

It grows with each release that needs more of it. So far, the declarations, and the lines they read:

- a base carrying a field, an effect and kinds for the commands beneath it, and names read as the app's own;
- a fleet's command that a detachment says too, its slot renamed (`fleet {fleet} mine`, `detachment {detachment}
  mine`);
- a station that may be left out (`dock {station}` beside `dock nearest`);
- a literal beside a slot, in two commands (`jump {system}`, `jump nearest {ore}`);
- a required flag and a switch, on a command that asks first (`fleets merge {fleet} --into …`);
- a `Bool` said as a word (`fleets start true`);
- an optional positional, a slot of several words, and the rest of the line;
- a read with a typed reply, a command that asks first, and an interactive command with the form an agent says
  instead;
- a share in percent, or off (`fleet {fleet} retreat {share}`), and a routine taken up with its variables, each
  read by the variable's own names (`fleet {fleet} run {routine} {variables**}`);
- the app's names, as resolvers over fixed tables (:class:`Table`, :class:`Variables`, :data:`NAMES`): fleets,
  detachments, goods, stations within a fleet's reach (one with an apostrophe in its name), routines, and each
  routine's variables.
"""

import difflib

# At runtime: tooling evaluates a command's annotations (`typing.get_type_hints`).
from datetime import timedelta  # noqa: TC003
from typing import ClassVar

import parsed

FLEET = parsed.Name('fleet')
DETACHMENT = parsed.Name('detachment')


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
        variables = {variable for held in routines.values() for variable in held}
        super().__init__(
            {variable: variable for variable in variables}, within={r: set(v) for r, v in routines.items()}
        )
        self.routines = routines

    def values(self, key: str, scope: str | None) -> parsed.Resolver | None:
        held = [self.routines[scope]] if scope in self.routines else list(self.routines.values())
        return next((found[key] for found in held if key in found), None)


GOODS = Table({'Iron': 'iron', 'Coal': 'coal'})
STATIONS = Table(
    {'Vesta': 'vesta', "Vruba'a Belt 1": 'vrubaa-belt-1', 'Ceres': 'ceres'},
    within={'f1': {'vesta', 'vrubaa-belt-1'}, 'f2': {'ceres'}},
)

#: The app's names, by category, as a line is read with them.
NAMES: dict[str, parsed.Resolver] = {
    'fleet': Table({'Prospector': 'f1', 'Hauler': 'f2'}),
    'detachment': Table({'Scouts': 'd2'}),
    'good': GOODS,
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
    """A base: the fleet every command beneath it acts on, their effect, and how a fleet or a detachment is read."""

    EFFECT = parsed.Effect.WRITE
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'fleet': FLEET, 'detachment': DETACHMENT}

    fleet: str = parsed.Str(required=True, doc='the fleet')


@parsed.parsed
class FleetMine(FleetCommand):
    """Mine until the hold is full."""

    PHRASE = 'fleet {fleet} mine'
    EXTRA_PHRASES = ('detachment {detachment} mine',)
    POLYMORPHIC = True

    for_: timedelta | None = parsed.TimeDelta(data_key='for', default=None, doc='stop after this long')


@parsed.parsed
class FleetDock(FleetCommand):
    """Dock at a station, or at the nearest."""

    PHRASE = 'fleet {fleet} dock {station}'
    EXTRA_PHRASES = ('fleet {fleet} dock nearest',)
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'station': parsed.Name('station', scope='fleet')}

    station: str | None = parsed.Str(default=None, doc='the station; left out, the nearest')


@parsed.parsed
class FleetJump(FleetCommand):
    """Jump to a system."""

    PHRASE = 'fleet {fleet} jump {system}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'system': parsed.Name('system')}

    system: str = parsed.Str(required=True, doc='the system')


@parsed.parsed
class FleetJumpNearest(FleetCommand):
    """Jump to the nearest system with an ore."""

    PHRASE = 'fleet {fleet} jump nearest {ore}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'ore': parsed.Name('good')}

    ore: str = parsed.Str(required=True, doc='the ore')


@parsed.parsed
class FleetRetreat(FleetCommand):
    """Set the share of its hull at which a fleet retreats, or turn retreating off."""

    PHRASE = 'fleet {fleet} retreat {share}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'share': parsed.kinds.Number(suffix='%', words={'off': None})}

    share: float | None = parsed.Float(
        required=True, nullable=True, ge=5, le=95, doc='the share, in percent; off, never'
    )


@parsed.parsed
class FleetRun(FleetCommand):
    """Take up a routine, its variables given."""

    PHRASE = 'fleet {fleet} run {routine} {variables**}'
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
