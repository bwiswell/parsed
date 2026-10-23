# `_walk/_route.py`: a line sent to its mount

An [app](../app.md) holds several trees, each mounted under a prefix of words. `Routes` is a trie of those words:
each mount's prefix, then each word its commands may begin with, which leads to the mount. A line's words are
followed from the root until one leads to a mount, and that mount's tree reads the whole line, prefix and all.

```
relay ─┬─ run              → service.cli under 'relay'
       ├─ validate-config  → service.cli under 'relay'
       └─ status           → service.cli under 'relay'
fleet                      → farm.commands at the root
log                        → farm.commands at the root
```

`Routes` holds anything `Mounted`: an object with a `tree` and a `label`, as an app's `Mount` has.

## Adding a mount

`routes.add(mount)` refuses, with a `DeclarationError` naming both mounts, a mount that would make a line read two
ways:

| Refused | The message |
|---|---|
| a word that begins a command in two mounts at one prefix | `relay and other both say 'relay run'` |
| a prefix that runs through a word of another mount's | `logs is mounted where farm says 'fleet'` |
| a first word where other mounts stand | `rio says 'rio', where gateway is mounted` |
| a tree with no commands | `empty has no commands to mount` |

Nothing is added when a mount is refused. Two mounts may share a prefix, as long as no word begins a command in
both.

## Routing a line

`routes.route(line)` follows the line's words, case aside, never a quoted one, to its mount. parsed's own flags
(`--yes`, `--json`, …) are passed over; any other flag, or `--`, ends the words, since only a mount's tree knows
whether a flag takes a value. A line that reaches no mount is a `ReadError`, as the walk makes one:

| The line | The refusal |
|---|---|
| empty | `no command: the line has no words`, suggesting every first word |
| a flag first | `--yes comes before a command: a flag follows the first word` |
| a word no mount says there | `no command 'rela'; did you mean relay?`, or the words that may come there |
| ending, or reaching a flag, at a prefix | `relay: then what? run \| validate-config \| status` |

## How far words go

For a session's subjects ([`app.md`](../app.md#subjects)): `routes.begins(token)` says whether a word begins a
line, the first word of a mount's prefix or of a command at the root, case aside, never a quoted one; and
`routes.reach(tokens)` how far words go: the mount they reach, `True` where they stop along a prefix short of one,
or `False` where a word goes nowhere.

## Completing a line

`routes.complete(text)` follows the words before the one being typed. Where they reach a mount, it gives the mount,
whose tree completes the line. Short of one, it gives a `Completion` of the words that may follow, those that begin
with the word being typed; none past a word no mount says, or for a quoted word.
