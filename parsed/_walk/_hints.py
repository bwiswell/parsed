"""What a refusal says besides what's wrong: how a command is said, and what may have been meant.

A **usage** is a phrase with a ``<slot>`` for each slot, then its flags: ``fleets merge <fleet> --into <fleet>
[--quiet] [--yes]``. An optional slot is ``[<n>]``, several words ``<goods> …``, the rest of the line ``<message
…>``. A required flag stands as it is said; any other is in brackets, a list's flag with ``…`` after it. A flag's
value is written by its kind (:func:`label`): ``--for <span>``, ``--into <fleet>``. A command that may ask first
(``ASKS``) ends with ``[--yes]``, which answers it. One that passes a line on says its flags before the line:
``see [--pretty] <line …>``.

**Did-you-mean** is the standard library's ``difflib``: up to three words or flags close to the one given.
"""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

from parsed._phrase import Word
from parsed.kinds import Line

from ._terms import Arity

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from seared import Field

    from parsed._phrase import Bound, Place
    from parsed.command import Declaration
    from parsed.kinds import Kind
    from parsed.tree import Flag


def usage(  # noqa: PLR0913 -- how a phrase is said, and what it ends with
    bound: Bound,
    flags: Iterable[Flag],
    fields: Mapping[str, Field],
    *,
    start: int = 0,
    asks: bool = False,
    passing: bool = False,
) -> str:
    """How a command is said by ``bound``'s phrase: its words, a ``<slot>`` for each slot, then its flags.

    ``start`` is where in the phrase's parts to begin, for the rest of a line that says the parts before it; ``asks``,
    whether the command may ask first, so it ends with ``[--yes]``; ``passing``, whether it ends at a line passed on,
    which its flags then stand before: ``see [--pretty] <line …>``.
    """
    places = {place.slot: place for place in bound.places}
    parts = bound.phrase.parts[start:]
    words = [part.text if isinstance(part, Word) else slot(places[part.name]) for part in parts]
    after = [*(_flag(flag, fields[flag.field]) for flag in flags), *(['[--yes]'] if asks else [])]
    if passing and words:
        return ' '.join([*words[:-1], *after, words[-1]])
    return ' '.join([*words, *after])


def passes(found: Declaration, bound: Bound) -> bool:
    """Whether ``bound``'s phrase ends at a line passed on: a slot read by a :class:`~parsed.kinds.Line`."""
    last = bound.places[-1] if bound.places else None
    return last is not None and last.rest and isinstance(found.kind_of(last), Line)


def slot(place: Place) -> str:
    """A slot as a usage writes it."""
    said = f'<{place.slot} …>' if place.rest else f'<{place.slot}> …' if place.many else f'<{place.slot}>'
    return said if place.required else f'[{said}]'


def plain_slot(place: Place) -> str:
    """A slot as a refusal or a help's row names it: as a usage writes it, an optional one without its brackets."""
    return slot(place).removeprefix('[').removesuffix(']')


def label(kind: Kind, field: Field, name: str) -> str:
    """What a usage writes a flag's value as, between ``<`` and ``>``: ``span``, ``n|off``.

    Its kind's label (:meth:`parsed.kinds.Kind.usage_label`), else ``name``, the flag's; then the kind's literal
    words, each after a ``|``.
    """
    return '|'.join([kind.usage_label(field) or name, *kind.words])


def _flag(flag: Flag, field: Field) -> str:
    if flag.arity is Arity.SWITCH:
        return f'[--{flag.name}]'
    said = f'--{flag.name} <{flag.label}>'
    if field.many:
        said = f'{said} …'
    return said if field.required else f'[{said}]'


def close(word: str, candidates: Iterable[str]) -> list[str]:
    """Up to three of ``candidates`` close to ``word``, the closest first."""
    return difflib.get_close_matches(word, list(candidates), n=3)


def either(words: Sequence[str]) -> str:
    """Words joined for a sentence: ``a``, ``a or b``, ``a, b or c``."""
    return words[0] if len(words) == 1 else f'{", ".join(words[:-1])} or {words[-1]}'
