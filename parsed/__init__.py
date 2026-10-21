"""Public surface of the ``parsed`` package: typed command trees on seared, for people and agents.

Re-exports seared's declaration surface, as zeared does, so ``import parsed`` is enough to declare a command: every
field type, the error hierarchy, the ``Seared`` base class (renamed ``Parsed``) and the decorator (renamed
``parsed``). Everything else of seared's stays reachable as ``seared.*``.

parsed's own surface:

- ``command.py``: :class:`Command`, the base of every command, and what a command declares.
- ``effect.py``: :class:`Effect` and :func:`effect_of`, what running a command does.
- ``errors.py``: :class:`ParsedError`, the base of parsed's errors, and :class:`DeclarationError`.
- ``kinds.py``: :class:`Kind`, how a field's words are read, and :class:`Name`, one of an app's names; the default
  kinds stay ``parsed.kinds.*``.
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

from .command import Command
from .effect import Effect, effect_of
from .errors import DeclarationError, ParsedError
from .kinds import Kind, Name

__version__ = '0.1.0'

__all__ = [
    'UUID',
    'Bool',
    'Bytes',
    'Command',
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
    'SearedError',
    'Str',
    'T',
    'Time',
    'TimeDelta',
    'Tuple',
    'Union',
    'ValidationError',
    '__version__',
    'effect_of',
    'parsed',
]
