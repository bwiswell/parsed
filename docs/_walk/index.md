# `_walk/`: words, and how they walk a tree

A private subpackage, gathered by its `__init__.py`:

- [`_words.py`](_words.md) splits a line into words;
- [`_walker.py`](_walker.md) splits off a line's flags and walks its words from a tree's root, keeping each
  field's words.

[`Tree.walk` and `Tree.read`](../tree.md#reading-a-line) use both. The walk's terms (`SlotKind`, `Arity`,
`RESERVED`) are also the tree's, and `parsed.tree` gives them, with `Reading`; [`tree.md`](../tree.md) says what a
line may be.
