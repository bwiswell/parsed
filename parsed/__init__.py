"""Public surface of the ``parsed`` package: typed command trees on seared, for people and agents.

Re-exports seared's declaration surface, as zeared does, so ``import parsed`` is enough to declare a command: every
field type, the error hierarchy, the ``Seared`` base class (renamed ``Parsed``) and the decorator (renamed
``parsed``). Everything else of seared's stays reachable as ``seared.*``.

parsed's own surface:

- ``app.py``: :class:`App`, a program's trees mounted under prefixes, the handlers their commands run with, the
  hooks around them, and the names it reads lines with.
- ``argv.py``: a program's arguments as its command line, its root options first, for :meth:`App.main`.
- ``context.py``: :class:`Context`, what a handler is given beside its command.
- ``command.py``: :class:`Command`, the base of every command, and what a command declares.
- ``effect.py``: :class:`Effect` and :func:`effect_of`, what running a command does.
- ``errors.py``: :class:`ParsedError`, the base of parsed's errors, :class:`DeclarationError`, :class:`ReadError`,
  :class:`RefusedError`, :class:`RenderError` and :class:`TimedOutError`.
- ``kinds.py``: :class:`Kind`, how a field's words are read, and :class:`Name`, one of an app's names; the default
  kinds stay ``parsed.kinds.*``.
- ``names.py``: :class:`Resolver`, what an app gives for a category of its names.
- ``reply.py``: :class:`Result`, what running a line comes to, and its exit code; :class:`Ask`, a handler's question,
  asked before it acts.
- ``tree.py``: :class:`Tree`, every command's phrases compiled into one trie, and the lines it reads.
- ``help.py``, ``wait.py``: a command's help and a listing; a read that waits on its reply. They give no root names.
- ``doc/``: commands as data, for the tools that read them; ``import parsed`` doesn't import it.
- ``__main__.py``: ``python -m parsed check``, a package's commands checked in its CI (:mod:`parsed.doc.check`).

``_walk/`` and ``_phrase/`` are private.
"""

from seared import (
    UUID,
    Bool,
    Bytes,
    Date,
    DateTime,
    Decimal,
    Dict,
    Enum,
    Float,
    Int,
    NDArray,
    PandasFrame,
    Path,
    PolarsFrame,
    SearedError,
    Str,
    T,
    Time,
    TimeDelta,
    Tuple,
    Union,
    ValidationError,
)
from seared import (
    Seared as Parsed,  # the base class, renamed for one package's texture
)
from seared import (
    seared as parsed,  # the decorator, renamed for the same reason
)

from .app import App
from .command import Command
from .context import Context
from .effect import Effect, effect_of
from .errors import DeclarationError, ParsedError, ReadError, RefusedError, RenderError, TimedOutError
from .kinds import Kind, Name
from .names import Resolver
from .reply import Ask, Result
from .tree import Tree

__version__ = '0.2.1'

__all__ = [
    'UUID',
    'App',
    'Ask',
    'Bool',
    'Bytes',
    'Command',
    'Context',
    'Date',
    'DateTime',
    'Decimal',
    'DeclarationError',
    'Dict',
    'Effect',
    'Enum',
    'Float',
    'Int',
    'Kind',
    'NDArray',
    'Name',
    'PandasFrame',
    'Parsed',
    'ParsedError',
    'Path',
    'PolarsFrame',
    'ReadError',
    'RefusedError',
    'RenderError',
    'Resolver',
    'Result',
    'SearedError',
    'Str',
    'T',
    'Time',
    'TimeDelta',
    'TimedOutError',
    'Tree',
    'Tuple',
    'Union',
    'ValidationError',
    '__version__',
    'effect_of',
    'parsed',
]
