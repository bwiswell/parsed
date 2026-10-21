"""Commands shaped like farlandia's hardest, written fresh: parsed's tests depend on no game.

It grows with each release that needs more of it. So far, the declarations alone:

- a base carrying a field, an effect and kinds for the commands beneath it, and names read as the app's own;
- a fleet's command that a detachment says too, its slot renamed (`fleet {fleet} mine`, `detachment {detachment}
  mine`);
- a station that may be left out (`dock {station}` beside `dock nearest`);
- an optional positional, a slot of several words, and the rest of the line;
- a read with a typed reply, a command that asks first, and an interactive command with the form an agent says
  instead.
"""

# At runtime: tooling evaluates a command's annotations (`typing.get_type_hints`).
from datetime import timedelta  # noqa: TC003
from typing import ClassVar

import parsed

FLEET = parsed.Name('fleet')
DETACHMENT = parsed.Name('detachment')


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
