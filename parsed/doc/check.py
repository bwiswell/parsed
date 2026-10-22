"""``parsed check``: a conformance check of a package's commands, for its CI.

:func:`check` builds the tree of every command in the targets (modules or packages, by name), then checks each
command:

- **the tree builds:** every phrase reads and binds, no two read a line two ways, and every flag means one thing;
- **round trips:** two instances made from its fields' types and constraints, one with only its required fields
  and one with every field it can give a value, each render to a line that reads back to it;
- **its examples:** each line of its ``EXAMPLES`` reads to it, a ``<name>`` placeholder standing for any value. A
  line with no placeholder loads too;
- **its schema:** ``json_schema`` builds and takes its example: the instance's wire form has only keys it names,
  and each it requires, and loads back to it. It holds as a constrained decoder needs it to: closed, each ``enum``
  a list of distinct JSON scalars, a field of choices (an ``Enum``'s) an ``enum``, and compact, at most
  ``max_schema_bytes`` written compactly.

A command whose required fields can't all be given a value (a pattern no example word fits, a type with no
example) has no round trips, and is listed as skipped, with those fields; its examples and its schema are still
checked. The :class:`CheckReport` says what was checked, what was skipped, and each :class:`Problem`, with the
command (by module and name) and the check it failed. ``python -m parsed check`` runs it (``parsed/__main__.py``),
the report as JSON on stdout.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from seared import FieldKind, SearedError, field_kind

from parsed.errors import DeclarationError, ReadError, RenderError
from parsed.kinds import Choice
from parsed.tree import Tree

from .json_schema import json_schema

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from seared import Field

    from parsed.command import Command, Declaration

#: The most bytes a command's schema may take, written compactly, unless the check is told otherwise.
MAX_SCHEMA_BYTES = 2048

_PLACEHOLDER = re.compile(r'<[^<>\s]+>')

#: Words a string's example is tried as, in turn, against its lengths and its pattern.
_WORDS = ('example', 'a', 'x', '1', 'a1', 'example-1', 'ex')

#: Stands for a value no example could be made for.
_UNMADE = object()


@dataclass(frozen=True, slots=True)
class Problem:
    """A check a command failed.

    Attributes:
        check: Which: ``tree``, ``round-trip``, ``example`` or ``schema``.
        message: What's wrong.
        command: The command's class, by module and name; ``None`` for the tree's own.
        line: The line at fault, where there's one.
    """

    check: str
    message: str
    command: str | None = None
    line: str | None = None

    def to_json(self) -> dict[str, object]:
        """The problem as data, leaving out the parts it doesn't have."""
        found = {'check': self.check, 'command': self.command, 'line': self.line, 'message': self.message}
        return {key: value for key, value in found.items() if value is not None}


@dataclass(frozen=True, slots=True)
class CheckReport:
    """What a check found.

    Attributes:
        targets: The modules and packages checked.
        commands: How many commands their tree holds.
        round_trips: How many generated instances were rendered and read back.
        examples: How many ``EXAMPLES`` lines were read.
        schemas: How many schemas were built.
        skipped: The commands with no round trips, by module and name, each with the fields that had no example.
        problems: Each check a command failed.
    """

    targets: tuple[str, ...]
    commands: int
    round_trips: int
    examples: int
    schemas: int
    skipped: Mapping[str, tuple[str, ...]]
    problems: tuple[Problem, ...]

    @property
    def ok(self) -> bool:
        """Whether every check passed."""
        return not self.problems

    def to_json(self) -> dict[str, object]:
        """The report as the command writes it."""
        return {
            'targets': list(self.targets),
            'ok': self.ok,
            'commands': self.commands,
            'checked': {'round-trips': self.round_trips, 'examples': self.examples, 'schemas': self.schemas},
            'skipped': {command: list(fields) for command, fields in self.skipped.items()},
            'problems': [problem.to_json() for problem in self.problems],
        }


def check(targets: Sequence[str], *, max_schema_bytes: int = MAX_SCHEMA_BYTES) -> CheckReport:
    """Check every command in ``targets``, as the module's docstring describes.

    Raises:
        ImportError: A target doesn't import.
    """
    try:
        tree = Tree.collect(*targets)
    except DeclarationError as e:
        return CheckReport(tuple(targets), 0, 0, 0, 0, {}, (Problem('tree', str(e)),))
    checking = _Checking(tree, max_schema_bytes)
    for found in tree.commands:
        checking.command(found)
    if not tree.commands:
        checking.problems.append(Problem('tree', f'no commands in {", ".join(targets)}'))
    return CheckReport(
        targets=tuple(targets),
        commands=len(tree.commands),
        round_trips=checking.round_trips,
        examples=checking.examples,
        schemas=checking.schemas,
        skipped=checking.skipped,
        problems=tuple(checking.problems),
    )


