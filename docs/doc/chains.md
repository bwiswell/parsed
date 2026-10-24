# `doc/chains.py`: a chain as one tool call

A chain's steps ([`command.md`](../command.md#chains)) are one order, so a tool calls them as one: the chain's
shared fields once, and `steps`, each step tagged under `step` (`parsed.doc.chains.TAG`) by its phrase's words after
the shared part, never by a class name:

```json
{"fleet": "f1", "steps": [{"step": "jump", "system": "sol"}, {"step": "move", "to": "sol-belt"}, {"step": "mine"}]}
```

```python
import parsed.doc

parsed.doc.chain_schema(tree, FleetCommand)            # the schema those arguments fill
steps = parsed.doc.load_chain(tree, FleetCommand, call)  # [FleetJump(…), FleetMove(…), FleetMine(…)]
app.render(steps)                                      # 'fleet f1 jump sol then move sol-belt then mine'
parsed.doc.chain_keys(steps, names)                    # ['fleet/f1/jump/sol', 'fleet/f1/move/sol-belt', 'fleet/f1/mine']
parsed.doc.dump_chain(steps)                           # the call again
```

A chain's steps are a tree's: [`tree.chains`](../tree.md#chains) holds each base's steps among its commands, so a
mount's tree holds the steps it was given. Each function takes the tree and the base.

## `introspect_chain(tree, base)`

A `ChainDoc`, refusing a class that isn't a chain's base with steps in the tree with a `TypeError`:

| Attribute | Holds |
|---|---|
| `base` | the chain's base, the class that declares `STEPS = True` |
| `schema` | seared's `SchemaDoc` of the base: the shared fields |
| `shared` | the shared fields, by attribute name, as the base declares them |
| `heads` | the shared parts its steps' phrases say, each once: `fleet {fleet}`, a twin's `detachment {detachment}` |
| `slots` | those parts' slots, each name once: `SlotDoc`s ([`introspect.md`](introspect.md)) |
| `steps` | each step, in the tree's order: `StepDoc`s |
| `effect` | the strongest of its steps' effects; `None` where any step declares none, since none is inferred |
| `asks` | whether any step may ask before it acts |

A **`StepDoc`** is a step's `tag`, its `PHRASE`'s words after the shared part (`jump`, `jump nearest`); its
`phrase` from there, slots and all (`jump {system}`); and its `command`, the step's `CommandDoc`, with its own keys,
effect, kinds, and its `chain` and `moves`.

## `chain_schema(tree, base)`

The JSON Schema a tool call of the chain fills, built in one order, so the same chain gives the same bytes:

- **the shared fields** at the top, as the steps' own schemas have them, `x-kind` and all;
- **`steps`**, an array of one step or more, each item `anyOf` the steps' branches, which constrained decoders hold;
- **a step's branch** is its command's schema ([`json_schema.md`](json_schema.md)) without the shared fields: its
  description, its tag as a `const` first, its own properties, closed (`unevaluatedProperties: false`). Its classes'
  definitions go under the root's `$defs`;
- **the chain's own,** after its title (the base's name) and description: `x-effect`, its strongest step's, and
  `x-asks` where any step asks.

On a step's branch, where a step declares them:

| Key | Holds |
|---|---|
| `x-moves` | the wire name of the field that moves the chain on (`system`), or `true` for somewhere the line doesn't say |
| `x-asks` | `true` |
| `x-follows` | on a property: `true`, for a name looked for where the chain will be by then |

```json
{"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "FleetCommand", "x-effect": "write",
 "type": "object",
 "properties": {"fleet": {"type": "string", "description": "the fleet", "x-kind": "fleet"},
                "steps": {"type": "array", "description": "the steps, in order", "minItems": 1,
                          "items": {"anyOf": [
                            {"description": "Jump to a system.", "x-moves": "system", "type": "object",
                             "properties": {"step": {"const": "jump"},
                                            "system": {"type": "string", "description": "the system",
                                                       "x-kind": "system"}},
                             "required": ["step", "system"], "unevaluatedProperties": false},
                            …]}}},
 "required": ["fleet", "steps"], "unevaluatedProperties": false}
```

## `load_chain(tree, base, data)` and `dump_chain(steps)`

`load_chain` reads a call to its steps' instances, each loaded by seared with the shared fields, every key checked
as a refusing `load` checks them. A call that isn't one raises seared's `ValidationError`, its path the key at
fault:

| Given | Refused |
|---|---|
| no `steps`, or none in it | `FleetCommand.steps: required key missing`; `… expected a list of steps, one at least` |
| a key the chain doesn't take | `FleetCommand.x: unknown key` |
| a step with no tag, or one the chain hasn't | `FleetCommand.steps[1].step: no step 'fly': one of mine, dock, jump, …` |
| a shared field inside a step | `FleetCommand.steps[0].fleet: a chain's shared field, given once, at the top` |
| a value its step's field refuses | `FleetCommand.steps[0].for: cannot deserialize 'soon' as timedelta` |

`dump_chain` writes steps back as a call, the shared fields once and each step's own as seared dumps them. Steps
that aren't one chain's are a `TypeError`, and steps that don't share its fields' values a `ValueError`.

## What's refused

Each is a `DeclarationError`, when the doc or the schema is built. A tree that only reads lines is never held to
them, as a tool call is a tool's need, not the line's:

| Declared | Refused because |
|---|---|
| two steps whose phrases say the same words after their shared parts | a tool call tells a chain's steps by them |
| a step whose `PHRASE` says no words after the shared part | |
| a step field on `step`, or a shared field on `steps` | they're the call's own keys |

[`parsed check`](check.md) round-trips each chain, through its line and through its schema.
