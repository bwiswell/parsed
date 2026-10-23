# `command.py`: commands, and what they declare

A command is a seared class: a subclass of `parsed.Command`, decorated with `@parsed.parsed` (seared's decorator,
renamed). Its fields are what it takes. Its class constants say the rest, as a zeared message's `TOPIC` and
`EFFECT` do:

```python
from datetime import timedelta

import parsed


@parsed.parsed
class FleetCommand(parsed.Command):
    EFFECT = parsed.Effect.WRITE                    # every command beneath it writes, unless it says otherwise

    fleet: str = parsed.Str(required=True, doc='the fleet')


@parsed.parsed
class FleetMine(FleetCommand):
    """Mine until the hold is full."""

    PHRASE = 'fleet {fleet} mine'

    for_: timedelta | None = parsed.TimeDelta(data_key='for', default=None, doc='stop after this long')
```

## The constants

| Constant | Default | What it says |
|---|---|---|
| `PHRASE` | `None` | the words that say it (`'fleet {fleet} mine'`). A class without one is a base, not a command |
| `EXTRA_PHRASES` | `()` | other phrases that say it too, as a tuple |
| `EFFECT` | `None` | what running it does: `parsed.Effect.READ`, `WRITE` or `ACTION`, or its name ([`effect.md`](effect.md)) |
| `ASKS` | `False` | whether it may ask before it acts ([`reply.md`](reply.md#asking-first)): said ahead of time, for help and an agent's tooling; asking doesn't need it |
| `INTERACTIVE` | `False` | whether it's only for a person at the client: an editor, a viewer |
| `POLYMORPHIC` | `None` | whether a phrase says a slot by an alias; when declared, it's checked |
| `INSTEAD` | `None` | on an interactive command, the command an agent says in its place |
| `REPLY` | `None` | the seared class its handler returns |
| `KINDS` | empty | how a field's words are read, by field name ([`kinds.md`](kinds.md)) |
| `ALIASES` | empty | other names a phrase's slot may fill a field by, slot name to field name: `{'detachment': 'fleet'}` |
| `EXAMPLES` | `()` | lines that say it, for help and for `parsed check` to read; a `<name>` stands for any value |
| `STEPS` | `False` | on a chain's base: the commands beneath it are steps, which `then` joins on a line ([chains](#chains)) |
| `MOVES` | `False` | on a step: where it takes its chain, the field that says so (`'to'`), or `True` for somewhere the line doesn't say ([a chain's place](#a-chains-place)) |

- **Every constant but `PHRASE` is optional, and none is inferred.** A command declares what it knows; nothing is
  required for one tool or another's sake.
- **Each is inherited** like any class attribute, so a base can declare one for every command beneath it. `KINDS`
  and `ALIASES` are merged along the bases instead: a base's entries and its subclasses' all count, a subclass's
  winning where they share a key.
- **Annotate a mutable constant as a `ClassVar`** (`KINDS: ClassVar[dict[str, …]] = {…}`), as ruff's RUF012 asks.
  seared never takes a `ClassVar` for a field.

## Phrases

A phrase is words separated by spaces, each a literal word or a slot ([`_phrase/_grammar.md`](_phrase/_grammar.md)):

- **a word** is said as it is: lowercase letters, digits, `-` and `_`;
- **`{name}`** is one field's value, as zeared writes a topic's slot;
- **`{name**}`** is the rest of the line, so it comes last.

A phrase begins with a word, and names each slot once.

**`PHRASE` binds each slot to the field it names, or its alias gives:** that field is a positional, and every
other field is a flag ([`_phrase/_binding.md`](_phrase/_binding.md)). A slot whose field isn't `required` is
optional, and a `many` field's slot takes several words; either is followed by a word or ends the phrase, so a line
reads one way.

**`EXTRA_PHRASES` say the same command another way:**

- **another wording** takes `PHRASE`'s slots, in any order, and may leave one out, whose field keeps its default:

  ```python
  PHRASE = 'fleet {fleet} dock {station}'
  EXTRA_PHRASES = ('fleet {fleet} dock nearest',)     # station keeps its default, None: the nearest
  ```

- **a polymorphic twin** says a slot by an alias: `ALIASES` gives a slot's name the field it fills, usually once,
  on a base, and the slot reads by its own `KINDS` entry if it has one, else by its field's kind. A slot binds by
  name, so a twin may leave out an optional slot too:

  ```python
  class FleetCommand(parsed.Command):
      KINDS: ClassVar[dict[str, parsed.Kind]] = {'fleet': parsed.Name('fleet'), 'detachment': parsed.Name('detachment')}
      ALIASES: ClassVar[dict[str, str]] = {'detachment': 'fleet'}

  PHRASE = 'fleet {fleet} mine'
  EXTRA_PHRASES = ('detachment {detachment} mine',)  # fills `fleet`, read by KINDS['detachment']
  ```

  `PHRASE` may say one too: a detachment's own `rejoin` is `PHRASE = 'detachment {detachment} rejoin'`.
  `POLYMORPHIC` needn't be declared for any of this. Declared, it's checked both ways: `True` refuses a class whose
  phrases say no slot by an alias, and `False` one that does.

**`EXAMPLES` are lines that say it,** for help, generated pages and an app's skill text: whole lines, a `<name>`
standing for any value where a real one would date.

```python
EXAMPLES = ('fleet <fleet> mine', 'fleet prospector mine --for 1h30m')
```

A declaration keeps them as given, as it has no tree to read them with; [`parsed check`](doc/check.md) reads each
one, so an example can't rot unnoticed. A subclass inherits a base's lines as it does any constant, and the check
reads them as its own, so a subclass with a phrase of its own gives its own.

## Chains

**A chain's base declares `STEPS = True`,** and every command beneath it is a step: a line says several, joined by
`then`, and they run as one order ([`tree.md`](tree.md#chains), [`app.md`](app.md#chains)):

```python
@parsed.parsed
class FleetCommand(parsed.Command):
    STEPS = True
    fleet: str = parsed.Str(required=True)

# fleet prospector jump sol then move belt then mine
```

- **A command beneath it that isn't a step** declares `STEPS = False`, as any constant can be overridden: a
  setting, or a purchase that asks first.
- **The base's own fields are the chain's shared fields:** the first step says them, and every step gets them.
- **`STEPS = True` goes on a base,** a class without a `PHRASE`: on a command, it's refused.

### A chain's place

**A step that takes its chain somewhere declares `MOVES`:** the field that says where, so a later step's names are
looked for where the fleet will be, not where it is:

```python
@parsed.parsed
class FleetJump(FleetCommand):
    PHRASE = 'fleet {fleet} jump {system}'
    MOVES = 'system'
    system: str = parsed.Str(required=True)

@parsed.parsed
class FleetDock(FleetCommand):
    PHRASE = 'fleet {fleet} dock {station}'
    MOVES = 'station'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'station': parsed.Name('station', scope='fleet', follows=True)}
    station: str | None = parsed.Str(default=None)

# fleet prospector jump sol then dock ceres: ceres looked for in sol
```

- **`MOVES` names a field of the step's own,** of one value (a slot or a flag): after the step, the chain is where
  that field's value says, its key as its resolver read it. Left out (`dock nearest`), the step takes it somewhere
  the line doesn't say: a default isn't the line's.
- **`MOVES = True`** is a step that goes somewhere the line doesn't say (`jump nearest iron`). A step that declares
  neither leaves the chain where it was.
- **A name follows the chain** where its kind says `follows=True` ([`kinds.md`](kinds.md#name)): its scope is one
  of the chain's shared fields, the fleet, and in a later step, once a step before it has moved the chain, the
  resolver is given where it moved to instead ([`names.md`](names.md#a-chains-place)). Where the chain went
  somewhere the line doesn't say, it's given no scope. A name whose scope doesn't follow (the fleet's hold) keeps
  its field's.

## Bases

A subclass of `Command` without a `PHRASE` is a base. It can carry fields and constants for the commands beneath
it. **A base that declares fields must be decorated too:** seared drops an undecorated base's fields from its
subclasses without a word, so parsed refuses a command beneath such a base, naming it. A base without fields of its
own (one that only sets `EFFECT`, say) needn't be.

**Every field needs an annotation,** as a dataclass's does: seared leaves out a field without one, on any class, so
parsed refuses it and suggests one (`hours: float = …`).

**A command can inherit a protocol's request class,** a plain seared class, so its fields and their bounds are the
protocol's own rather than copied:

```python
@parsed.parsed
class HandheldConnect(parsed.Command, HandheldEndpoint):   # HandheldEndpoint: the protocol's request
    PHRASE = 'handheld connect {source} {reader_id}'
    EFFECT = parsed.Effect.WRITE
```

## `declaration(cls)`

`parsed.command.declaration(cls)` reads a class's constants once, checks each, and returns its `Declaration`:

- the class, its phrase (`None` for a base) and its extra phrases;
- its effect (a name normalised to its member), `asks`, `interactive`, `polymorphic`, `instead` and `reply`;
- `chain`: for a step, its chain's base, the nearest class above it declaring `STEPS = True`; `None` otherwise;
- `moves`: where a step takes its chain, its `MOVES`: a field's name, `True`, or `False`;
- its merged `kinds` and `aliases`, read-only, and `field_kinds`: each field's kind, its entry or its type's
  default;
- `phrases`: `PHRASE` and each extra phrase, bound, each slot to the field it fills;
- `flags`: the fields no slot of `PHRASE` names.

`is_command` says whether it has a phrase, `can_wait` whether a line may wait on it (a read with a `REPLY`:
[`wait.md`](wait.md)), and `kind_of(place)` the kind a slot reads by: a slot by an alias's own
entry, if it has one, else its field's. The result is kept on the class itself, so there's no registry beside
it. `parsed.command.is_chain_base(cls)` says whether a class is a chain's base.

What's wrong is a `DeclarationError`, a `ParsedError` and a `TypeError`, naming the class, the constant and how to
put it right:

| Declared | Refused because |
|---|---|
| a `PHRASE` that's empty, or not a string | a phrase is a string of words |
| `EXTRA_PHRASES = 'go on'` | a tuple of phrases; one alone needs a trailing comma |
| `EXTRA_PHRASES` on a base | a base has no phrases |
| `EXAMPLES = 'fleet f1 mine'`, or a line that's empty | a tuple of lines; one alone needs a trailing comma |
| `EXAMPLES` on a base | a base says nothing |
| `STEPS = True` on a command, or inherited from one | it goes on a chain's base, a class without a `PHRASE` |
| `STEPS` not `True` or `False` | |
| `MOVES` on a command that isn't a step | it says where a step takes its chain |
| `MOVES` naming no field, one of the chain's shared fields, or a field of several values | it names a field of the step's own, of one value: a chain is in one place |
| `MOVES` not a field's name, `True` or `False` | |
| a name that follows its chain on a command that isn't a step, or scoped by a field the chain doesn't share | it follows a field the chain shares, along its steps |
| `EFFECT = 'reed'` | expected one of read, write, action |
| `ASKS` or `INTERACTIVE` not `True` or `False`; `POLYMORPHIC` not either or left out | |
| `INSTEAD` on a command that isn't interactive, naming itself, a base or a non-command, or another interactive command | it names a form an agent can use, in place of an interactive command |
| a `REPLY` that isn't a decorated seared class | |
| `KINDS` that isn't a mapping, or a key that isn't a field name | |
| a command with a `PHRASE`, not decorated | decorate it with `@parsed.parsed` |
| a base that declares fields, not decorated | seared would drop them |
| a field without an annotation, on the command, a base or a request class it inherits | seared would leave it out; add an annotation (`hours: float = …`) |
| a phrase that doesn't read (`'Mine'`, `'{fleet} mine'`, a slot twice, `{rest**}` not last) | the message says which part, and why |
| a slot that names no field and none of `ALIASES` | it lists the fields and the aliases |
| an alias to no field, an alias that's a field's own name, or two slots of one phrase for one field | |
| an optional or `many` slot followed straight by another slot | a line would read two ways |
| an extra phrase with a slot that's a flag in `PHRASE`, or written as the rest of the line in one and not the other | |
| an extra phrase that leaves out a required slot | give the field a default, or keep the slot |
| `ALIASES` that isn't a mapping of slot names to field names | |
| `POLYMORPHIC = True` and no slot said by an alias, or `False` and one | |
| an entry of a command's own `KINDS` that names no field and none of its aliases | a typo; a base's entries may go unused |
| a `KINDS` value that isn't a kind | it names the class that declared it |
| a field whose type has no word form, and no `KINDS` entry | it couldn't be said on a line |
| a `Name` whose `scope` is no other field of the command | |
| scopes that go round (`a` scoped by `b`, `b` by `a`) | a scope is read before the names it narrows |
| a `keyed` field read by any kind but `Pairs`, or `Pairs` reading a field that isn't keyed | a keyed field's words are pairs |
| a `Pairs` field that `PHRASE` doesn't say as the rest of the line | `{variables**}` |
| a literal word that reads to `None`, on a field that isn't `nullable` | seared would drop the `null` |
