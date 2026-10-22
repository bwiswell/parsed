"""Two commands that say one phrase: the tree won't build."""

import parsed


@parsed.parsed
class Dock(parsed.Command):
    """Dock at a station."""

    PHRASE = 'dock {station}'

    station: str = parsed.Str(required=True)


@parsed.parsed
class Berth(parsed.Command):
    """Berth at a station, said as docking is."""

    PHRASE = 'dock {berth}'

    berth: str = parsed.Str(required=True)
