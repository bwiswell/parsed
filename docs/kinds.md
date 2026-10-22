# `kinds.py`: how a field's words are read

A kind says how a field's words read on a line: what they read to, what Tab may offer, and how a value is written
back as words. Kinds are plain data. A module that declares commands imports nothing of an app's to give one: a
`Name`'s lookups are the app's own, given at run time by its category.

Reading a line, each word is read by its field's kind to the field's wire value: what seared's `load` takes, and
what a tool call would send.

## Every field has a kind

A field's kind is its `KINDS` entry, or else its seared type's default (`parsed.kinds.default_kind(field)`):

| seared field | Default kind | Its words |
|---|---|---|
| `Str`, `Path`, `UUID` | `Word` | a word, as written; a `UUID` checked |
| `Int`, `Float`, `Decimal` | `Number` | a number, its thousands grouped by commas or not |
| `Bool` | `Switch` | `true` or `false`; as a flag, given or not |
| `Enum` | `Choice` | one of its values, case aside |
| `TimeDelta` | `Duration` | `90s`, `10m`, `2h`, `1h30m` |
| `Date`, `DateTime`, `Time` | `Moment` | ISO 8601 |
| `T`, `Union`, `Tuple`, `Bytes`, `Dict`, the arrays and frames | none | give it a kind in `KINDS` |
| any `keyed` field | none | [`Pairs`](#pairs), given in `KINDS` |

A `many` field's kind reads each of its words. A field whose type has no word form, and no `KINDS` entry, is
refused when its command is declared: it couldn't be said on a line.

## Reading a word

`kind.read(word, field)` gives the field's wire value for a word: one of its [literal words](#literal-words)'
value, else its own form's. seared then checks it as it checks any value, so a field's bounds, lengths and pattern
hold on a line as they do on the wire:

| Kind | Reads | To |
|---|---|---|
| `Word` | any word; for a `UUID`, a UUID | the word: `logs/today` |
| `Number` | for an `Int`, a whole number: `40`, `-3`, `1,000`; its `suffix` may follow it | an `int`: `1000` |
| | for a `Float`, a number: `1.5`, `.5`, `1e3`, `12,500.25` | a `float`: `12500.25` |
| | for a `Decimal`, a number | its digits, kept exact: `'1234.50'` |
| `Switch` | `true` or `false`, case aside | `True` or `False` |
| `Choice` | one of the `Enum`'s values, as written or case aside | the value: `GREEN` to `'green'`, `2` to `2` |
| `Duration` | hours, minutes and seconds, each optional, in that order: `90s`, `10m`, `1.5h`, `1h30m` | seconds: `5400.0` |
| `Moment` | ISO 8601: `2026-10-21`, `14:30`, `2026-10-21T14:30`, by the field | the word |
| `Name` | any word | its key, by the app's resolver ([`names.md`](names.md)); else the word, as typed |

A comma in a number groups its thousands, three digits each, so `1,00` and `1,5` aren't numbers; neither are `inf`
and `nan`. A span of time says its unit, so `90` isn't one. A word a kind can't read raises a `ValueError` saying
what one should be (`'soon' is not a span of time: say 90s, 10m, 2h or 1h30m`); on a line, the walk refuses it as a
`ReadError` naming the phrase or the flag.

A kind of an app's own subclasses `Kind` and overrides `form(word, field)`, its own form of a word; the base's gives
the word as written. `read` stays the base's, so its literal words come first.

## Literal words

Any kind may take `words`: literal words it reads before its own form, each to a value of its own, matched case
aside. A quoted word is never one, so a value spelled like a literal can still be said.

```python
@parsed.parsed
class FleetRetreat(FleetCommand):
    PHRASE = 'fleet {fleet} retreat {share}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'share': parsed.kinds.Number(suffix='%', words={'off': None})}

    share: float | None = parsed.Float(required=True, nullable=True, ge=5, le=95)
```

`retreat 30%` reads `30.0`, `retreat OFF` reads `None`, and `retreat "off"` is no number. Each literal is one
lowercase word. A literal that reads to `None` wants a `nullable` field, since seared drops a `null` from any other:
a command whose field isn't is refused. `Number(suffix='%')` lets its suffix follow the number, and leaves it off.

`kind.literal(word)` gives a literal word's value, or `parsed.kinds.NOT_LITERAL` for a word that isn't one.

## `Name`

`parsed.Name(category, scope=None)` is one of an app's names: a fleet, a station, a good. Its words read to the
name's key by the resolver the app gives for its `category` with each line ([`names.md`](names.md)); with none,
as typed.

```python
@parsed.parsed
class FleetCommand(parsed.Command):
    KINDS: ClassVar[dict[str, parsed.Kind]] = {
        'fleet': parsed.Name('fleet'),
        'detachment': parsed.Name('detachment'),    # a renamed slot's kind, for the polymorphic twins
    }

    fleet: str = parsed.Str(required=True)


@parsed.parsed
class FleetDock(FleetCommand):
    PHRASE = 'fleet {fleet} dock {station}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'station': parsed.Name('station', scope='fleet')}

    station: str | None = parsed.Str(default=None)
```

- **`category`** is a name (`fleet`, `station`): what the app's resolvers are given by.
- **`scope`** names another field of the command, whose value narrows the lookup: `scope='fleet'` looks for a
  station within the fleet's reach, the resolver given the fleet's key. It must name a field of every command that
  reads by it, other than the field itself, and a command's scopes mustn't go round, or the command is refused. An
  entry a base declares but a command never reads by isn't held to it.

## `Pairs`

`parsed.kinds.Pairs(category, scope=None)` reads a `keyed` field's words as `key value` pairs, said as the rest of
the line: a routine's variables.

```python
@parsed.parsed
class FleetRun(FleetCommand):
    PHRASE = 'fleet {fleet} run {routine} {variables**}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {
        'routine': parsed.Name('routine'),
        'variables': parsed.kinds.Pairs('variable', scope='routine'),
    }

    routine: str = parsed.Str(required=True)
    variables: dict[str, str] = parsed.Str(keyed=True, default_factory=dict)
```

`fleet f1 run mining ore iron home vesta` gives `{'ore': 'iron', 'home': 'vesta'}`. The app's resolver for the
category reads each key, and gives each key's values a resolver of their own
([`names.md`](names.md#pairs)); with none, keys and values read as typed. A command is refused when a `Pairs` kind
reads a field that isn't keyed or isn't said as the rest of the line, or when a keyed field reads by any other kind.

`Name` and `Pairs` are both `parsed.kinds.Named`: a category, and a scope.

## The default kinds

`Word`, `Number`, `Switch`, `Choice`, `Duration` and `Moment` are `parsed.kinds.*`, beside `Kind`, the base of
every kind. Each is plain data, compared by value. Only `Kind` and `Name` are on parsed's root, since seared's field
types (`parsed.Path`, `parsed.Enum`) take the plainer names there.
