# `errors.py`: what can go wrong

Every error parsed raises is a `parsed.ParsedError`. A line that doesn't read is one error, a `ReadError`,
whichever part refused it: the walk, a field's kind, or seared, whose `ValidationError` comes back as the word that
gave the value.

| Error | Raised when |
|---|---|
| `ParsedError` | the base of every error below |
| `DeclarationError` | a command is declared in a way parsed can't use ([`command.md`](command.md)): it names the class and the constant, and says how to put it right. It's a `TypeError` too, as a mistake in a class's definition is in Python |
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
