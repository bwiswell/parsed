"""An agent's tooling's verbs as a tree, shaped like `tooled`'s and written fresh: parsed's tests depend on no tool.

Its command line reads by hand what parsed reads here: spans of time (`--timeout 2m`), counts (`--count 3`), and
`slot=value` words, read by a kind of the fixture's own (`Assignment`), as an app's kind is. Every verb takes the
policy, `--pretty` and `--select`, from its base. `see`, `do` and `session run` pass a line of the app's on whole,
its flags among it (`parsed.kinds.Line`).
"""

# At runtime: tooling evaluates a command's annotations (`typing.get_type_hints`).
import enum
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path  # noqa: TC003
from typing import ClassVar

import parsed


@dataclass(frozen=True, slots=True)
class Assignment(parsed.Kind):
    """A ``slot=value`` word: a slot of a contract and its value, or with ``dotted``, a path into a reply.

    Its wire value is the word as written, once it's checked to say one.

    Attributes:
        dotted: Whether the name is a dotted path (``reply.docked``, ``ships[].hull``), not a slot's name.
    """

    dotted: bool = False

    def form(self, word: str, field: object) -> object:
        """The word, once it has a name, ``=``, and a value."""
        name, eq, _ = word.partition('=')
        parts = [part.removesuffix('[]') for part in name.split('.')] if self.dotted else [name]
        if not eq or not all(part.isidentifier() for part in parts):
            msg = f'{word!r} is not {self.what(field)}'
            raise ValueError(msg)
        return word

    def example(self, field: object) -> object:
        """``docked=true``, or ``fleet=f1``: a word its form reads, for ``parsed check``."""
        return 'docked=true' if self.dotted else 'fleet=f1'

    def what(self, field: object) -> str:
        """``slot=value``, or ``path=value``, with an example."""
        return 'path=value, such as docked=true' if self.dotted else 'slot=value, such as fleet=f1'


SLOT = Assignment()
CONDITION = Assignment(dotted=True)


class Format(enum.Enum):
    """The form tool definitions are written in."""

    OPENAI = 'openai'
    ANTHROPIC = 'anthropic'
    MCP = 'mcp'


@parsed.parsed
class Verb(parsed.Command):
    """A base: what every verb takes, the policy it reads and how it writes."""

    policy: Path | None = parsed.Path(default=None, doc='the policy file (else $TOOLED_POLICY, else ./tooled.toml)')
    pretty: bool = parsed.Bool(default=False, doc='indent the JSON (the default on a terminal)')
    select: str | None = parsed.Str(default=None, doc='keep parts: a.b, list[].key; comma-separated')


@parsed.parsed
class Check(Verb):
    """Read the policy and the protocol, and say what's wrong."""

    PHRASE = 'check'
    EFFECT = parsed.Effect.READ

    connect: bool = parsed.Bool(default=False, doc='also open the session the policy describes')
    resolve: bool = parsed.Bool(default=True, doc="resolve the protocol's operations")


@parsed.parsed
class Operations(Verb):
    """List the operations the policy shows."""

    PHRASE = 'operations'
    EFFECT = parsed.Effect.READ


@parsed.parsed
class Described(parsed.Parsed):
    """An operation, described."""

    operation: str = parsed.Str(required=True, doc='its name')
    reply: bool = parsed.Bool(default=False, doc="whether it's the reply's schema")


@parsed.parsed
class Describe(Verb):
    """Describe an operation: its request as a field list, or its reply."""

    PHRASE = 'describe {operation}'
    EFFECT = parsed.Effect.READ
    REPLY = Described

    operation: str = parsed.Str(required=True, doc='an operation: its class name, or module:Class')
    variant: str | None = parsed.Str(default=None, doc="one variant of the request's union, by its tag")
    reply: bool = parsed.Bool(default=False, doc="the reply's whole schema, not its field list")


@parsed.parsed
class Reading(Verb):
    """A base: a verb that reads an operation, narrowed by its slots."""

    KINDS: ClassVar[dict[str, parsed.Kind]] = {'slots': SLOT}

    operation: str = parsed.Str(required=True, doc='a contract: its class name, or module:Class')
    slots: list[str] = parsed.Str(many=True, default_factory=list, doc='a slot to narrow by; left out, it widens')


