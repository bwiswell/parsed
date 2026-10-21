"""Public surface of the ``parsed`` package: typed command trees on seared, for people and agents.

Re-exports seared's declaration surface, as zeared does, so ``import parsed`` is enough to declare a class: every
field type, the error hierarchy, the ``Seared`` base class (renamed ``Parsed``) and the decorator (renamed
``parsed``). Everything else of seared's stays reachable as ``seared.*``.
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

__version__ = '0.1.0'

__all__ = [
    'UUID',
    'Bool',
    'Bytes',
    'Date',
    'DateTime',
    'Decimal',
    'Dict',
    'Enum',
    'Float',
    'Int',
    'NDArray',
    'PandasFrame',
    'Parsed',
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
    'parsed',
]
