# `errors.py`: what can go wrong

Every error parsed raises is a `parsed.ParsedError`. A line that doesn't read is one error, a `ReadError`,
whichever part refused it: the walk, a field's kind, or seared, whose `ValidationError` comes back as the word that
gave the value. A command for a person at a terminal, run with none, is a `RefusedError`.

| Error | Raised when |
|---|---|
| `ParsedError` | the base of every error below |
| `DeclarationError` | a command, a tree or an app is declared in a way parsed can't use ([`command.md`](command.md), [`tree.md`](tree.md#what-the-build-refuses), [`app.md`](app.md#what-it-refuses)): it names the class or the mount and what's wrong, and says how to put it right. It's a `TypeError` too, as a mistake in a class's definition is in Python |
| `TimedOutError` | a wait whose bound passed before its reply met every condition ([`wait.md`](wait.md#waiting)): `fleets show {fleet}: docked=true not met within 30s`, with its last `reply` and how long it `waited`. `session.call` raises it; `session.run` makes it the result's `timeout`, exit 7. It's a `TimeoutError` too |
| `RefusedError` | a line refused before it runs: a command for a person at a terminal (`INTERACTIVE`), run with none ([`app.md`](app.md#a-person-at-a-terminal)): ``ship {ship} fit is for a person at a terminal: say `ships make <ship> add <part>` instead``, with its `line` and what's said `instead`, if anything. `to_json()` gives `error` (`refused`), `message`, `line`, and `instead` where there's one. `session.call` raises it; `session.run` makes it the result's `refused`, exit 3 |
| `RenderError` | an instance no phrase of its command can say ([`_walk/_render.md`](_walk/_render.md)): a value holding a double quote, one the app's names don't know, or a class that isn't one of the tree's commands. It's a `ValueError` too |
| `ReadError` | a line doesn't read ([`_walk/_walker.md`](_walk/_walker.md#what-it-refuses)): a word no command says, a slot left empty, a flag the command doesn't take, a word its kind can't read. Its message says what's wrong, with the words read up to it. It's a `ValueError` too, as a value Python can't read is |

## `ReadError`

Its message is the text for people: what's wrong, with the words read up to it, then any did-you-mean, then a hint
in backticks (``fleet f1 jump: which system? `fleet f1 jump <system>` ``). The same parts are there as data, for a
front end that renders it its own way:

| Attribute | Holds |
|---|---|
| `message` | the text for people, as `str(error)` |
| `kind` | `'usage'` for a line that doesn't read; `'validation'` for a value seared refuses once it's read |
| `line` | the line read |
| `column` | where on the line it stands, from 0: the word at fault's start, or the line's end where a word is missing |
| `word` | the word at fault, as typed; `None` where one is missing |
| `field` | the field it's for, by attribute name, when the walk knows it |
| `hint` | how to say it, as a line with a `<slot>` for each value: `fleet f1 jump <system>` |
| `suggestions` | what may have been meant: close words or flags, or the words that may come next |

`error.to_json()` gives them as one object, `error` its kind, leaving out the parts it doesn't have:

```json
{"error": "usage", "message": "fleet f1 jump: which system? `fleet f1 jump <system>`",
 "line": "fleet f1 jump", "column": 13, "hint": "fleet f1 jump <system>"}
```

A `'validation'` error's `__cause__` is seared's `ValidationError`.
