# `effect.py`: what running a command does

A command declares its effect as `EFFECT`, a `parsed.Effect` or its name (`parsed.effect.EffectName`, the type
`Literal['read', 'write', 'action']`). It's optional, never inferred, and inherited, so a base can declare it for
every command beneath it.

```python
@parsed.parsed
class FleetsShow(parsed.Command):
    PHRASE = 'fleets show {fleet}'
    EFFECT = parsed.Effect.READ                     # or by name: EFFECT = 'read'

    fleet: str = parsed.Str(required=True)
```

## The vocabulary

The vocabulary is zeared's, value for value and in the same order, so a command and a zeared contract are judged on
one scale. parsed keeps its own copy, since it never imports zeared.

| Effect | Means | Safe to repeat | HTTP analogue |
|---|---|---|---|
| `READ` | changes nothing a caller could observe | yes | `GET` |
| `WRITE` | changes state, but twice leaves the same state as once | yes, the same state | `PUT`, `DELETE` |
| `ACTION` | anything else: repeating it repeats the effect, or the effect leaves the system | no | `POST` |

- **Incidental effects** (logging, metrics, caches, audit records) don't count.
- **A command that may do several things** declares the strongest, so the declaration is an upper bound.
- **Asking first is a separate matter** (`ASKS`): a command that asks may still be a `WRITE`.

## Order

`READ < WRITE < ACTION`: the order ranks how much care a caller owes before running a command, not the strings'
order. `max()` of several effects is the strongest. An effect name (`'read'`) compares as its member; any other
operand raises `TypeError`, rather than falling back to string order, in which `'action' < 'read'`.

## `effect_of(cls)`

`parsed.effect_of(cls)` reads `cls.EFFECT`, inherited like any attribute, so it works on any class:

- `None` when nothing declares one: unknown, never a guess;
- an `Effect` member, a name normalised to its member;
- `ValueError` for a name that isn't one, `TypeError` for anything else, each naming the class.

A command's [`declaration`](command.md#declarationcls) uses it, and turns either error into a `DeclarationError`.
