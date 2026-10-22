# `doc/introspect.py`: a command, as data

`is_command_class(obj)` says whether `obj` is a command class: a decorated subclass of `Command` with a `PHRASE`.
A base, a reply's class, a protocol's request class and an undecorated subclass aren't.

`introspect_command(cls)` gives its `CommandDoc`, refusing a class that isn't a command with a `TypeError`:

| Attribute | Holds |
|---|---|
| `schema` | seared's `SchemaDoc` of its fields |
| `phrase`, `extra_phrases` | its `PHRASE` and `EXTRA_PHRASES` |
| `slots` | every slot of its phrases, each name once, in the order they first stand: `SlotDoc`s |
| `flags` | its flags, in the order its fields are declared: `FlagDoc`s |
| `kinds` | each field's kind, by attribute name |
| `effect`, `asks`, `interactive`, `polymorphic`, `instead`, `reply` | the constants, as declared; none inferred |
| `fields_from` | the seared classes it takes fields from that aren't commands, nearest first |

A **`SlotDoc`** is a slot's `name` as a phrase writes it (a field's name, or an alias), the `field` it fills, the
`kind` its words read by (an alias's own, or the field's), and whether it's `required`, takes several words (`many`)
or the rest of the line (`rest`). So a polymorphic command's twin shows as a second slot for the same field, read
by its own kind: `detachment`, filling `fleet`, read as a detachment.

A **`FlagDoc`** is a flag's `name` as a line writes it (`for`, `no-stop`), its `field` and `kind`, whether it's a
`switch` (and `negated`), `required`, or a list's (`many`).

**`fields_from`** links a command to the contract it's built on: a command that inherits a protocol's request class
(`class HandheldConnect(parsed.Command, HandheldEndpoint)`) names that class, beside its `reply`, so a tool can tell
a command that overlaps a contract from one that doesn't. Both are plain seared classes, so parsed imports nothing
of the protocol's library.
