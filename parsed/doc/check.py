"""``parsed check``: a conformance check of a package's commands, for its CI.

:func:`check` builds the tree of every command in the targets (modules or packages, by name), then checks each
command:

- **the tree builds:** every phrase reads and binds, no two read a line two ways, and every flag means one thing;
- **round trips:** two instances made from its fields' types and constraints (or a kind's own example,
  :meth:`parsed.kinds.Kind.example`), one with only its required fields and one with every field it can give a
  value, each render to a line that reads back to it;
- **its examples:** each line of its ``EXAMPLES`` reads to it, a ``<name>`` placeholder standing for any value. A
  line with no placeholder loads too;
- **its schema:** ``json_schema`` builds and takes its example: the instance's wire form has only keys it names,
  and each it requires, and loads back to it. It holds as a constrained decoder needs it to: closed, each ``enum``
  a list of distinct JSON scalars, a field of choices (an ``Enum``'s) an ``enum``, and compact, at most
  ``max_schema_bytes`` written compactly.

Then each chain (:attr:`parsed.tree.Tree.chains`), from the same examples. Its steps are grouped by the shared part
their phrase says (``fleet {fleet}``), since a later step reads under its first's; each group gives one chain of
every step's instance with only its required fields, and one of every step's with every field it can give, each step
in the tree's order.

- **round trips:** each renders to a line that reads back to its steps;
- **its schema:** ``chain_schema`` builds, closed, each step's branch closed and tagged by a ``const``, at most
  ``max_chain_bytes``; and each chain, dumped as a tool call (``dump_chain``), has only keys the schema names, each it
  requires, and loads back to its steps (``load_chain``).

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

from parsed.command import declaration
from parsed.errors import DeclarationError, ReadError, RenderError
from parsed.kinds import Choice
from parsed.tree import Tree

from .chains import TAG, chain_schema, dump_chain, head_text, load_chain
from .json_schema import json_schema

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from seared import Field

    from parsed.command import Command, Declaration

#: The most bytes a command's schema may take, written compactly, unless the check is told otherwise.
MAX_SCHEMA_BYTES = 2048

#: The most bytes a chain's schema may take, written compactly: a union of its steps, so more than a command's.
MAX_CHAIN_BYTES = 8192

_PLACEHOLDER = re.compile(r'<[^<>\s]+>')

#: Words a string's example is tried as, in turn, against its lengths and its pattern.
_WORDS = ('example', 'a', 'x', '1', 'a1', 'example-1', 'ex')

#: Stands for a value no example could be made for.
_UNMADE = object()


@dataclass(frozen=True, slots=True)
class Problem:
    """A check a command failed.

    Attributes:
        check: Which: ``tree``, ``round-trip``, ``example``, ``schema`` or ``chain``.
        message: What's wrong.
        command: The command's class, by module and name (a chain's base, for a chain's); ``None`` for the tree's
            own.
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
        chains: How many chains were checked, each its round trips and its schema.
        skipped: The commands with no round trips, by module and name, each with the fields that had no example.
        problems: Each check a command failed.
    """

    targets: tuple[str, ...]
    commands: int
    round_trips: int
    examples: int
    schemas: int
    chains: int
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
            'checked': {
                'round-trips': self.round_trips,
                'examples': self.examples,
                'schemas': self.schemas,
                'chains': self.chains,
            },
            'skipped': {command: list(fields) for command, fields in self.skipped.items()},
            'problems': [problem.to_json() for problem in self.problems],
        }


def check(
    targets: Sequence[str], *, max_schema_bytes: int = MAX_SCHEMA_BYTES, max_chain_bytes: int = MAX_CHAIN_BYTES
) -> CheckReport:
    """Check every command in ``targets``, and every chain, as the module's docstring describes.

    Raises:
        ImportError: A target doesn't import.
    """
    try:
        tree = Tree.collect(*targets)
    except DeclarationError as e:
        return CheckReport(tuple(targets), 0, 0, 0, 0, 0, {}, (Problem('tree', str(e)),))
    checking = _Checking(tree, max_schema_bytes, max_chain_bytes)
    for found in tree.commands:
        checking.command(found)
    for base, steps in tree.chains.items():
        checking.chain(base, steps)
    if not tree.commands:
        checking.problems.append(Problem('tree', f'no commands in {", ".join(targets)}'))
    return CheckReport(
        targets=tuple(targets),
        commands=len(tree.commands),
        round_trips=checking.round_trips,
        examples=checking.examples,
        schemas=checking.schemas,
        chains=checking.chains,
        skipped=checking.skipped,
        problems=tuple(checking.problems),
    )


class _Checking:
    """One check's tally, as it goes."""

    def __init__(self, tree: Tree, max_schema_bytes: int, max_chain_bytes: int) -> None:
        self.tree, self.max_schema_bytes, self.max_chain_bytes = tree, max_schema_bytes, max_chain_bytes
        self.round_trips = self.examples = self.schemas = self.chains = 0
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

    def chain(self, base: type, steps: Sequence[Declaration]) -> None:
        name = f'{base.__module__}.{base.__qualname__}'
        self.chains += 1
        groups: dict[str, list[Declaration]] = {}
        for step in steps:
            groups.setdefault(head_text(step), []).append(step)
        chains: list[list[Command]] = []
        for group in groups.values():
            made = [instances for instances, unmade in (_instances(step.cls) for step in group) if not unmade]
            if made:
                required, every = [found[0] for found in made], [found[-1] for found in made]
                chains += [required] if every == required else [required, every]
        for chain in chains:
            self._chain_trip(name, chain)
        try:
            schema = chain_schema(self.tree, base)
        except (TypeError, DeclarationError) as e:
            self.problems.append(Problem('chain', f"its schema doesn't build: {e}", name))
            return
        size = len(json.dumps(schema, separators=(',', ':')))
        if size > self.max_chain_bytes:
            msg = (
                f'its schema takes {size} bytes, over {self.max_chain_bytes}: a decoder holds a compact one more easily'
            )
            self.problems.append(Problem('chain', msg, name))
        self.problems.extend(Problem('chain', msg, name) for msg in _chain_shape(schema))
        for chain in chains:
            self._chain_call(name, base, schema, chain)

    def _chain_trip(self, name: str, chain: list[Command]) -> None:
        """A chain rendered to its line, and read back to its steps."""
        try:
            line = self.tree.render(chain)
        except RenderError as e:
            self.problems.append(Problem('chain', f"{chain!r} doesn't render: {e}", name))
            return
        try:
            back = [step.load() for step in self.tree.walk(line).steps]
        except ReadError as e:
            self.problems.append(Problem('chain', f"it doesn't read back: {e}", name, line))
            return
        if back != chain:
            self.problems.append(Problem('chain', f'it reads back as {back!r}, not {chain!r}', name, line))

    def _chain_call(self, name: str, base: type, schema: dict[str, Any], chain: list[Command]) -> None:
        """A chain dumped as a tool call: only keys its schema names, each it requires, loaded back to its steps."""
        data = dump_chain(chain)
        faults = _unnamed(schema, data)
        branches = {
            branch['properties'][TAG]['const']: branch for branch in schema['properties']['steps']['items']['anyOf']
        }
        for at, item in enumerate(data['steps']):
            faults += [f'steps[{at}]: {fault}' for fault in _unnamed(branches.get(item[TAG], {}), item)]
        if faults:
            self.problems.append(Problem('chain', f"its schema doesn't take its call: {'; '.join(faults)}", name))
            return
        try:
            back = load_chain(self.tree, base, data)
        except SearedError as e:
            self.problems.append(Problem('chain', f"its call doesn't load: {e}", name))
            return
        if back != chain:
            self.problems.append(Problem('chain', f'its call loads as {back!r}, not {chain!r}', name))


