"""Commands shaped like farlandia's hardest, written fresh: parsed's tests depend on no game.

It grows with each release that needs more of it. So far, the declarations alone: a base carrying a field and an
effect for the commands beneath it, a read with a typed reply, a command that asks first, and an interactive command
with the form an agent says instead.
"""

# At runtime: tooling evaluates a command's annotations (`typing.get_type_hints`).
from datetime import timedelta  # noqa: TC003

import parsed


@parsed.parsed
class FleetView(parsed.Parsed):
    """What a fleet's view returns: a reply."""

    fleet: str = parsed.Str(required=True, doc="the fleet's key")
    docked: bool = parsed.Bool(default=False, doc='whether it is docked')


@parsed.parsed
class FleetCommand(parsed.Command):
    """A base: the fleet every command beneath it acts on, and their effect."""

    EFFECT = parsed.Effect.WRITE

    fleet: str = parsed.Str(required=True, doc='the fleet')


@parsed.parsed
class FleetMine(FleetCommand):
    """Mine until the hold is full."""

    PHRASE = 'fleet {fleet} mine'

    for_: timedelta | None = parsed.TimeDelta(data_key='for', default=None, doc='stop after this long')


@parsed.parsed
class FleetBuyShip(FleetCommand):
    """Buy a ship at the station the fleet is docked at, asked first: it names the price."""

    PHRASE = 'fleet {fleet} buy ship {hull}'
    EFFECT = parsed.Effect.ACTION
    ASKS = True

    hull: str = parsed.Str(required=True, doc='the hull to buy')


@parsed.parsed
class FleetsShow(parsed.Command):
    """Show a fleet."""

    PHRASE = 'fleets show {fleet}'
    EFFECT = parsed.Effect.READ
    REPLY = FleetView

    fleet: str = parsed.Str(required=True, doc='the fleet')


@parsed.parsed
class ShipsMakeAdd(parsed.Command):
    """Fit a part to a ship, without the fit editor."""

    PHRASE = 'ships make {ship} add {part}'
    EFFECT = parsed.Effect.WRITE

    ship: str = parsed.Str(required=True, doc='the ship')
    part: str = parsed.Str(required=True, doc='the part to fit')


@parsed.parsed
class ShipFit(parsed.Command):
    """Open the fit editor on a ship: the client's own."""

    PHRASE = 'ship {ship} fit'
    INTERACTIVE = True
    INSTEAD = ShipsMakeAdd

    ship: str = parsed.Str(required=True, doc='the ship')
