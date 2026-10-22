"""Handlers bound by their path, so an app imports this module only when one is first looked up."""

#: Not a handler: a path that names it is refused when it's looked up.
COUNT = 3


def run(command: object, ctx: object) -> str:
    """Say what ran."""
    return f'ran {command!r}'


class Service:
    """Handlers as methods of a class, named by a dotted path within the module."""

    @staticmethod
    def status(command: object, ctx: object) -> str:
        """Say what was asked."""
        return f'status of {command!r}'
