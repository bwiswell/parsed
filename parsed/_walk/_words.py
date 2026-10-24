r"""How a line splits into words.

Words are split on whitespace. **Double quotes** hold a name with spaces: ``"Vruba'a Belt 1"`` is one word, its
quotes left off. A quote may stand anywhere in a word (``belt-"1 a"`` is ``belt-1 a``), and ``""`` is an empty word.
A single quote is a plain character.

**A backslash right before a double quote makes it a plain character,** quoted or not: ``"{\"station\": \"s1\"}"``
is ``{"station": "s1"}``. It's the one escape: any other backslash is itself (``C:\temp``). :func:`word` writes any
string as a word that reads back to it.

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


def split(line: str, *, partial: bool = False) -> list[Token]:
    """A line's words, in order.

    Args:
        line: The line.
        partial: Whether it's a line being typed, so a quote left open holds the last word as far as it goes.

    Raises:
        ReadError: A quote is left open, on a line that isn't being typed.
    """
    tokens: list[Token] = []
    text: list[str] = []
    start = -1  # where the word being read starts; -1 between words
    opened = -1  # where the open quote is; -1 outside quotes
    escaped = _escaped(line) if _ESCAPE in line else ()  # each double quote a backslash makes plain
    for at, ch in enumerate(line):
        if ch == '"':
            if at in escaped:
                text[-1] = ch  # in the place of its backslash, the character just before it
                continue
            start = at if start < 0 else start
            opened = at if opened < 0 else -1
        elif ch.isspace() and opened < 0:
            if start >= 0:
                tokens.append(Token(text=''.join(text), start=start, raw=line[start:at]))
                text, start = [], -1
        else:
            start = at if start < 0 else start
            text.append(ch)
    if opened >= 0 and not partial:
        hint = f'{line}"'
        msg = f'the quote at column {opened + 1} is never closed: {line[opened:]} `{hint}`'
        raise ReadError(msg, line=line, column=opened, hint=hint)
    if start >= 0:
        tokens.append(Token(text=''.join(text), start=start, raw=line[start:]))
    return tokens


def word(text: str, *, quoted: bool = False) -> str:
    r"""``text`` as a line's word, which :func:`split` reads back to it.

    Each ``"`` is written ``\"``. The word is quoted where it holds whitespace or is empty, or where ``quoted`` asks
    (one spelled like a literal, or a flag); a quoted word's trailing backslashes are written after its closing quote,
    so none escapes it: ``"C:\My Dir"\``.
    """
    said = text.replace('"', _ESCAPE)
    if text and not quoted and not any(ch.isspace() for ch in text):
        return said
    body = said.rstrip('\\')
    return f'"{body}"{said[len(body) :]}'


#: A double quote a backslash makes plain.
_ESCAPE = '\\"'


def _escaped(line: str) -> frozenset[int]:
    """Where in ``line`` each double quote a backslash makes plain stands."""
    found: set[int] = set()
    at = line.find(_ESCAPE)
    while at >= 0:
        found.add(at + 1)
        at = line.find(_ESCAPE, at + 2)
    return frozenset(found)
