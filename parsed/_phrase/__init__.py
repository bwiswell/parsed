"""``_phrase``: what a phrase says, and how a command's phrases bind to its fields.

Pattern B subdir. ``_grammar.py`` reads a phrase's words and slots; ``_binding.py`` binds each of a command's phrases
to its fields. :func:`parsed.command.declaration` uses both.
"""

from ._binding import Binding, Bound, Place, bind
from ._grammar import Phrase, Slot, Word, parse

__all__ = ['Binding', 'Bound', 'Phrase', 'Place', 'Slot', 'Word', 'bind', 'parse']
