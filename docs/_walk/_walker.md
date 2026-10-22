# `_walk/_walker.py`: a line, walked

`walk(tree, line)` reads a line by a [`Tree`](../tree.md) to a `Reading`, in two steps: the flags split off, then
the words walked from the root. `Tree.walk(line)` calls it.

## The flags first

A word that begins with `--`, outside quotes, is a flag, anywhere after the line's first word:

- **its name is lowercased,** and `--name=value` gives its value in the same word: `--for=90`,
  `--label="north dock"`;
- **whether it takes a value is the tree's to say** (`tree.flags`), since the walk doesn't know its command yet: a
  switch takes no value, and any other flag takes the word after it, even one that's a literal (`--into merge`), or
  begins with one dash (`--by -3`);
- **a list's flag may be given again,** each adding a word: `--tag a --tag b`. Any other flag is given once;
- **parsed's own,** `--help`, `--json`, `--yes` and `--dry-run`, are switches every command takes. They're kept
  apart from the fields, in `Reading.own`, for whatever runs the command;
- **`--` ends the flags:** every word after it is a word, `--` and all.

## Then the words

From the root, a word at a time ([`tree.md`](../tree.md#reading-a-line)): a word that is a literal child of the node
takes that branch, case aside and never quoted; else the node's slot takes it. A slot of several words takes them up
to a word that's a literal after them, or the end; the rest of the line takes every word left, joined by single
spaces (or as a list, for a list's field).

**Each word is read by its field's kind** ([`kinds.md`](../kinds.md#reading-a-word)), once the walk knows its
command: `1,000` to `1000`, `1h30m` to `5400.0` seconds, `GREEN` to an `Enum`'s `'green'`. A slot by an alias
reads by its own `KINDS` entry, if it has one. The rest of the line is read once, joined; a list's words are read
one by one.

A kind's [literal words](../kinds.md#literal-words) come first, never for a quoted word. **A name is read by the
resolver for its category** ([`names.md`](../names.md)), when `walk(tree, line, names)` has one, or as typed; a
[`Pairs`](../kinds.md#pairs) field's words in twos, each key by its category's resolver and each value by the one it
gives the key. The walk first gathers each field's words, then reads them in an order that puts a scope before
the names it narrows, whatever their order on the line, and gives each resolver its scope's value.

## `Reading`

| Attribute | Holds |
|---|---|
| `end` | where the walk ended: the command, the phrase, and the slots read |
| `given` | each field the line gives, by attribute name: its slots in the phrase's order, then its flags in the line's. A field the line leaves out isn't here, and keeps its default |
| `own` | parsed's own flags the line gives, by name: `yes`, `json`, … |
| `line` | the line read |
| `command` | the command class (a property) |

Each of `given` is a `Given`: `by`, the slot (a `Place`) or the flag (a `Flag`) that took the words; `words`, every
`Token` that went into the field, flags and all, in the line's order; and `value`, what seared loads for it: each
word read by the field's kind, a list of them for a list's field, or a switch's `True` (`False` for a `--no-…`
switch).

`reading.data()` is the values by wire name, as seared's `load` takes them and a tool call would send them:
`{'fleet': 'f1', 'for': 5400.0}`. `reading.load()` loads the command from them, refusing any key the command
doesn't know.

## What it refuses

One [`ReadError`](../errors.md#readerror) for each, its message saying what's wrong with the words read up to it,
then any did-you-mean, then the hint in backticks. Its `column` is the word at fault's, or the line's end where a
word is missing; its `suggestions` are the did-you-mean's words, or the words that may come next:

| The line | Says | Suggests |
|---|---|---|
| has no words | `no command: the line has no words` | the first words |
| leaves a quote open | ``the quote at column 5 is never closed: "hello `say "hello"` `` | |
| begins with a flag | `--yes comes before a command: a flag follows the first word` | |
| gives a flag no command takes | `no command takes --fro; did you mean --for?` | flags close to it |
| gives a value to a switch | `--quiet takes nothing after it` | |
| ends at a flag that takes a value, or gives it a flag | ``--for needs a value `--for <for>` `` | |
| gives a flag twice | `--for is given twice` | |
| says a word no command says | `no command 'fleet f1 mien'; did you mean mine?` | words close to it |
| … with no word close to it | `no command 'fleet f1 xyz': buy \| dock \| jump \| mine \| sell` | the words that may come |
| goes on after a command's last word | ``log 40: '50' is left over `log [<n>]` `` | |
| stops at a slot | ``fleet f1 jump: which system? `fleet f1 jump <system>` `` | |
| stops at a word that isn't a command | `fleet f1: then what? buy \| dock \| jump \| mine \| sell` | the words that may come |
| gives a flag its command doesn't take | ``fleet f1 mine takes no --into `fleet <fleet> mine [--for <for>]` `` | its flags close to it |
| leaves out a required flag | ``fleets merge f1 needs --into `fleets merge f1 --into <into>` `` | |
| gives a slot a word its kind can't read | `log {n}: 'many' is not a whole number` | |
| gives a flag a word its kind can't read | `--for: 'soon' is not a span of time: say 90s, 10m, 2h or 1h30m` | |
| gives a name no name answers to | ``--into: no fleet 'Haulr'; did you mean Hauler? `fleets merge <fleet> --into <into> [--quiet]` `` | the resolver's |
| gives a pair's key no key answers to | `… {variables**}: no variable 'hme' for routine 'mining'; did you mean home?` | the resolver's |
| gives a pair's value no name answers to | `… {variables**}: no home 'mars'` | the key's resolver's |
| leaves a key without its value | `… {variables**}: 'home' and its value? pairs come in twos` | |
| gives a key twice | `… {variables**}: ore is given twice` | |

A hint is a usage ([`_hints.md`](_hints.md)): the command's; or, at a slot left empty, the line so far, then the
rest of the one command's usage past it (flags and all), or the slot's `<…>` where several lie past it.
Since a switch takes no value, `--quiet yes` reads `yes` as a word, which the command may not take.

**seared's refusals** of a value, once read (its bounds, lengths or pattern), come back from `load` as a
`ReadError` whose `kind` is `'validation'`, at the word that gave the value: `log {n}: must be >= 1, got 0`, or
`--port: must be <= 65535, got 70000`. For a list, it's the word at the refused index; for the rest of the line, the
whole of it. seared's `ValidationError` is its `__cause__`.
