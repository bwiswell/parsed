"""A phrase's grammar: the words that say a command.

A phrase is words separated by spaces, each a literal word or a slot:

- **a word** is said as it is: lowercase letters, digits, ``-`` and ``_``, beginning with a letter or a digit
  (``fleet``, ``set-up``);
- **``{name}``** is one field's value, as zeared writes a topic's slot;
- **``{name**}``** is the rest of the line, so it comes last.

A phrase begins with a word, and names each slot once. What a slot's name means, a field or a renamed one, is the
binding's to say (:mod:`._binding`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD = re.compile(r'[a-z0-9][a-z0-9_-]*')
_SLOT = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)(\*\*)?\}')


@dataclass(frozen=True, slots=True)
class Word:
    """A literal word, said as it is."""

    text: str


@dataclass(frozen=True, slots=True)
class Slot:
    """A slot: a field's value, or with ``rest``, the rest of the line."""

    name: str
    rest: bool = False


@dataclass(frozen=True, slots=True)
class Phrase:
    """A phrase, read: its text, and its parts in order."""

    text: str
    parts: tuple[Word | Slot, ...]

    @property
    def slots(self) -> tuple[Slot, ...]:
        """Its slots, in order."""
        return tuple(part for part in self.parts if isinstance(part, Slot))

    @property
    def words(self) -> tuple[str, ...]:
        """Its literal words, in order."""
        return tuple(part.text for part in self.parts if isinstance(part, Word))


def parse(text: str) -> Phrase:
    """Read a phrase's words and slots.

    Raises:
        ValueError: The phrase doesn't read. The message says which part, and why.
    """
    tokens = text.split()
    if not tokens:
        msg = 'a phrase has words'
        raise ValueError(msg)
    parts: list[Word | Slot] = []
    seen: set[str] = set()
    for at, token in enumerate(tokens):
        part = _part(token)
        if isinstance(part, Slot):
            if at == 0:
                msg = f'a phrase begins with a word, not the slot {token}'
                raise ValueError(msg)
            if part.name in seen:
                msg = f'{{{part.name}}} appears twice'
                raise ValueError(msg)
            if part.rest and at != len(tokens) - 1:
                msg = f'{token} takes the rest of the line, so it comes last'
                raise ValueError(msg)
            seen.add(part.name)
        parts.append(part)
    return Phrase(text=' '.join(tokens), parts=tuple(parts))


def _part(token: str) -> Word | Slot:
    if _WORD.fullmatch(token):
        return Word(token)
    found = _SLOT.fullmatch(token)
    if found:
        return Slot(found[1], rest=bool(found[2]))
    if '{' in token or '}' in token:
        msg = f'{token!r} is neither a word nor a slot: a slot is {{name}}, or {{name**}} last'
        raise ValueError(msg)
    msg = f"{token!r} is not a word: a word is lowercase letters, digits, '-' and '_'"
    raise ValueError(msg)
