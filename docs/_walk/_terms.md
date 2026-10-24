# `_walk/_terms.py`: the walk's terms

What the walk reads by, and the tree builds by too: parsed's own flags, the word that joins a chain, what a slot
takes, and whether a flag takes a value. [`tree.md`](../tree.md) gives them on `parsed.tree`, beside `Reading` and
`Completion`.

| Name | Holds |
|---|---|
| `RESERVED` | `('help', 'json', 'yes', 'dry-run')`: the flags parsed takes for itself on every command, which no field may be named for ([`tree.md`](../tree.md#flags)) |
| `HELP`, `HELP_SHORT` | `'help'` and `'h'`: the flag that asks for help, and its short form, which no `SHORTS` may take |
| `JSON` | `'json'`: the flag that asks for what came of a line as its envelope, a line of JSON ([`app.md`](../app.md)) |
| `THEN` | `'then'`: the word that joins a chain's steps on a line, read case aside and never quoted |

**`SlotKind`**, a `StrEnum`, is what a slot takes, as a tree's node holds it and the build checks that one node
takes one kind:

| Member | Takes |
|---|---|
| `ONE` | one word: `{fleet}` |
| `MANY` | one word or more, until a literal after them or the end: `{goods}`, a list's field |
| `REST` | the rest of the line: `{message**}` |

**`Arity`**, a `StrEnum`, is whether a flag takes a value, as `Tree.flags` says it across a tree, since the walk
splits flags off before it knows the command:

| Member | Is |
|---|---|
| `SWITCH` | given or not: `--loud` |
| `VALUE` | the word after it, or after `=`: `--for 10m`, `--for=10m` |
