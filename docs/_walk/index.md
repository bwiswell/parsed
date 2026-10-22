# `_walk/`: words, and how they walk a tree

A private subpackage, gathered by its `__init__.py`:

- [`_words.py`](_words.md) splits a line into words;
- [`_walker.py`](_walker.md) splits off a line's flags and walks its words from a tree's root, keeping each
  field's words, and refuses a line that doesn't read;
- [`_hints.py`](_hints.md) writes a refusal's hint and did-you-mean;
- `_terms.py` holds the walk's terms, which the tree builds by too: `RESERVED`, parsed's own flags; `SlotKind`,
  what a slot takes; and `Arity`, whether a flag takes a value.

[`Tree.walk` and `Tree.read`](../tree.md#reading-a-line) use them. `parsed.tree` gives the walk's terms, with
`Reading`; [`tree.md`](../tree.md) says what a line may be.
