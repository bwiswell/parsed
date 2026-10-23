"""A chain whose two steps say the same words after their shared parts: its lines read, but a tool call can't tell
its steps apart.
"""

import parsed


@parsed.parsed
class Vessel(parsed.Command):
    """A chain's base: a vessel's orders."""

    STEPS = True

    vessel: str = parsed.Str(required=True)


@parsed.parsed
class ShipGo(Vessel):
    """A ship goes somewhere."""

    PHRASE = 'ship {vessel} go {to}'

    to: str = parsed.Str(required=True)


@parsed.parsed
class BoatGo(Vessel):
    """A boat goes somewhere: its words after the shared part are a ship's."""

    PHRASE = 'boat {vessel} go {to}'

    to: str = parsed.Str(required=True)
