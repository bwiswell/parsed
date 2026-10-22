"""``_walk``: how a line splits into words, and how the words walk a tree.

Pattern B subdir. ``_words.py`` splits a line into words; ``_walker.py`` splits off its flags and walks the rest from
a tree's root, keeping each field's words. :meth:`parsed.tree.Tree.walk` and :meth:`~parsed.tree.Tree.read` use both.
"""

from ._walker import RESERVED, Arity, Given, Reading, SlotKind, walk
from ._words import Token, split

__all__ = ['RESERVED', 'Arity', 'Given', 'Reading', 'SlotKind', 'Token', 'split', 'walk']