class _Checking:
    """One check's tally, as it goes."""

    def __init__(self, tree: Tree, max_schema_bytes: int) -> None:
        self.tree, self.max_schema_bytes = tree, max_schema_bytes
        self.round_trips = self.examples = self.schemas = 0
        self.skipped: dict[str, tuple[str, ...]] = {}
        self.problems: list[Problem] = []

    def command(self, found: Declaration) -> None:
        name = _named(found)
        instances, unmade = _instances(found.cls)
        if unmade:
            self.skipped[name] = tuple(unmade)
        for instance in instances:
            self._round_trip(name, instance)
        for line in found.examples:
            self._example(found, line)
        self._schema(found, instances[-1] if instances else None)

    def _round_trip(self, name: str, instance: Command) -> None:
        self.round_trips += 1
        try:
            line = self.tree.render(instance)
        except RenderError as e:
            self.problems.append(Problem('round-trip', f"{instance!r} doesn't render: {e}", name))
            return
        try:
            back = self.tree.read(line)
        except ReadError as e:
            self.problems.append(Problem('round-trip', f"it doesn't read back: {e}", name, line))
            return
        if back != instance:
            self.problems.append(Problem('round-trip', f'it reads back as {back!r}, not {instance!r}', name, line))

    def _example(self, found: Declaration, line: str) -> None:
        name = _named(found)
        self.examples += 1
        try:
            reading = self.tree.walk(line, placeholders=True)
            if reading.command is not found.cls:
                msg = f'it reads as {reading.command.__qualname__}, not {found.cls.__qualname__}'
                self.problems.append(Problem('example', msg, name, line))
            elif not _PLACEHOLDER.search(line):
                reading.load()
        except ReadError as e:
            self.problems.append(Problem('example', str(e), name, line))

    def _schema(self, found: Declaration, instance: Command | None) -> None:
        name = _named(found)
        self.schemas += 1
        try:
            schema = json_schema(found.cls)
        except TypeError as e:
            self.problems.append(Problem('schema', str(e), name))
            return
        size = len(json.dumps(schema, separators=(',', ':')))
        if size > self.max_schema_bytes:
            msg = f'it takes {size} bytes, over {self.max_schema_bytes}: a decoder holds a compact one more easily'
            self.problems.append(Problem('schema', msg, name))
        self.problems.extend(Problem('schema', msg, name) for msg in _shape(schema, found))
        if instance is None:
            return
        data = found.cls.dump(instance)
        unnamed = sorted(set(data) - set(schema.get('properties', {})))
        missing = sorted(set(schema.get('required', ())) - set(data))
        if unnamed or missing:
            msg = f"it doesn't take its example: {unnamed} not among its properties, {missing} required but not there"
            self.problems.append(Problem('schema', msg, name))
            return
        try:
            back = found.cls.load(data, unknown='raise')
        except SearedError as e:
            self.problems.append(Problem('schema', f"its example doesn't load: {e}", name))
            return
        if back != instance:
            self.problems.append(Problem('schema', f'its example loads as {back!r}, not {instance!r}', name))


def _named(found: Declaration) -> str:
    return f'{found.cls.__module__}.{found.cls.__qualname__}'


def _shape(schema: dict[str, Any], found: Declaration) -> list[str]:
    """What keeps a constrained decoder from holding ``schema``: each fault, said."""
    faults = []
    if schema.get('type') != 'object' or schema.get('unevaluatedProperties') is not False:
        faults.append("it isn't a closed object: a decoder would give keys the command doesn't take")
    faults += [f'{at}: {fault}' for at, values in _enums(schema) if (fault := _enum_fault(values)) is not None]
    wires = {spec.attr: spec.wire for spec in found.cls.__seared_fields__}
    properties = schema.get('properties', {})
    for attr, kind in found.field_kinds.items():
        prop = properties.get(wires[attr])
        if isinstance(kind, Choice) and prop is not None and next(_enums(prop), None) is None:
            faults.append(f"{wires[attr]} is one of a field's choices, but its schema has no enum of them")
    return faults


