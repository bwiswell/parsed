# `doc/check.py`: `parsed check`, a package's commands checked in its CI

```sh
uv run python -m parsed check farm.commands
```

`python -m parsed check <target> …` builds the tree of every command in the targets (modules or packages, by name,
as `Tree.collect` takes them) and checks each command, as `tooled check --no-resolve` checks a protocol in its CI.

## What it checks

| Check | Passes when |
|---|---|
| `tree` | the tree builds (every phrase reads and binds, no two read a line two ways, every flag means one thing), and the targets hold a command |
| `round-trip` | two instances made from the command's fields, one with only its required fields and one with every field it can give, each render to a line that reads back to it |
| `example` | each line of its `EXAMPLES` reads to it, and a line with no placeholder loads too |
| `schema` | `json_schema` builds, takes the command's example, holds as a constrained decoder needs it to, and stays compact |

**The instances are made from each field's type and constraints,** with no generator beside: a string `example`
(or the first of a few words its lengths and pattern take), a number `1` moved into its bounds, a switch the other
way from its default, an `Enum`'s first member, a span of ten minutes, a list of one, a pair `key` and its value.
A command whose required field takes none of them (a pattern no word fits) has no round trips, and is listed under
`skipped` with that field. Its examples and its schema are still checked, so an `EXAMPLES` line covers it.

**An example's `<name>` stands for any value,** as help writes one (`fleet <fleet> mine --for <for>`): the walk
reads it by no kind and no resolver ([`_walk/_walker.md`](../_walk/_walker.md#placeholders)), and the line must end
at the command whose example it is. A line with no placeholder is loaded too, so its values keep their bounds:
`log 0` is refused where `log {n}` has `ge=1`.

**A schema holds as a constrained decoder needs it to** for filling a tool call's arguments:

- it's a closed object (`unevaluatedProperties: false`);
- each `enum` is a list of distinct JSON scalars, and a field of an `Enum`'s choices has one;
- it takes its example: the instance with every field it can give, dumped, has only keys the schema names and each
  it requires, and loads back to that instance;
- it stays compact: at most `--max-schema-bytes` (2048 by default), written with no spaces.

## The report

The report is JSON on stdout:

```json
{
  "targets": ["farm.commands"],
  "ok": false,
  "commands": 3,
  "checked": {"round-trips": 4, "examples": 5, "schemas": 3},
  "skipped": {},
  "problems": [
    {"check": "example", "command": "farm.commands.Mine", "line": "mien <fleet>",
     "message": "no command 'mien'; did you mean mine?"}
  ]
}
```

Each problem has its `check`, its `command` by module and name (none for the tree's own), the `line` at fault where
there's one, and a `message`.

| Exit | When |
|---|---|
| `0` | every check passed |
| `1` | a problem, in the report |
| `2` | a usage that doesn't read, or a target that doesn't import: `{"error": "usage", "message": …}` on stderr |

**From Python,** `parsed.doc.check(targets, max_schema_bytes=2048)` gives the same as a `CheckReport`: `ok`, the
counts, `skipped`, `problems` and `to_json()`. It raises `ImportError` for a target that doesn't import. Each
problem is a `Problem`: `check`, `message`, `command` and `line`.
