# `kinds.py`: how a field's words are read

A kind says how a field's words read on a line: what they read to, what Tab may offer, and how a value is written
back as words. Kinds are plain data. A module that declares commands imports nothing of an app's to give one: a
`Name`'s lookups are the app's own, given at run time by its category.

So far, kinds are declared; reading lines by them comes next.

## Every field has a kind

A field's kind is its `KINDS` entry, or else its seared type's default (`parsed.kinds.default_kind(field)`):

| seared field | Default kind | Its words |
|---|---|---|
| `Str`, `Path`, `UUID` | `Word` | a word, as written |
| `Int`, `Float`, `Decimal` | `Number` | a number |
| `Bool` | `Switch` | `true` or `false`; as a flag, given or not |
| `Enum` | `Choice` | one of its values |
| `TimeDelta` | `Duration` | `90s`, `10m`, `1h30m` |
| `Date`, `DateTime`, `Time` | `Moment` | ISO 8601 |
| `T`, `Union`, `Tuple`, `Bytes`, `Dict`, the arrays and frames, any `keyed` field | none | give it a kind in `KINDS` |

A `many` field's kind reads each of its words. A field whose type has no word form, and no `KINDS` entry, is
refused when its command is declared: it couldn't be said on a line.

## `Name`

`parsed.Name(category, scope=None)` is one of an app's names: a fleet, a station, a good. Its words read to the
name's key by what the app gives for its `category`.

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

- **`category`** is a name (`fleet`, `station`): what the app's lookups are given by.
- **`scope`** names another field of the command, whose value narrows the lookup: `scope='fleet'` looks for a
  station within the fleet's system. It must name a field of every command that reads by it, other than the field
  itself, or the command is refused. An entry a base declares but a command never reads by isn't held to it.

## The default kinds

`Word`, `Number`, `Switch`, `Choice`, `Duration` and `Moment` are `parsed.kinds.*`, beside `Kind`, the base of
every kind. Each is plain data, compared by value. Only `Kind` and `Name` are on parsed's root, since seared's field
types (`parsed.Path`, `parsed.Enum`) take the plainer names there.
