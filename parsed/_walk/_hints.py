"""What a refusal says besides what's wrong: how a command is said, and what may have been meant.

A **usage** is a phrase with a ``<slot>`` for each slot, then its flags: ``fleets merge <fleet> --into <into>
[--quiet]``. An optional slot is ``[<n>]``, several words ``<goods> …``, the rest of the line ``<message …>``. A
required flag stands as it is said; any other is in brackets, a list's flag with ``…`` after it.

**Did-you-mean** is the standard library's ``difflib``: up to three words or flags close to the one given.
"""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

from parsed._phrase import Word

from ._terms import Arity

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from seared import Field

    from parsed._phrase import Bound, Place
    from parsed.tree import Flag


def usage(bound: Bound, flags: Iterable[Flag], fields: Mapping[str, Field]) -> str:
    """How a command is said by ``bound``'s phrase: its words, a ``<slot>`` for each slot, then its flags."""
    places = {place.slot: place for place in bound.places}
    words = [part.text if isinstance(part, Word) else slot(places[part.name]) for part in bound.phrase.parts]
    return ' '.join([*words, *(_flag(flag, fields[flag.field]) for flag in flags)])


def slot(place: Place) -> str:
    """A slot as a usage writes it."""
    said = f'<{place.slot} …>' if place.rest else f'<{place.slot}> …' if place.many else f'<{place.slot}>'
    return said if place.required else f'[{said}]'


def _flag(flag: Flag, field: Field) -> str:
    if flag.arity is Arity.SWITCH:
        return f'[--{flag.name}]'
    said = f'--{flag.name} <{flag.name}>'
    if field.many:
        return f'[{said} …]'
    return said if field.required else f'[{said}]'


def close(word: str, candidates: Iterable[str]) -> list[str]:
    """Up to three of ``candidates`` close to ``word``, the closest first."""
    return difflib.get_close_matches(word, list(candidates), n=3)


def either(words: Sequence[str]) -> str:
    """Words joined for a sentence: ``a``, ``a or b``, ``a, b or c``."""
    return words[0] if len(words) == 1 else f'{", ".join(words[:-1])} or {words[-1]}'
