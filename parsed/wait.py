"""Waiting on a read: ``--until`` conditions on its reply, ``--timeout``, how long to wait, and ``--watch``.

**A command can wait** when it declares ``EFFECT = READ`` and a ``REPLY``: running a read again is known to be
safe, and its reply has typed values for a condition to read. On it, ``--until PATH=VALUE`` is a condition on the
reply, in ``tooled wait``'s grammar, so an agent learns one:

- **the path** is dotted (``docked``, ``cargo.iron``), a whole number stepping into a list (``ships.0.name``);
- **the value** is read as JSON if it reads as JSON (``40``, ``true``, ``null``, ``"30%"``), else as a string
  (``idle``), and compared as JSON compares (``40`` is ``40.0``, never ``true``);
- **several conditions,** each its own ``--until``, must all hold.

Each path is checked against the reply's dump schema (seared's, ``mode='dump'``) when the line is read, before
anything runs, with what may have been meant. ``--timeout`` is how long to wait, a span of time (``90s``, ``2m``),
:data:`TIMEOUT` seconds by default.

**Watching** (``--watch``) gives the reply now, then again each time it changes, until ``--count N`` replies, the
bound, the conditions (with ``--until``), or a signal. Without conditions a watch has no bound, unless
``--timeout`` gives one.

**The flags are a tree's** once any of its commands can wait, as a line's flags are split before its command is
known: ``--watch`` a switch, the others taking a value. A command that can wait can't take any of their names for a
field. On any other command, a field of its own may take them; without one, the flag is refused, saying why the
command can't wait.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Any

from seared.doc import json_schema

if TYPE_CHECKING:
    from collections.abc import Sequence

    from seared import Seared

#: The flags a wait takes, which a tree takes once any of its commands can wait.
FLAGS = ('until', 'timeout', 'watch', 'count')

#: Those of :data:`FLAGS` that are switches; the others take a value.
SWITCHES = frozenset({'watch'})

#: How long a wait waits, in seconds, unless ``--timeout`` says.
TIMEOUT = 30.0

#: The names a refusal lists, at most, where a path left the schema.
_LISTED = 8

#: A scalar's JSON Schema types: a path that goes on past one names nothing.
_SCALARS = frozenset({'string', 'number', 'integer', 'boolean', 'null'})


@dataclass(frozen=True, slots=True)
class Condition:
    """One ``--until``: a path into the reply's wire form, and the value it must hold there.

    Attributes:
        path: The path's parts: a field's name, or a whole number for a list's element.
        value: The value it must hold, as JSON reads it.
        text: The condition as given, ``path=value``.
    """

    path: tuple[str, ...]
    value: object
    text: str

    @classmethod
    def parse(cls, text: str) -> Condition:
        """A condition from ``path=value``: a dotted path, and its value, read as JSON if it reads as JSON.

        Raises:
            ValueError: No ``=``, or a path with an empty part.
        """
        path, sep, raw = text.partition('=')
        parts = tuple(path.split('.'))
        if not sep or not all(parts):
            msg = f'a condition is path=value, the path dotted (docked, cargo.iron), not {text!r}'
            raise ValueError(msg)
        try:
            value = json.loads(raw)
        except ValueError:
            value = raw
        return cls(parts, value, text)

    def find(self, wire: object) -> tuple[bool, object]:
        """Whether ``wire`` (a reply's wire form) has the path, and what it holds there."""
        found = wire
        for part in self.path:
            if isinstance(found, dict) and part in found:
                found = found[part]
            elif isinstance(found, list) and part.isdigit() and int(part) < len(found):
                found = found[int(part)]
            else:
                return False, None
        return True, found

    def met(self, wire: object) -> bool:
        """Whether ``wire`` holds the condition's value at its path."""
        found, held = self.find(wire)
        return found and _equal(held, self.value)


@dataclass(frozen=True, slots=True)
class Wait:
    """A read's wait: the conditions its reply must meet, every one, how long to wait, and whether to watch.

    Attributes:
        until: The conditions, in the order given; none, for a watch until its count, its bound or a signal.
        timeout: How long to wait, in seconds; ``None`` for a watch with no bound.
        watch: Whether to give each reply as it changes (``--watch``), rather than the last.
        count: How many replies a watch gives, at most; ``None`` for no count.
    """

    until: tuple[Condition, ...]
    timeout: float | None = TIMEOUT
    watch: bool = False
    count: int | None = None

    def met(self, reply: Seared) -> bool:
        """Whether ``reply`` meets every condition, read in its wire form as seared dumps it."""
        wire = type(reply).dump(reply)
        return all(condition.met(wire) for condition in self.until)


def problem(condition: Condition, reply: type[Seared]) -> tuple[str, list[str]] | None:
    """Why ``condition``'s path names nothing in ``reply``'s dump schema, and what may have been meant.

    ``None`` when it names a field, or reaches a shape the schema doesn't say, which a path may name anything in.
    """
    schema = _schema(reply)
    node: object = schema
    for at, part in enumerate(condition.path):
        offer = _offer(schema, node)
        if offer is None:
            return None
        names, items, keys = offer
        if part.isdigit() and items is not None:
            node = items
        elif part in names:
            node = names[part]
        elif keys is not None:
            node = keys
        else:
            return _refusal(condition, at, list(names), reply, listed=items is not None)
    return None


def _refusal(
    condition: Condition, at: int, names: Sequence[str], reply: type[Seared], *, listed: bool
) -> tuple[str, list[str]]:
    where, missing = '.'.join(condition.path[:at]), condition.path[at]
    said = f'--until {".".join(condition.path)!r} names no field of {reply.__name__}'
    near = difflib.get_close_matches(missing, names, n=3, cutoff=0.6)
    if listed:
        return f'{said}; {where!r} is a list: {where}.0.{missing}', []
    if near:
        return f'{said}; did you mean {" or ".join(map(repr, near))}?', near
    if names:
        shown = ', '.join(names[:_LISTED]) + (', …' if len(names) > _LISTED else '')
        return f'{said}; the fields {f"of {where!r}" if where else "there"}: {shown}', list(names)
    return f'{said}; {where!r} has no fields', []


@cache
def _schema(reply: type[Seared]) -> dict[str, Any]:
    return json_schema(reply, mode='dump')


def _offer(schema: dict[str, Any], node: object) -> tuple[dict[str, Any], object, object] | None:
    """What a JSON Schema node lets a path name next: its fields, a list's items, a map's values.

    ``None`` for a shape the walk doesn't read, which a path may name anything in.
    """
    node = _deref(schema, node)
    if not isinstance(node, dict):
        return None
    names: dict[str, Any] = {}
    items: object = None
    keys: object = None
    found = False
    if isinstance(node.get('properties'), dict):
        names.update(node['properties'])
        found = True
    if isinstance(node.get('additionalProperties'), dict):
        keys, found = node['additionalProperties'], True
    if node.get('type') == 'array' and isinstance(node.get('items'), dict):
        items, found = node['items'], True
    branches = [*node.get('anyOf', ()), *node.get('oneOf', ()), *node.get('allOf', ())]
    for branch in branches:
        if not isinstance(branch, dict) or branch.get('type') == 'null':
            continue
        inner = _offer(schema, branch)
        if inner is None:
            return None
        names.update(inner[0])
        items = items if inner[1] is None else inner[1]
        keys = keys if inner[2] is None else inner[2]
        found = True
    if found or _is_scalar(node):
        return names, items, keys
    return None


def _is_scalar(node: dict[str, Any]) -> bool:  # a JSON Schema node
    kind = node.get('type')
    if isinstance(kind, list):
        return bool(kind) and set(kind) <= _SCALARS
    return kind in _SCALARS or 'enum' in node or 'const' in node


def _deref(schema: dict[str, Any], node: object) -> object:
    """A JSON Schema node, its ``$ref`` to the schema's own ``$defs`` followed."""
    seen: set[str] = set()
    while isinstance(node, dict) and isinstance(node.get('$ref'), str) and node['$ref'] not in seen:
        seen.add(node['$ref'])
        node = schema.get('$defs', {}).get(node['$ref'].removeprefix('#/$defs/'), {})
    return node


def _equal(a: object, b: object) -> bool:  # JSON-ready values
    """JSON's equality: a number is no boolean, though Python's ``True == 1``; ``40`` equals ``40.0``."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, int | float) and isinstance(b, int | float):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_equal(a[key], b[key]) for key in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b, strict=True))
    return type(a) is type(b) and a == b
