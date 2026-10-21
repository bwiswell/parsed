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
| `ASKS` | `False` | whether it may ask before it acts |
| `INTERACTIVE` | `False` | whether it's only for a person at the client: an editor, a viewer |
| `POLYMORPHIC` | `None` | whether its extra phrases rename a slot; when declared, it's checked |
| `INSTEAD` | `None` | on an interactive command, the command an agent says in its place |
| `REPLY` | `None` | the seared class its handler returns |
| `KINDS` | empty | how a field's words are read, by field name |

- **Every constant but `PHRASE` is optional, and none is inferred.** A command declares what it knows; nothing is
  required for one tool or another's sake.
- **Each is inherited** like any class attribute, so a base can declare one for every command beneath it.
- **`KINDS` is merged along the class's bases** instead: a base's entries and its subclasses' all count, and a
  subclass's entry wins where both name a field.
- **Annotate a mutable constant as a `ClassVar`** (`KINDS: ClassVar[dict[str, …]] = {…}`), as ruff's RUF012 asks.
  seared never takes a `ClassVar` for a field.

## Phrases

A phrase is words separated by spaces, each a literal word or a slot ([`_phrase/_grammar.md`](_phrase/_grammar.md)):

- **a word** is said as it is: lowercase letters, digits, `-` and `_`;
- **`{name}`** is one field's value, as zeared writes a topic's slot;
- **`{name**}`** is the rest of the line, so it comes last.

A phrase begins with a word, and names each slot once.

**`PHRASE` binds each slot to the field it names:** that field is a positional, and every other field is a flag
([`_phrase/_binding.md`](_phrase/_binding.md)). A slot whose field isn't `required` is optional, and a `many`
field's slot takes several words; either is followed by a word or ends the phrase, so a line reads one way.

**`EXTRA_PHRASES` say the same command another way:**

- **an alias** takes `PHRASE`'s slots, in any order, and may leave one out, whose field keeps its default:

  ```python
  PHRASE = 'fleet {fleet} dock {station}'
  EXTRA_PHRASES = ('fleet {fleet} dock nearest',)     # station keeps its default, None: the nearest
  ```

- **a polymorphic twin** renames a slot: a slot named after no field fills the field of `PHRASE`'s slot at its
  place, and is read by the `KINDS` entry its name keys. It keeps `PHRASE`'s slots, in their order:

  ```python
  PHRASE = 'fleet {fleet} mine'
  EXTRA_PHRASES = ('detachment {detachment} mine',)  # fills `fleet`, read by KINDS['detachment']
  ```

  `POLYMORPHIC` needn't be declared for this. Declared, it's checked both ways: `True` refuses a class whose extra
  phrases rename nothing, and `False` one that renames a slot.

## Bases

A subclass of `Command` without a `PHRASE` is a base. It can carry fields and constants for the commands beneath
it. **A base that declares fields must be decorated too:** seared drops an undecorated base's fields from its
subclasses without a word, so parsed refuses a command beneath such a base, naming it. A base without fields of its
own (one that only sets `EFFECT`, say) needn't be.

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
- its merged `kinds`, read-only;
- `phrases`: `PHRASE` and each extra phrase, bound, each slot to the field it fills;
- `flags`: the fields no slot of `PHRASE` names.

`is_command` says whether it has a phrase. The result is kept on the class itself, so there's no registry beside
it.

What's wrong is a `DeclarationError`, a `ParsedError` and a `TypeError`, naming the class, the constant and how to
put it right:

| Declared | Refused because |
|---|---|
| a `PHRASE` that's empty, or not a string | a phrase is a string of words |
| `EXTRA_PHRASES = 'go on'` | a tuple of phrases; one alone needs a trailing comma |
| `EXTRA_PHRASES` on a base | a base has no phrases |
| `EFFECT = 'reed'` | expected one of read, write, action |
| `ASKS` or `INTERACTIVE` not `True` or `False`; `POLYMORPHIC` not either or left out | |
| `INSTEAD` on a command that isn't interactive, naming itself, a base or a non-command, or another interactive command | it names a form an agent can use, in place of an interactive command |
| a `REPLY` that isn't a decorated seared class | |
| `KINDS` that isn't a mapping, or a key that isn't a field name | |
| a command with a `PHRASE`, not decorated | decorate it with `@parsed.parsed` |
| a base that declares fields, not decorated | seared would drop them |
| a phrase that doesn't read (`'Mine'`, `'{fleet} mine'`, a slot twice, `{rest**}` not last) | the message says which part, and why |
| a slot of `PHRASE` that names no field | it lists the fields |
| an optional or `many` slot followed straight by another slot | a line would read two ways |
| an extra phrase with a slot that's a flag in `PHRASE`, or written as the rest of the line in one and not the other | |
| an extra phrase that leaves out a required slot | give the field a default, or keep the slot |
| a renamed slot with no `KINDS` entry by its name, a renaming phrase with fewer slots than `PHRASE`, or its others out of order | |
| `POLYMORPHIC = True` and nothing renamed, or `False` and something renamed | |
| an entry of a command's own `KINDS` that names no field and no renamed slot | a typo; a base's entries may go unused |
