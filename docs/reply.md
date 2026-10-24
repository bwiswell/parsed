# `reply.py`: what running a line comes to

A handler returns its command's `REPLY` (an instance of the seared class it declares), text, or nothing; or, to ask
before it acts, a `parsed.Ask`. `await session.run(line)` gives what came of the line as a `parsed.Result`: one
envelope, the same for every parsed app, however the line went ([`app.md`](app.md#sessions)).

| Attribute | Holds |
|---|---|
| `line` | the line run, as read: a session's subject's words before it, where one was tried ([`app.md`](app.md#subjects)) |
| `command` | the phrase that said it, after its mount's prefix: `'relay run'`, `'fleet {fleet} mine'`; `None` when it doesn't read |
| `ok` | whether it went well |
| `done` | whether its handler ran for real: to its end, not for a dry run (`--dry-run`), to answer `--help`, or to stop at a question |
| `asks` | the question it stopped at, unanswered or answered no; `None` if none |
| `met` | for a line that waits (`--until`), whether its reply met every condition ([`wait.md`](wait.md)); `None` for one that doesn't |
| `waited` | for a line that waits, how long it waited, in seconds; `None` for one that doesn't |
| `reply` | the `REPLY` its handler returned, or `None` |
| `text` | for people: the reply's `str()`, the text its handler returned, the command's usage for `--help`, the question it stopped at, or the error's message |
| `error` | what went wrong, as data, `{'error': kind, 'message': …}` and its parts; `None` if nothing did |
| `exception` | the exception behind the error, for a program that wants it; never written out, and left out of comparisons |
| `code` | the exit code (a property) |

**A reply's text is its `str()`.** A reply class may define `__str__`, which seared leaves free; without one,
Python falls back to seared's `__repr__` (`FleetView(fleet='f1', docked=True)`). A handler whose text needs the
app's state (a width, a mirror) returns the text itself.

## Errors and exit codes

| `error` | When | `code` |
|---|---|---|
| none | it went well; for `--help`, or a question it stopped at, too | `0` |
| `usage` | the line doesn't read: the `ReadError`'s own data, with its line, column, word, hint and suggestions | `2` |
| `refused` | a command for a person at a terminal, run with none ([`app.md`](app.md#a-person-at-a-terminal)): the `RefusedError`'s own data, with its line, and `instead` (what's said in its place) where the command declares one | `3` |
| `validation` | a value its field refuses: the `ReadError`'s own data, with the field | `4` |
| `timeout` | a wait whose bound passed before its reply met every condition: `{'error': 'timeout', 'message': 'fleets show f1: docked=true not met within 30s'}`, its reply the last read | `7` |
| `handler` | its handler raised, has no binding, or returned something besides its `REPLY`, text or nothing (a waited-on one, besides its `REPLY`): `{'error': 'handler', 'message': "KeyError: 'nope'"}` | `1` |

The codes are `tooled`'s where the meanings match. A handler's failure is never silent: its message names the
exception, and the exception itself is kept as `result.exception`.

## Asking first

A handler that may cost something asks before it acts, in two phases: it returns `parsed.Ask(question, then)`,
having done nothing yet, and `then` acts once the question is answered yes.

```python
def buy(command: FleetBuyShip, ctx: parsed.Context[Hangar]) -> parsed.Ask:
    price = ctx.state.price(command.hull)

    def bought() -> str:
        ctx.state.buy(command.fleet, command.hull)
        return f'{command.fleet} bought a {command.hull}'

    return parsed.Ask(f'Buy a {command.hull} for {price:,} credits?', bought)
```

- **`then`** is a callable of nothing, sync or async, returning what a handler returns: its `REPLY`, text, nothing,
  or another `Ask`, asked in turn.
- **`--yes`** on the line answers every question yes, on any command, whether or not it declares `ASKS`; `yes=True`
  to `run`, `call` or `app.run` does the same. `ASKS` only says ahead of time that a command may ask, and its usage
  ends with `[--yes]`.
- **Else the session's `answer`** is asked, if it has one: yes or no from the question, sync or async.
  `parsed.reply.terminal(question)` is one for a person at a terminal: `question [y/N]`, yes for `y` or `yes`, case
  aside, and no for anything else, or the end of input.
- **A question left unanswered, or answered no,** leaves the line undone: its result's `asks` holds the question,
  `done` is false, and its exit code is `0`. An agent's tooling sees the question and nothing done, and says
  `--yes` to go on.

An `Ask` whose question isn't a sentence, or whose `then` isn't callable, is refused with a `TypeError`.

## As JSON

`result.to_json()` is the envelope as `--json` writes it, every key always there, the reply dumped as seared
writes it:

```json
{"command": "fleets show {fleet}", "line": "fleets show f1", "ok": true, "done": true, "asks": null,
 "met": null, "waited": null, "reply": {"fleet": "f1", "docked": true}, "text": "FleetView(fleet='f1', docked=True)",
 "error": null}
```

`parsed.reply.CODES` maps each error kind to its exit code.