def _enums(node: object, at: str = '') -> Iterator[tuple[str, object]]:
    """Each ``enum`` under ``node``, with where it stands, as a JSON Pointer."""
    if isinstance(node, list):
        for i, item in enumerate(node):
            yield from _enums(item, f'{at}/{i}')
    elif isinstance(node, dict):
        for key, value in node.items():
            if key == 'enum':
                yield at or '/', value
            else:
                yield from _enums(value, f'{at}/{key}')


def _enum_fault(values: object) -> str | None:
    if not isinstance(values, list) or not values:
        return 'an enum with no values'
    if not all(value is None or isinstance(value, (str, int, float, bool)) for value in values):
        return 'an enum of values that are not JSON scalars'
    if len({json.dumps(value) for value in values}) != len(values):
        return 'an enum with a value twice'
    return None


def _instances(cls: type[Command]) -> tuple[list[Command], list[str]]:
    """Two of ``cls``'s instances, its required fields only and every field it can give: the fields it can't."""
    required: dict[str, object] = {}
    every: dict[str, object] = {}
    unmade: list[str] = []
    for spec in cls.__seared_fields__:
        value = _example(spec.field)
        if value is _UNMADE:
            if spec.field.required:
                unmade.append(spec.attr)
            continue
        every[spec.attr] = value
        if spec.field.required:
            required[spec.attr] = value
    if unmade:
        return [], unmade
    found = [cls(**required)]
    if every != required:
        found.append(cls(**every))
    return found, []


def _example(field: Field) -> object:
    """A value for ``field`` from its type and constraints, or ``_UNMADE``: a list of one, a dict of one pair."""
    value = _scalar(field)
    if value is _UNMADE:
        return _UNMADE
    if field.keyed:
        return {'key': value}
    return [value] if field.many else value


def _scalar(field: Field) -> object:
    kind = field_kind(field)
    if kind is FieldKind.STR:
        return _string(field)
    if kind in {FieldKind.INT, FieldKind.FLOAT}:
        return _number(field, integral=kind is FieldKind.INT)
    if kind is FieldKind.BOOL:
        return not field.default if isinstance(field.default, bool) else True
    if kind is FieldKind.ENUM:
        return next(iter(getattr(field, 'enum', ())), _UNMADE)
    fixed: dict[FieldKind | None, object] = {
        FieldKind.DECIMAL: Decimal('1.5'),
        FieldKind.TIMEDELTA: timedelta(minutes=10),
        FieldKind.DATE: date(2026, 10, 21),
        FieldKind.DATETIME: datetime(2026, 10, 21, 14, 30),  # noqa: DTZ001 -- an example, with no zone of its own
        FieldKind.TIME: time(14, 30),
        FieldKind.PATH: Path('example'),
        FieldKind.UUID: uuid.UUID(int=1),
    }
    return fixed.get(kind, _UNMADE)


def _string(field: Field) -> object:
    lowest, highest = getattr(field, 'min_length', None), getattr(field, 'max_length', None)
    pattern = getattr(field, 'pattern', None)
    words = [*_WORDS, 'e' * lowest] if lowest else list(_WORDS)
    for word in words:
        if lowest is not None and len(word) < lowest:
            continue
        if highest is not None and len(word) > highest:
            continue
        if pattern is not None and re.fullmatch(pattern, word) is None:
            continue
        return word
    return _UNMADE


def _number(field: Field, *, integral: bool) -> object:
    bounds = {name: getattr(field, name, None) for name in ('ge', 'gt', 'le', 'lt')}
    step = 1 if integral else 0.5
    tried = [1, bounds['ge'], bounds['le']]
    tried += [bounds['gt'] + step if bounds['gt'] is not None else None]
    tried += [bounds['lt'] - step if bounds['lt'] is not None else None]
    for value in tried:
        if value is not None and _within(value, bounds):
            return int(value) if integral else float(value)
    return _UNMADE


def _within(value: float, bounds: dict[str, float | None]) -> bool:
    ge, gt, le, lt = bounds['ge'], bounds['gt'], bounds['le'], bounds['lt']
    return not (
        (ge is not None and value < ge)
        or (gt is not None and value <= gt)
        or (le is not None and value > le)
        or (lt is not None and value >= lt)
    )
