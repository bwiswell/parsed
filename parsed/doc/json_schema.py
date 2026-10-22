"""A command's JSON Schema: seared's load schema, closed, with what only a command says as ``x-`` keys.

:func:`json_schema` is the schema a tool call's arguments fill: seared's ``mode='load'`` document for the command's
fields, closed as a refusing ``load`` is (``unknown='raise'``), each field's bounds and docs among it. On it:

- **each property read by a name** (a ``Name``, or ``Pairs``) has ``x-kind``, its category, and ``x-scope``, the wire
  name of the field that narrows it, when it has one;
- **the command's own** follow its title and description: ``x-phrase``, ``x-extra-phrases``, ``x-effect``,
  ``x-asks``, ``x-interactive``, ``x-instead`` (the phrase an agent says in its place) and ``x-reply`` (its reply's
  class), each only when the command declares it.

Nothing a constrained decoder needs is an ``x-`` key: they say what the command is, not what the call may hold. The
document is built in one order, so the same command gives the same bytes every time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from seared.doc import json_schema as _seared_json_schema

from parsed.command import declaration
from parsed.kinds import Named

from .introspect import is_command_class

if TYPE_CHECKING:
    from parsed.command import Declaration


def json_schema(cls: type) -> dict[str, Any]:
    """The JSON Schema of ``cls``'s arguments, as the module's docstring describes.

    Raises:
        TypeError: ``cls`` isn't a command class, or a field has no JSON Schema (seared's refusal).
        DeclarationError: Its declaration doesn't check.
    """
    if not is_command_class(cls):
        msg = f'json_schema() takes a command class, got {cls!r}'
        raise TypeError(msg)
    found = declaration(cls)
    schema = _seared_json_schema(cls, mode='load', unknown='raise')
    _mark_names(schema, found)
    head = {key: schema[key] for key in ('$schema', 'title', 'description') if key in schema}
    rest = {key: value for key, value in schema.items() if key not in head}
    return {**head, **_own(found), **rest}


def _mark_names(schema: dict[str, Any], found: Declaration) -> None:
    """Give each property read by a name its ``x-kind``, and its ``x-scope`` when it has one."""
    wires = {spec.attr: spec.wire for spec in found.cls.__seared_fields__}
    attrs = {wire: attr for attr, wire in wires.items()}
    for wire, prop in schema.get('properties', {}).items():
        kind = found.field_kinds[attrs[wire]]
        if isinstance(kind, Named):
            prop['x-kind'] = kind.category
            if kind.scope is not None:
                prop['x-scope'] = wires.get(kind.scope, kind.scope)


def _own(found: Declaration) -> dict[str, Any]:
    """The command's own ``x-`` keys, each only where it declares it."""
    own: dict[str, Any] = {'x-phrase': found.phrase}
    if found.extra_phrases:
        own['x-extra-phrases'] = list(found.extra_phrases)
    if found.effect is not None:
        own['x-effect'] = found.effect.value
    if found.asks:
        own['x-asks'] = True
    if found.interactive:
        own['x-interactive'] = True
    if found.instead is not None:
        own['x-instead'] = found.instead.PHRASE
    if found.reply is not None:
        own['x-reply'] = found.reply.__name__
    return own