@parsed.parsed
class Fetch(Reading):
    """Fetch a retained contract's values."""

    PHRASE = 'fetch {operation} {slots}'
    EFFECT = parsed.Effect.READ
    EXAMPLES = ('fetch FleetState fleet=f1', 'fetch FleetState --timeout 10s')

    timeout: timedelta = parsed.TimeDelta(default=timedelta(seconds=5), doc='how long to wait for its replies')


@parsed.parsed
class Query(Reading):
    """Ask a queryable that reads."""

    PHRASE = 'query {operation} {slots}'
    EFFECT = parsed.Effect.READ
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'param': SLOT}

    request: str | None = parsed.Str(default=None, doc='the request, in its wire form: JSON, - for stdin, @path')
    param: list[str] = parsed.Str(many=True, default_factory=list, doc='a selector parameter')


@parsed.parsed
class Listen(Reading):
    """Print each value a contract publishes, as JSON lines."""

    PHRASE = 'listen {operation} {slots}'
    EFFECT = parsed.Effect.READ

    count: int | None = parsed.Int(default=None, ge=1, doc='stop after this many values')
    for_: timedelta | None = parsed.TimeDelta(default=None, data_key='for', doc='stop after this long')
    meta: bool = parsed.Bool(default=False, doc="add each value's key, origin and time")


@parsed.parsed
class Invoke(Reading):
    """Ask a queryable that writes; --dry-run builds the request and checks it, and sends nothing."""

    PHRASE = 'invoke {operation} {slots}'
    EFFECT = parsed.Effect.WRITE

    timeout: timedelta = parsed.TimeDelta(default=timedelta(seconds=5), doc='how long to wait for its replies')
    request: str | None = parsed.Str(default=None, doc='the request, in its wire form: JSON, - for stdin, @path')
    retry: bool = parsed.Bool(default=True, doc='after no reply, ask once more')


@parsed.parsed
class Wait(Reading):
    """Wait for a retained contract or a stream to hold a value, and print it."""

    PHRASE = 'wait {operation} {slots}'
    EFFECT = parsed.Effect.READ
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'until': CONDITION}
    EXAMPLES = ('wait FleetState fleet=f1 --until docked=true --timeout 2m',)

    until: list[str] = parsed.Str(many=True, required=True, doc='a path and the value it must equal; all must hold')
    timeout: timedelta = parsed.TimeDelta(default=timedelta(seconds=30), doc='how long to wait')
    meta: bool = parsed.Bool(default=False, doc="add the value's key, origin and time")


@parsed.parsed
class Tools(Verb):
    """Export the operations the policy shows as tool definitions, for a harness."""

    PHRASE = 'tools'
    EFFECT = parsed.Effect.READ

    format: Format = parsed.Enum(enum=Format, default=Format.OPENAI, doc='the form to write them in')
    sizes: bool = parsed.Bool(default=False, doc="each tool's bytes and estimated tokens, not the tools")


@parsed.parsed
class Call(Verb):
    """Call a tool, by the name the tools verb gives it."""

    PHRASE = 'call {tool}'
    EFFECT = parsed.Effect.WRITE

    tool: str = parsed.Str(required=True, doc="the tool, by its name in tools' output")
    args: str | None = parsed.Str(default=None, doc="the call's arguments, as JSON")


#: A line of the app's, passed on whole: its flags, parsed's own among them, are its own.
LINE: dict[str, parsed.Kind] = {'line': parsed.kinds.Line()}


@parsed.parsed
class See(Verb):
    """Read the app by a line of its own, as a user would say it."""

    PHRASE = 'see {line**}'
    EFFECT = parsed.Effect.READ
    KINDS = LINE

    line: str = parsed.Str(required=True, doc="the app's line, its flags among it")


@parsed.parsed
class Do(Verb):
    """Run a line of the app's that acts, as a user would say it."""

    PHRASE = 'do {line**}'
    EFFECT = parsed.Effect.ACTION
    KINDS = LINE

    line: str = parsed.Str(required=True, doc="the app's line, its flags among it")


@parsed.parsed
class SessionRun(Verb):
    """Run a command in the session, as given after --."""

    PHRASE = 'session run {command**}'
    EFFECT = parsed.Effect.ACTION
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'command': parsed.kinds.Line()}

    command: str = parsed.Str(required=True, doc='the command, and its arguments')
