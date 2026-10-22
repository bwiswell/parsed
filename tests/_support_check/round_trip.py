"""A kind whose two ways disagree: it writes a word upper-cased, and reads it as said."""

from dataclasses import dataclass
from typing import ClassVar

import parsed


@dataclass(frozen=True, slots=True)
class Shouted(parsed.Kind):
    """Writes a word upper-cased."""

    def spell(self, value, field):
        return [str(value).upper()]


@parsed.parsed
class Shout(parsed.Command):
    """Shout a word."""

    PHRASE = 'shout {word}'
    KINDS: ClassVar[dict[str, parsed.Kind]] = {'word': Shouted()}

    word: str = parsed.Str(required=True)
