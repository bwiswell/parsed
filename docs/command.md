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

`parsed.command.declaration(cls)` reads a class's constants once, checks each, and returns its `Declaration`: the
class, its phrase (`None` for a base), its extra phrases, its effect (a name normalised to its member), `asks`,
`interactive`, `polymorphic`, `instead`, `reply`, and its merged `kinds`, read-only. `is_command` says whether it
has a phrase. The result is kept on the class itself, so there's no registry beside it.

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
