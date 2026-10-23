"""``_walk``: how a line splits into words, and how the words walk a tree.

Pattern B subdir. ``_words.py`` splits a line into words; ``_walker.py`` splits off its flags and walks the rest from
a tree's root, keeping each field's words; ``_complete.py`` offers what may come next on a line being typed;
``_render.py`` writes an instance back to its line; ``_hints.py`` writes a refusal's usage and did-you-mean;
``_terms.py`` holds the terms the tree builds by; ``_route.py`` sends a line to the mount whose tree reads it.
:meth:`parsed.tree.Tree.walk`, :meth:`~parsed.tree.Tree.read`, :meth:`~parsed.tree.Tree.complete` and
:meth:`~parsed.tree.Tree.render` use them, and :class:`parsed.app.App` its routes.
"""

from ._complete import Completion, complete, goes
from ._render import key, moved_by, render
from ._route import Mounted, Routes
from ._terms import RESERVED, THEN, Arity, SlotKind
from ._walker import Given, Reading, walk
from ._words import Token, split

__all__ = [
    'RESERVED',
    'THEN',
    'Arity',
    'Completion',
    'Given',
    'Mounted',
    'Reading',
    'Routes',
    'SlotKind',
    'Token',
    'complete',
    'goes',
    'key',
    'moved_by',
    'render',
    'split',
    'walk',
]