def _named(found: Declaration) -> str:
    return f'{found.cls.__module__}.{found.cls.__qualname__}'


def _unnamed(schema: Mapping[str, Any], data: Mapping[str, object]) -> list[str]:
    """What keeps ``schema``'s object from taking ``data``: keys it doesn't name, and keys it requires but lacks."""
    unnamed = sorted(set(data) - set(schema.get('properties', {})))
    missing = sorted(set(schema.get('required', ())) - set(data))
    return [f'{unnamed} not among its properties'] * bool(unnamed) + [f'{missing} required but not there'] * bool(
        missing
    )


def _chain_shape(schema: dict[str, Any]) -> list[str]:
    """What keeps a constrained decoder from holding a chain's ``schema``: each fault, said."""
    faults = []
    if schema.get('type') != 'object' or schema.get('unevaluatedProperties') is not False:
        faults.append("it isn't a closed object: a decoder would give keys the chain doesn't take")
    for branch in schema.get('properties', {}).get('steps', {}).get('items', {}).get('anyOf', ()):
        tag = branch.get('properties', {}).get(TAG, {}).get('const')
        if not isinstance(tag, str) or branch.get('unevaluatedProperties') is not False:
            faults.append(f'step {tag!r} is not a closed object tagged by a const')
    faults += [f'{at}: {fault}' for at, values in _enums(schema) if (fault := _enum_fault(values)) is not None]
    return faults


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
    kinds = declaration(cls).field_kinds
    for spec in cls.__seared_fields__:
        value = _example(spec.field, kinds[spec.attr].example(spec.field))
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


def _example(field: Field, own: object = None) -> object:
    """A value for ``field``, or ``_UNMADE``: a list of one, a dict of one pair.

    Its kind's own example (``own``), where it gives one; else one made from its type and constraints.
    """
    value = _scalar(field) if own is None else own
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
