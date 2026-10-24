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
and `nan`. A span of time says its unit, so `90` isn't one; `parsed.kinds.span(word)` reads one to its seconds,
and `spell_span(seconds)` writes one. A word a kind can't read raises a `ValueError` saying what one should be
(`'soon' is not a span of time: say 90s, 10m, 2h or 1h30m`); on a line, the walk refuses it as a `ReadError` naming
the phrase or the flag.

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

## Writing a value

`kind.write(value, field)` is reading's other way: a wire value as the words a line says it in, which read back to
it. A literal word comes first, for a value one reads to (`None` as `off`, matched by value and type, so `True`
isn't a literal for `1`); else `kind.spell(value, field)`, the kind's own spelling:

| Kind | Spells |
|---|---|
| `Number` | a whole float as an integer's digits (`30.0` as `30`), any other as Python writes it, exactly |
| `Switch` | `true` or `false` |
| `Duration` | seconds as hours, minutes and seconds, those that aren't nought: `5400.0` as `1h30m`, `0` as `0s` |
| `Pairs` | each pair's key and value, in turn |
| the others | the value as a word |

A kind of an app's own that overrides `form` overrides `spell` too, so its values write back.

## Describing its words

`kind.describe(field)` says what a field's words are, for help ([`help.md`](help.md)) and reference pages
([`doc/render.md`](doc/render.md)) where the field has no `doc=`: `kind.what(field)`, the kind's own description,
then its literal words (`a number, % after it or not, or off`):

| Kind | Says |
|---|---|
| `Word` | `a word`; `a path` for a `Path`, `a UUID` for a `UUID` |
| `Number` | `a whole number` for an `Int`, else `a number`; with a suffix, `% after it or not` |
| `Switch` | `true or false` |
| `Choice` | `one of red, green or blue`, the `Enum`'s values |
| `Duration` | `a span of time, such as 90s, 10m or 1h30m` |
| `Moment` | `a date, such as 2026-10-21`, a time or both, by its field |
| `Name` | `a station`, by its [term](#name), and `, within its fleet` for a scoped one; `an ore` before a vowel's sound, `a unit` |
| `Pairs` | `variable and value pairs`, by its term |

A kind of an app's own overrides `what` (`a hex number, such as ff`); its literal words follow, as they do for any.

## Labelling a value

`kind.usage_label(field)` is what a usage writes a flag's value as, between `<` and `>`: `--for <span>`, not
`--for <for>`. `None` leaves it to the flag's name. A usage writes the kind's literal words after it, each after a
`|` (`--share <n|off>`), and says it wherever a flag's value is written: a usage and a refusal's hint, help's rows,
the root options' usage and help, and a reference page ([`_walk/_hints.md`](_walk/_hints.md)).

| Kind | Labels a value |
|---|---|
| `Word` | `path` for a `Path`, `uuid` for a `UUID`; else `None`, the flag's name |
| `Number` | `n` |
| `Switch` | `true\|false`, for a value; a `Bool` flag is a switch, and takes none |
| `Choice` | the `Enum`'s values: `visual\|text\|auto` |
| `Duration` | `span` |
| `Moment` | `date`, `time` or `datetime`, by its field |
| `Name`, `Pairs` | its [term](#name): `fleet`, `ore` |

A slot keeps its name (`<fleet>`, `<goods> …`): a phrase is read by its slots' names, and a slot's name already says
what it holds. A kind of an app's own may override `usage_label`; the base's gives `None`.

## An example

`kind.example(field)` is a value the field may hold, as an instance holds it, for `parsed check` to make its
instances with ([`doc/check.md`](doc/check.md)). It's `None` by default, which leaves the value to the field's type
and constraints. A kind of an app's own with a form of its own gives one its form reads, since a value made from the
type alone may not: a `slot=value` kind gives `'fleet=f1'`, where a string's `example` would be refused.

## What a kind offers

Completion offers a kind's literal words, then `kind.offers(field)`: a `Choice`'s values, `true` and `false` for a
`Switch`, and `10m`, `30m` and `1h` for a `Duration`. The others offer nothing of their own, since any word may do;
a name's are its resolver's `options`. A kind of an app's own may override `offers`.

## `Name`

`parsed.Name(category, scope=None, *, follows=False, label=None)` is one of an app's names: a fleet, a station, a
good. Its words read to the name's key by the resolver the app gives for its `category` with each line
([`names.md`](names.md)); with none, as typed.

```python
@parsed.parsed
class FleetCommand(parsed.Command):
    KINDS: ClassVar[dict[str, parsed.Kind]] = {
        'fleet': parsed.Name('fleet'),
        'detachment': parsed.Name('detachment'),    # an alias's kind, for the polymorphic twins
    }
    ALIASES: ClassVar[dict[str, str]] = {'detachment': 'fleet'}

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
- **`follows=True`** makes the scope follow its chain's place, on a step whose scope is a field its chain shares:
  `Name('station', scope='fleet', follows=True)` is a station where the fleet is, or, after a step that moves the
  chain on, where it will be ([`command.md`](command.md#a-chains-place)). It needs a scope, and is refused on a
  command that isn't a step, or with a scope the chain doesn't share. A kind that follows isn't equal to one that
  doesn't.
- **`label`** is what a person calls one, where the category isn't: an app splits a category by how a name is read
  (a good in the deposit where the fleet is), so `Name('good_in_deposit', scope='fleet', label='ore')` is refused as
  `no ore 'lab'`, written `--ore <ore>` and described as `an ore`. It's words, with no `<`, `>` or `|`. Its
  **term**, `kind.term`, is the label, or else the category: what refusals, usages and help say. The category stays
  the key resolvers are given by, and a schema's `x-kind` ([`doc/json_schema.md`](doc/json_schema.md)).

## `Pairs`

`parsed.kinds.Pairs(category, scope=None, *, label=None)` reads a `keyed` field's words as `key value` pairs, said
as the rest of the line: a routine's variables.

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

`Name` and `Pairs` are both `parsed.kinds.Named`: a category, a scope, and a label, its term the label or the
category. A pair's key is refused by its term (`no variable 'hme'`).

## `Line`

`parsed.kinds.Line()` reads the rest of a line as typed, from its first word: a line one command passes on to
another, its flags, parsed's own, `--` and `then` among it, quotes and escapes kept, so it reads there as it was
said.

```python
@parsed.parsed
class See(Verb):
    PHRASE = 'see {line**}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'line': parsed.kinds.Line()}

    line: str = parsed.Str(required=True, doc="the app's line")
```

| The line | `line` | The command's |
|---|---|---|
| `see fleet f1 buy ship hauler --yes` | `fleet f1 buy ship hauler --yes` | |
| `see --pretty fleet f1 show --until docked=true` | `fleet f1 show --until docked=true` | `--pretty` |
| `--yes see fleet f1 --help` | `fleet f1 --help` | `--yes` |
| `session run -- fleet f1 --x` | `fleet f1 --x` | |

- **It starts at its first word,** as argparse's `REMAINDER` does: a flag before it is the command's own, parsed's
  among them, so a command that passes a line on may take flags of its own, said first (`see [--pretty] <line …>`),
  and `see --help` is its own help. `--` before it ends the command's flags: `see -- --x` passes `--x` on.
- **Declared where it fits:** a `Str` of one value, said as the rest of each phrase (`{line**}`), on a command that
  isn't a chain's step, since it takes `then` too. Anywhere else, the command is refused.
- **How it's read** ([`_walk/_walker.md`](_walk/_walker.md#a-line-passed-on)): before a line's flags are split, the
  walk follows its words to see whether they enter a `Line` slot, and there the rest is the slot's one word. A tree
  with none reads as ever.
- **Written back,** it's said as it is, after the command's flags ([`_walk/_render.md`](_walk/_render.md));
  completion offers nothing within it, since it's another app's.

## The default kinds

`Word`, `Number`, `Switch`, `Choice`, `Duration` and `Moment` are `parsed.kinds.*`, beside `Kind`, the base of
every kind. Each is plain data, compared by value. Only `Kind` and `Name` are on parsed's root, since seared's field
types (`parsed.Path`, `parsed.Enum`) take the plainer names there.
