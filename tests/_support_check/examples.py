"""Examples that rot: one no longer reads, one reads as another command, one reads but doesn't load."""

import parsed


@parsed.parsed
class Mine(parsed.Command):
    """Mine with a fleet; its second example says a word since renamed."""

    PHRASE = 'mine {fleet}'
    EXAMPLES = ('mine <fleet>', 'mien <fleet>', 'dig <site>')

    fleet: str = parsed.Str(required=True)


@parsed.parsed
class Dig(parsed.Command):
    """Dig at a site."""

    PHRASE = 'dig {site}'

    site: str = parsed.Str(required=True)


@parsed.parsed
class Log(parsed.Command):
    """Show the log; its second example asks for no lines, which its bound refuses."""

    PHRASE = 'log {n}'
    EXAMPLES = ('log 40', 'log 0')

    n: int = parsed.Int(default=20, ge=1)
