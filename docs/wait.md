# `wait.py`: a read that waits on its reply

A command that declares `EFFECT = READ` and a `REPLY` can wait: running a read again is known to be safe, and its
reply has typed values for a condition to read. Such a line takes `--until`, a condition on the reply, and
`--timeout`, how long to wait:

```
fleets show frigate --until docked=true --timeout 2m
```

`declaration(cls).can_wait` says whether a command can, and `tree.waits` whether any of a tree's can.

## Conditions

`--until PATH=VALUE` is a condition in `tooled wait`'s grammar, so an agent learns one:

- **the path** is dotted (`docked`, `cargo.iron`), a whole number stepping into a list (`ships.0.name`);
- **the value** is read as JSON if it reads as JSON (`40`, `true`, `null`, `"30%"`), else as a string (`idle`);
- **several conditions,** each its own `--until`, must all hold.

A condition is met where the reply's wire form, as seared dumps it, holds its value at its path. Values compare as
JSON compares: `40` is `40.0`, and a number is never a boolean (`docked=1` isn't `docked=true`).

**Each path is checked against the reply's dump schema** when the line is read, before anything runs. A path that
names no field is refused, with what may have been meant:

```
--until 'dockd' names no field of FleetView; did you mean 'docked'?
--until 'ships.name' names no field of Board; 'ships' is a list: ships.0.name
```

A map takes any key, and a shape the schema doesn't say (an open object) takes any path.

## The bound

`--timeout` is how long to wait, a span of time as a `Duration` reads one (`90s`, `2m`, `1h30m`); `30s` by default.
It bounds a wait, so it's refused without an `--until`, and given once.

## The flags are a tree's

A line's flags are split off before its command is known, so a flag's name means one thing across a tree. Once
any of its commands can wait, a tree takes `--until` and `--timeout`, each taking a value:

- **a command that can wait** can't take either name for a field (give the field a `data_key`);
- **any other command** may have a field of its own by either name, which then takes it as any flag; a switch by
  either name is refused when the tree is built, since it would mean two things;
- **without a field of its own**, a command that can't wait refuses `--until`, saying why:
  ``fleet f1 mine can't wait: --until is for a read, a command that declares EFFECT = READ and a REPLY``.

## What a line that waits reads to

Its [`Reading`](_walk/_walker.md#reading)'s `wait` is a `Wait`: `until`, its `Condition`s, and `timeout`, in
seconds. `wait.met(reply)` says whether a reply meets every condition.

## Waiting

A [session](app.md#sessions) runs the read, then reads again until its reply meets every condition, or the bound
passes:

- **at once when the app says its state moved:** `session.changed()`, from any thread, wired where the app learns
  of a change (`controls.on_change = session.changed`). A change while a read is under way isn't missed: the wait
  holds the change it was given before the read began;
- **else every `interval` seconds** (`app.open(state, interval=…)`, a second by default). An app that signals every
  change opens with `interval=None`, so a wait reads only on a change, never on a poll.

At the bound it stops, reading again only if a change woke it there. A handler waited on returns its `REPLY`, since
a wait reads its values. Hooks run once around the whole wait, not around each read, and the session stays open for
it, so a wait pays the app's opening once.

## How it ends

| | `session.run` | `session.call` |
|---|---|---|
| met | the reply that met them, `met` true, exit `0` | the reply |
| past the bound | the last reply, `met` false, a `timeout` error, exit `7` | raises `TimedOutError`, its `reply` the last |

Either way, the result's `waited` says how long it waited, in seconds ([`reply.md`](reply.md)). The error names the
command and every condition: `fleets show {fleet}: docked=true not met within 30s`. A timeout is the line's
failure, so the on-error hooks see it, and the after hooks don't run.

With placeholders (`--until <until>`, `--timeout <timeout>`), as an example in help says them, a condition is any
condition and the bound is the default.

| Name | What it is |
|---|---|
| `Condition(path, value, text)` | one `--until`; `Condition.parse(text)`, `find(wire)`, `met(wire)` |
| `Wait(until, timeout)` | a read's wait; `met(reply)` |
| `problem(condition, reply)` | why a condition's path names nothing in a reply class's dump schema, and what may have been meant; `None` when it names a field |
| `FLAGS` | `('until', 'timeout')` |
| `TIMEOUT` | `30.0`, seconds |
