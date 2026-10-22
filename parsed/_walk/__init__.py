"""``_walk``: how a line splits into words, and how the words walk a tree.

Pattern B subdir. ``_words.py`` splits a line into words; ``_walker.py`` splits off its flags and walks the rest from
a tree's root, keeping each field's words; ``_complete.py`` offers what may come next on a line being typed;
``_render.py`` writes an instance back to its line; ``_hints.py`` writes a refusal's usage and did-you-mean;
``_terms.py`` holds the terms the tree builds by. :meth:`parsed.tree.Tree.walk`, :meth:`~parsed.tree.Tree.read`,
:meth:`~parsed.tree.Tree.complete` and :meth:`~parsed.tree.Tree.render` use them.
"""

from ._complete import Completion, complete
from ._render import render
from ._terms import RESERVED, Arity, SlotKind
from ._walker import Given, Reading, walk
from ._words import Token, split

__all__ = [
    'RESERVED',
    'Arity',
    'Completion',
    'Given',
    'Reading',
    'SlotKind',
    'Token',
    'complete',
    'render',
    'split',
    'walk',
]
