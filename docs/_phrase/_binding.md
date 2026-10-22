# `_phrase/_binding.py`: how a command's phrases bind to its fields

`bind(...)` takes a command's fields and what it declares about its phrases, and returns a `Binding`: `phrases`
(`PHRASE`, then each of `EXTRA_PHRASES`, each a `Bound`) and `flags` (the fields no slot of `PHRASE` fills, in their
declared order).

- **`Bound`:** the `phrase`, read; its `places`, in order; `left_out`, the fields `PHRASE` has slots for that this
  phrase leaves out, which keep their defaults; and `renames`, whether one of its slots says its field by an alias.
- **`Place`:** a slot bound: its `slot` name as written (also its `KINDS` key), the `field` it fills, and whether
  that field is `required`, takes several words (`many`), or the rest of the line (`rest`). `renamed` says whether
  the slot's name differs from its field's: whether it's an alias.

## The rules

**Every slot fills a field, by name:** the field it's named after, or, for a slot named in `ALIASES`, the field the
alias gives. A slot that's neither is refused, as is a phrase with two slots for one field, an alias to no field,
and an alias that's a field's own name.

**`PHRASE`:**

- the fields its slots fill are the positionals, and every other field is a flag;
- a slot that may be empty (its field isn't `required`) or takes several words (`many`) is followed by a word or
  ends the phrase, so a line reads one way.

**Each of `EXTRA_PHRASES`:**

- each slot fills one of `PHRASE`'s positionals, in any order, written alike (the rest of the line in both, or in
  neither);
- a positional it leaves out keeps its field's default, so the field must have one.

**Then:**

- `POLYMORPHIC`, when declared: `True` wants a phrase that says a slot by an alias, `False` refuses one;
- a command's own `KINDS` names its fields or its aliases. A base's entries may go unused by a given command.

Every refusal is a `DeclarationError` naming the class, the constant and the phrase.
