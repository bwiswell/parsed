"""How a line splits into words.

Words are split on whitespace. **Double quotes** hold a name with spaces: ``"Vruba'a Belt 1"`` is one word, its
quotes left off. A quote may stand anywhere in a word (``belt-"1 a"`` is ``belt-1 a``), and ``""`` is an empty word.
There are no escapes, so a word can't hold a double quote; a single quote is a plain character.

**A quoted word is a value:** never a literal, so ``jump "nearest"`` names a system called nearest, and never a flag,
so ``say "--loud"`` says it.
"""

from __future__ import annotations

from dataclasses import dataclass

from parsed.errors import ReadError


@dataclass(frozen=True, slots=True)
class Token:
    """A word of a line.

    Attributes:
        text: The word, its quotes left off.
        start: Where it starts in the line, from 0.
        raw: The word as typed, quotes and all.
    """

    text: str
    start: int
    raw: str

    @property
    def quoted(self) -> bool:
        """Whether any of it was quoted, so it's a value: never a literal or a flag."""
        return '"' in self.raw


def split(line: str) -> list[Token]:
    """A line's words, in order.

    Raises:
        ReadError: A quote is left open.
    """
    tokens: list[Token] = []
    text: list[str] = []
    start = -1  # where the word being read starts; -1 between words
    opened = -1  # where the open quote is; -1 outside quotes
    for at, ch in enumerate(line):
        if ch == '"':
            start = at if start < 0 else start
            opened = at if opened < 0 else -1
        elif ch.isspace() and opened < 0:
            if start >= 0:
                tokens.append(Token(text=''.join(text), start=start, raw=line[start:at]))
                text, start = [], -1
        else:
            start = at if start < 0 else start
            text.append(ch)
    if opened >= 0:
        msg = f'the quote at column {opened + 1} is never closed: {line[opened:]}'
        raise ReadError(msg)
    if start >= 0:
        tokens.append(Token(text=''.join(text), start=start, raw=line[start:]))
    return tokens
