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
command: `1,000` to `1000`, `1h30m` to `5400.0` seconds, `GREEN` to an `Enum`'s `'green'`. A renamed slot reads by
its own `KINDS` entry. The rest of the line is read once, joined; a list's words are read one by one.

## `Reading`

| Attribute | Holds |
|---|---|
| `end` | where the walk ended: the command, the phrase, and the slots read |
| `given` | each field the line gives, by attribute name: its slots in the phrase's order, then its flags in the line's. A field the line leaves out isn't here, and keeps its default |
| `own` | parsed's own flags the line gives, by name: `yes`, `json`, … |
| `command` | the command class (a property) |

Each of `given` is a `Given`: `by`, the slot (a `Place`) or the flag (a `Flag`) that took the words; `words`, every
`Token` that went into the field, flags and all, in the line's order; and `value`, what seared loads for it: each
word read by the field's kind, a list of them for a list's field, or a switch's `True` (`False` for a `--no-…`
switch).

`reading.data()` is the values by wire name, as seared's `load` takes them and a tool call would send them:
`{'fleet': 'f1', 'for': 5400.0}`. `reading.load()` loads the command from them, refusing any key the command
doesn't know. A value out of its field's bounds, lengths or pattern raises seared's `ValidationError`, as does a
required field the line leaves out.

## What it refuses

A `ReadError`, its message saying what's wrong with the words read up to it:

| The line | Says |
|---|---|
| has no words | `no command: the line has no words` |
| leaves a quote open | `the quote at column 7 is never closed: "Vruba mine` |
| begins with a flag | `--yes comes before a command: a flag follows the first word` |
| gives a flag no command takes | `no command takes --n` |
| gives a value to a switch | `--quiet takes nothing after it` |
| ends at a flag that takes a value, or gives it a flag | `--for needs a value` |
| gives a flag twice | `--for is given twice` |
| says a word no command says | `no command 'fleet f1 progrms'` |
| goes on after a command's last word | `log 40: '50' is left over` |
| stops at a slot | `fleet f1 jump: which system?` |
| stops at a word that isn't a command | `fleet f1: then what? buy \| dock \| jump \| mine \| sell` |
| gives a flag its command doesn't take | `fleet {fleet} mine takes --for, not --into` |
| gives a slot a word its kind can't read | `log {n}: 'many' is not a whole number` |
| gives a flag a word its kind can't read | `--for: 'soon' is not a span of time: say 90s, 10m, 2h or 1h30m` |

Since a switch takes no value, `--quiet yes` reads `yes` as a word, which the command may not take.
