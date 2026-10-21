# `_phrase/_grammar.py`: a phrase's words and slots

`parse(text)` reads a phrase into a `Phrase`: its text, single-spaced, and its parts in order, each a `Word` (a
literal, said as it is) or a `Slot` (a field's value; with `rest`, the rest of the line). `Phrase.slots` and
`Phrase.words` give each kind of part alone.

| Part | Written | Reads |
|---|---|---|
| a word | lowercase letters, digits, `-` and `_`, beginning with a letter or a digit | `fleet`, `set-up`, `2fa` |
| a slot | `{name}`, a Python name | `{fleet}`, `{for_}` |
| the rest of the line | `{name**}`, last | `{message**}` |

**What it refuses,** with a `ValueError` saying which part and why:

- an empty phrase;
- a phrase that begins with a slot: a line is found by its first word;
- a slot named twice;
- `{name**}` anywhere but last;
- a token that's neither: `{fleet` or `x{fleet}`, `Fleet` (a capital), `fleet/mine` (a slash), `--for` (a flag's
  spelling), `*`.

`declaration` turns the `ValueError` into a `DeclarationError` naming the class, the constant and the phrase.
