# `_phrase/`: phrases, and how they bind

A private subpackage, gathered by its `__init__.py`:

- [`_grammar.py`](_grammar.md) reads a phrase's words and slots;
- [`_binding.py`](_binding.md) binds each of a command's phrases to its fields.

[`declaration`](../command.md#declarationcls) uses both: a command's `Declaration` holds its phrases, bound, and its
flags. Nothing here is part of parsed's public surface; [`command.md`](../command.md#phrases) says what a phrase
may be.
