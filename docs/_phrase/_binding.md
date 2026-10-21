# `_phrase/_binding.py`: how a command's phrases bind to its fields

`bind(...)` takes a command's fields and what it declares about its phrases, and returns a `Binding`: `phrases`
(`PHRASE`, then each of `EXTRA_PHRASES`, each a `Bound`) and `flags` (the fields no slot of `PHRASE` names, in their
declared order).

- **`Bound`:** the `phrase`, read; its `places`, in order; `left_out`, the fields `PHRASE` has slots for that this
  phrase leaves out, which keep their defaults; and `renames`, whether one of its slots renames a field.
- **`Place`:** a slot bound: its `slot` name as written (also its `KINDS` key), the `field` it fills, and whether
  that field is `required`, takes several words (`many`), or the rest of the line (`rest`). `renamed` says whether
  the slot's name differs from its field's.

## The rules

**`PHRASE`:**

- each slot names a field of the command, which it fills;
- a slot that may be empty (its field isn't `required`) or takes several words (`many`) is followed by a word or
  ends the phrase, so a line reads one way.

**Each of `EXTRA_PHRASES`:**

- **a slot named after a field** fills it, and the field is one of `PHRASE`'s slots, written alike (the rest of the
  line in both, or in neither);
- **a slot named after no field renames one:** it needs a `KINDS` entry by its own name, fills the field of
  `PHRASE`'s slot at the same place, and keeps the rest of `PHRASE`'s slots, in their order;
- **a slot left out** keeps its field's default, so the field must have one.

**Then:**

- `POLYMORPHIC`, when declared: `True` wants a phrase that renames a slot, `False` refuses one;
- a command's own `KINDS` names its fields or its renamed slots. A base's entries may go unused by a given command.

Every refusal is a `DeclarationError` naming the class, the constant and the phrase.
