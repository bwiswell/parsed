# `reply.py`: what running a line comes to

A handler returns its command's `REPLY` (an instance of the seared class it declares), text, or nothing.
`await session.run(line)` gives what came of the line as a `parsed.Result`: one envelope, the same for every parsed
app, however the line went ([`app.md`](app.md#sessions)).

| Attribute | Holds |
|---|---|
| `line` | the line run |
| `command` | the phrase that said it, after its mount's prefix: `'relay run'`, `'fleet {fleet} mine'`; `None` when it doesn't read |
| `ok` | whether it went well |
| `done` | whether its handler ran for real: to its end, not for a dry run (`--dry-run`) or to answer `--help` |
| `reply` | the `REPLY` its handler returned, or `None` |
| `text` | for people: the reply's `str()`, the text its handler returned, the command's usage for `--help`, or the error's message |
| `error` | what went wrong, as data, `{'error': kind, 'message': …}` and its parts; `None` if nothing did |
| `exception` | the exception behind the error, for a program that wants it; never written out, and left out of comparisons |
| `code` | the exit code (a property) |

**A reply's text is its `str()`.** A reply class may define `__str__`, which seared leaves free; without one,
Python falls back to seared's `__repr__` (`FleetView(fleet='f1', docked=True)`). A handler whose text needs the
app's state (a width, a mirror) returns the text itself.

## Errors and exit codes

| `error` | When | `code` |
|---|---|---|
| none | it went well; for `--help` too | `0` |
| `usage` | the line doesn't read: the `ReadError`'s own data, with its line, column, word, hint and suggestions | `2` |
| `validation` | a value its field refuses: the `ReadError`'s own data, with the field | `4` |
| `handler` | its handler raised, has no binding, or returned something besides its `REPLY`, text or nothing: `{'error': 'handler', 'message': "KeyError: 'nope'"}` | `1` |

The codes are `tooled`'s where the meanings match. A handler's failure is never silent: its message names the
exception, and the exception itself is kept as `result.exception`.

## As JSON

`result.to_json()` is the envelope as `--json` writes it, every key always there, the reply dumped as seared
writes it:

```json
{"command": "fleets show {fleet}", "line": "fleets show f1", "ok": true, "done": true,
 "reply": {"fleet": "f1", "docked": true}, "text": "FleetView(fleet='f1', docked=True)", "error": null}
```

`parsed.reply.CODES` maps each error kind to its exit code.
