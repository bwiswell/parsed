"""The walk's terms, which the tree builds by too: parsed's own flags, what a slot takes, and a flag's arity."""

from __future__ import annotations

import enum

#: Flags parsed takes for itself on every command, which no field may be named for.
RESERVED = ('help', 'json', 'yes', 'dry-run')

#: The flag that asks for help, and its short form, which no ``SHORTS`` may take.
HELP = 'help'
HELP_SHORT = 'h'

#: The word that joins a chain's steps on a line.
THEN = 'then'


class SlotKind(enum.StrEnum):
    """What a slot takes."""

    ONE = 'one'  # one word
    MANY = 'many'  # one word or more, until a literal after them or the end
    REST = 'rest'  # the rest of the line


class Arity(enum.StrEnum):
    """Whether a flag takes a value."""

    SWITCH = 'switch'  # given or not: --loud
    VALUE = 'value'  # the word after it, or after `=`: --for 10m, --for=10m
