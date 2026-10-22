# `_walk/_complete.py`: what may come next

`complete(tree, text, names)` reads a line being typed, up to the cursor, and offers what may come next.
`Tree.complete(text, names=…)` calls it, and gives back a `Completion`:

| Attribute | Holds |
|---|---|
| `words` | the candidates, as they'd be typed, each matching the word being typed, case aside |
| `replace` | how many characters before the cursor each replaces: the word being typed, or none |

It unpacks as a pair: `words, replace = tree.complete(text)`.

```python
tree.complete('fleet Prospector dock vr', names=names)
# Completion(words=['"Vruba\'a Belt 1"'], replace=2)
```

## What it offers

The words before the one being typed are read loosely, as far as they go, and what may come next is offered:

| Where the line stands | Offers |
|---|---|
| at its first word | the first words of every command |
| at a slot | its kind's literal words, its own offers (an `Enum`'s values, `true` and `false`, `10m`, `30m` and `1h` for a span of time), and for a name, the `options` of the resolver for its category, given its scope |
| after a slot or a word | the literal words that may come next |
| after a whole command | its flags not yet given (a list's again), `--yes` if it asks first, and `--until` (again) and `--timeout` (once) if it can wait |
| at `--until`'s value | a condition on each of the reply's fields: `fleet=`, `docked=` |
| at `--timeout`'s value | a few bounds: `30s`, `1m`, `2m`, `5m` |
| at a flag being typed, before then | the flags of every command the line may be |
| at a flag waiting for its value | its values, by its kind |
| in a `Pairs` field | a key not yet given, then that key's values; and the command's flags not yet given |
| in any other rest of the line | the command's flags not yet given, since a flag may stand anywhere |

A name's scope is its field's words so far, read by the scope's own resolver: `fleet Hauler dock ` offers the
stations within Hauler's reach, and `board --fleet Hauler ` does too. A quoted word is a value, so while one is
typed, no literal word or flag is offered. A candidate with a space in it comes back quoted, so it replaces the word
being typed whole. A line whose words don't read as far as they go is offered nothing.

The line is split as a line being typed is (`split(text, partial=True)`): a quote left open holds the last word, so
`dock "Vru` completes inside the quotes.
