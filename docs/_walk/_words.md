# `_walk/_words.py`: a line's words

`split(line)` splits a line into its words, in order, each a `Token`:

| Attribute | Holds |
|---|---|
| `text` | the word, its quotes left off |
| `start` | where it starts in the line, from 0 |
| `raw` | the word as typed, quotes and all |
| `quoted` | whether any of it was quoted (a property) |

**Words are split on whitespace,** and double quotes hold spaces:

| Typed | Words |
|---|---|
| `fleet "Vruba'a Belt 1" mine` | `fleet`, `Vruba'a Belt 1`, `mine` |
| `belt-"1 a"` | `belt-1 a`: a quote may stand anywhere in a word |
| `say ""` | `say`, and an empty word |
| `Vruba'a` | `Vruba'a`: a single quote is a plain character |

There are no escapes, so a word can't hold a double quote. A quote left open is refused with a `ReadError` naming
its column, unless the line is still being typed (`split(line, partial=True)`, for completion): then it holds the
last word as far as it goes.

**A quoted word is a value,** never a literal or a flag: `jump "nearest"` names a system called nearest, and
`say "--loud"` says it.
