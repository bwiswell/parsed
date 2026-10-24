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
| `--args "{\"station\": \"s1\"}"` | `--args`, `{"station": "s1"}`: a backslash right before a double quote makes it plain |
| `C:\temp a\d` | `C:\temp`, `a\d`: any other backslash is itself |

**The one escape** is a backslash right before a double quote, quoted or not: it makes the quote a plain
character, opening and closing nothing. There's no other: no `\\`, no `\n`. So a backslash right before a quote
that should close one (`"C:\dir\"`) escapes it instead, and the quote is left open.

A quote left open is refused with a `ReadError` naming its column, unless the line is still being typed
(`split(line, partial=True)`, for completion): then it holds the last word as far as it goes.

**`word(text, quoted=False)`** writes any string as a word that reads back to it: each `"` written `\"`, the word
quoted where it holds whitespace or is empty, or where `quoted` asks (a value spelled like a literal, or a flag),
and a quoted word's trailing backslashes after its closing quote (`"C:\My Dir"\`), so none escapes it. A command
line's arguments, a rendered value and a completion's candidate are written so.

| Text | Written |
|---|---|
| `{"station": "s1"}` | `"{\"station\": \"s1\"}"` |
| `name="40"` | `name=\"40\"` |
| `Vesta Ring` | `"Vesta Ring"` |
| `C:\My Dir\` | `"C:\My Dir"\` |

**A quoted word is a value,** never a literal or a flag: `jump "nearest"` names a system called nearest, and
`say "--loud"` says it. A word holding an escaped quote is one too.
