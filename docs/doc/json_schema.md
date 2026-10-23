# `doc/json_schema.py`: a command's arguments, as JSON Schema

`json_schema(cls)` is the schema a tool call's arguments fill: seared's load schema for the command's fields
(`mode='load'`), closed as a refusing `load` is (`unevaluatedProperties: false`), each field's bounds, defaults and
docs among it. Its values are the wire's, not the line's words: a span of time in seconds, a share as a number or
`null`.

**On each property read by a name** (a `Name`, or `Pairs`):

| Key | Holds |
|---|---|
| `x-kind` | its category: `fleet`, `station` |
| `x-scope` | the wire name of the field that narrows it, when it has one |

**The command's own**, after its `title` and `description`, each only when the command declares it:

| Key | Holds |
|---|---|
| `x-phrase` | its `PHRASE` |
| `x-extra-phrases` | its `EXTRA_PHRASES` |
| `x-effect` | `read`, `write` or `action` |
| `x-asks`, `x-interactive` | `true` |
| `x-instead` | the phrase of the command an agent says in its place |
| `x-reply` | its reply's class name |

```json
{"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FleetDock",
 "description": "Dock at a station, or at the nearest.",
 "x-phrase": "fleet {fleet} dock {station}", "x-extra-phrases": ["fleet {fleet} dock nearest"], "x-effect": "write",
 "type": "object",
 "properties": {"fleet": {"type": "string", "description": "the fleet", "x-kind": "fleet"},
                "station": {"type": "string", "description": "the station; left out, the nearest",
                            "x-kind": "station", "x-scope": "fleet"}},
 "required": ["fleet"], "unevaluatedProperties": false}
```

Nothing a constrained decoder needs is an `x-` key: they say what the command is, not what the call may hold. The
document is built in one order, so the same command gives the same bytes every time. A class that isn't a command
is refused with a `TypeError`. A chain's schema, its steps as one tool call, is [`chain_schema`](chains.md)'s.
