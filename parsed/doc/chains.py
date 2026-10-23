"""A chain as data: what it holds, its JSON Schema, and a tool call's arguments loaded to its steps and back.

A chain's steps (the commands beneath a base that declares ``STEPS = True``) are one order, so a tool calls them as
one: the chain's shared fields once, and ``steps``, an array of its steps, each tagged by its phrase's words after
the shared part, never by a class name:

.. code-block:: json

    {"fleet": "f1", "steps": [{"step": "jump", "system": "sol"}, {"step": "move", "to": "sol-belt"},
                              {"step": "mine"}]}

- :func:`introspect_chain` gives a :class:`ChainDoc`: the base, its shared fields and slots, each step's
  :class:`StepDoc` (its tag, its words, its :class:`~parsed.doc.CommandDoc`), and the chain's effect, the strongest
  of its steps', and whether any step asks;
- :func:`chain_schema` is the schema those arguments fill, closed as a command's is;
- :func:`load_chain` reads the arguments to the steps' instances, each given the shared fields, and
  :func:`dump_chain` writes steps back to them.

A chain's steps are a tree's (:attr:`parsed.tree.Tree.chains`): a mount's tree holds the steps it was given. Its
line is :meth:`parsed.tree.Tree.render`'s, given the steps, and each step's key for policy :func:`chain_keys`'s.

**What's refused** (a ``DeclarationError``, when the doc or the schema is built): two steps tagged alike, a step
whose phrase says no words after the shared part, a step field on the tag's wire name (``step``), and a shared
field on the steps' (``steps``). A tree that only reads lines is never held to them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from seared import ValidationError
from seared.doc import introspect as _seared_introspect

from parsed._phrase import Word
from parsed._walk._walker import _shared, _slot_text, head_of
from parsed.command import Command, declaration, is_chain_base
from parsed.errors import DeclarationError

from .introspect import introspect_command
from .json_schema import json_schema

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from seared.doc import SchemaDoc

    from parsed.command import Declaration
    from parsed.effect import Effect
    from parsed.tree import Tree

    from .introspect import CommandDoc, SlotDoc

#: The key each step is tagged by, in a chain's arguments.
TAG = 'step'

#: The key a chain's steps stand under.
STEPS = 'steps'

#: seared's words for a key a refusing ``load`` doesn't know, and for one a class requires.
_UNKNOWN, _MISSING = 'unknown key', 'required key missing'


@dataclass(frozen=True, slots=True)
class StepDoc:
    """A step of a chain.

    Attributes:
        tag: Its words after the chain's shared part, as its ``PHRASE`` says them: ``jump``, ``jump nearest``.
        phrase: Its ``PHRASE`` after the shared part, slots and all: ``jump {system}``.
        command: Its :class:`~parsed.doc.CommandDoc`.
    """

    tag: str
    phrase: str
    command: CommandDoc


@dataclass(frozen=True, slots=True)
class ChainDoc:
    """A chain, as data.

    Attributes:
        base: The chain's base, the class that declares ``STEPS = True``.
        schema: seared's ``SchemaDoc`` of the base: the shared fields.
        shared: The shared fields, by attribute name, in the order the base declares them.
        heads: The shared parts its steps' phrases say, each once: ``fleet {fleet}``, a twin's
            ``detachment {detachment}``.
        slots: The slots of those parts, each name once.
        steps: Each step, in the tree's order.
        effect: The strongest of its steps' effects; ``None`` where any step declares none, never inferred.
        asks: Whether any step may ask before it acts.
    """

    base: type[Command]
    schema: SchemaDoc
    shared: tuple[str, ...]
    heads: tuple[str, ...]
    slots: tuple[SlotDoc, ...]
    steps: tuple[StepDoc, ...]
    effect: Effect | None
    asks: bool


def introspect_chain(tree: Tree, base: type) -> ChainDoc:
    """The :class:`ChainDoc` of ``base``'s chain, its steps those among ``tree``'s commands.

    Raises:
        TypeError: ``base`` isn't a chain's base with steps in ``tree``.
        DeclarationError: Its steps can't be told apart by their words, or a key is taken (see the module).
    """
    steps = tree.chains.get(base) if is_chain_base(base) else None
    if not steps:
        msg = f"introspect_chain() takes a chain's base with steps among the tree's commands, got {base!r}"
        raise TypeError(msg)
    chain: type[Command] = steps[0].chain  # ty: ignore[invalid-assignment] -- a step's chain is its base
    shared = _shared(chain)
    wires = {spec.wire for spec in chain.__seared_fields__}
    if STEPS in wires:
        msg = f"{chain.__qualname__} has a field on {STEPS!r}, the key a chain's steps stand under"
        raise DeclarationError(msg)
    found: dict[str, StepDoc] = {}
    heads: dict[str, None] = {}
    slots: dict[str, SlotDoc] = {}
    for step in steps:
        doc = introspect_command(step.cls)
        tag, phrase = _words(step, shared)
        if tag in found:
            other = found[tag].command.phrase
            msg = (
                f"{other!r} and {step.phrase!r} are both tagged {tag!r} in {chain.__qualname__}'s chain: a tool call "
                f"tells a chain's steps by their words after its shared part"
            )
            raise DeclarationError(msg)
        if any(spec.wire == TAG and spec.attr not in shared for spec in step.cls.__seared_fields__):
            msg = f"{step.cls.__qualname__} has a field on {TAG!r}, the key a chain's steps are tagged by"
            raise DeclarationError(msg)
        found[tag] = StepDoc(tag=tag, phrase=phrase, command=doc)
        for bound in step.phrases:
            parts = bound.phrase.parts[: head_of(bound, shared)]
            heads.setdefault(' '.join(part.text if isinstance(part, Word) else _slot_text(part) for part in parts))
            named = {part.name for part in parts if not isinstance(part, Word)}
            for slot in doc.slots:
                if slot.name in named:
                    slots.setdefault(slot.name, slot)
    effects = [step.command.effect for step in found.values()]
    return ChainDoc(
        base=chain,
        schema=_seared_introspect(chain),
        shared=tuple(spec.attr for spec in chain.__seared_fields__),
        heads=tuple(heads),
        slots=tuple(slots.values()),
        steps=tuple(found.values()),
        effect=None if any(effect is None for effect in effects) else max(e for e in effects if e is not None),
        asks=any(step.command.asks for step in found.values()),
    )


def chain_schema(tree: Tree, base: type) -> dict[str, Any]:
    """The JSON Schema of a tool call of ``base``'s chain: its shared fields, and ``steps``, a tagged union's array.

    Each step's branch is its command's schema (:func:`~parsed.doc.json_schema`) without the shared fields, its tag
    a ``const``, closed; ``anyOf`` joins them, which constrained decoders hold. The chain's ``x-effect`` and
    ``x-asks`` follow its title and description. On a step: ``x-moves``, the field that moves the chain on (or
    ``true``), and ``x-follows`` on each property looked for where the chain will be by then.

    Raises:
        TypeError: ``base`` isn't a chain's base with steps in ``tree``, or a field has no JSON Schema.
        DeclarationError: As for :func:`introspect_chain`.
    """
    doc = introspect_chain(tree, base)
    chain = doc.base
    wires = {spec.attr: spec.wire for spec in chain.__seared_fields__}
    shared = set(wires.values())
    first = json_schema(doc.steps[0].command.schema.cls)
    properties = {wire: prop for wire, prop in first.get('properties', {}).items() if wire in shared}
    required = [wire for wire in first.get('required', ()) if wire in shared]
    defs: dict[str, Any] = {}
    branches = [_branch(step, shared, defs) for step in doc.steps]
    out: dict[str, Any] = {'$schema': first['$schema'], 'title': chain.__name__}
    if doc.schema.doc:
        out['description'] = doc.schema.doc
    if doc.effect is not None:
        out['x-effect'] = doc.effect.value
    if doc.asks:
        out['x-asks'] = True
    steps = {'type': 'array', 'description': 'the steps, in order', 'minItems': 1, 'items': {'anyOf': branches}}
    out.update(
        type='object',
        properties={**properties, STEPS: steps},
        required=[*required, STEPS],
        unevaluatedProperties=False,
    )
    if defs:
        out['$defs'] = dict(sorted(defs.items()))
    return out


def _branch(step: StepDoc, shared: set[str], defs: dict[str, Any]) -> dict[str, Any]:
    """A step's branch of a chain's schema: its own properties, its tag first, closed; its ``$defs`` to ``defs``."""
    cls = step.command.schema.cls
    schema = json_schema(cls)
    found = declaration(cls)
    wires = {spec.attr: spec.wire for spec in cls.__seared_fields__}
    follows = {wires[attr] for attr, kind in found.field_kinds.items() if getattr(kind, 'follows', False)}
    properties: dict[str, Any] = {TAG: {'const': step.tag}}
    for wire, prop in schema.get('properties', {}).items():
        if wire not in shared:
            properties[wire] = {**prop, 'x-follows': True} if wire in follows else prop
    for name, definition in schema.get('$defs', {}).items():
        if defs.setdefault(name, definition) != definition:
            msg = f"two classes named {name} in a chain's schema: their definitions would share one name"
            raise TypeError(msg)
    branch: dict[str, Any] = {}
    if 'description' in schema:
        branch['description'] = schema['description']
    if found.moves is not False:
        branch['x-moves'] = True if found.moves is True else wires[found.moves]
    if found.asks:
        branch['x-asks'] = True
    branch.update(
        type='object',
        properties=properties,
        required=[TAG, *(wire for wire in schema.get('required', ()) if wire not in shared)],
        unevaluatedProperties=False,
    )
    return branch


def load_chain(tree: Tree, base: type, data: Mapping[str, Any]) -> list[Command]:
    """A tool call of ``base``'s chain, read to its steps' instances, each given the shared fields.

    Every key is checked, as a refusing ``load`` checks them: an unknown one, a shared field inside a step (it's
    given once, at the top), a step with no tag or one the chain hasn't, and each step's own values, by seared.

    Raises:
        TypeError: As for :func:`introspect_chain`.
        ValidationError: ``data`` isn't a call of the chain; its path is the key at fault: ``steps[1].system``.
    """
    doc = introspect_chain(tree, base)
    name = doc.base.__name__
    if not isinstance(data, dict):
        msg = f'expected object, got {type(data).__name__}'
        raise ValidationError(msg, cls_name=name)
    shared = {spec.wire for spec in doc.base.__seared_fields__}
    for key in data:
        if key not in shared and key != STEPS:
            raise ValidationError(_UNKNOWN, path=(key,), cls_name=name)
    if STEPS not in data:
        raise ValidationError(_MISSING, path=(STEPS,), cls_name=name)
    said = data[STEPS]
    if not isinstance(said, list) or not said:
        msg = 'expected a list of steps, one at least' if isinstance(said, list) else f'expected array, got {said!r}'
        raise ValidationError(msg, path=(STEPS,), cls_name=name)
    steps = zip(doc.steps, tree.chains[doc.base], strict=True)
    call = _Call(name, {step.tag: found.cls for step, found in steps}, shared, data)
    return [call.step(item, (STEPS, at)) for at, item in enumerate(said)]


@dataclass(frozen=True, slots=True)
class _Call:
    """A chain's call, as its steps are loaded: the chain's name, its steps by tag, and the shared fields."""

    name: str
    tags: Mapping[str, type[Command]]
    shared: set[str]
    data: Mapping[str, Any]

    def step(self, item: object, path: tuple[str | int, ...]) -> Command:
        """One step, loaded with the shared fields given at the top; refused with its path within the call."""
        if not isinstance(item, dict):
            msg = f'expected object, got {type(item).__name__}'
            raise ValidationError(msg, path=path, cls_name=self.name)
        if TAG not in item:
            raise ValidationError(_MISSING, path=(*path, TAG), cls_name=self.name)
        cls = self.tags.get(item[TAG]) if isinstance(item[TAG], str) else None
        if cls is None:
            msg = f'no step {item[TAG]!r}: one of {", ".join(self.tags)}'
            raise ValidationError(msg, path=(*path, TAG), cls_name=self.name)
        own = {key: value for key, value in item.items() if key != TAG}
        for key in own:
            if key in self.shared:
                msg = "a chain's shared field, given once, at the top"
                raise ValidationError(msg, path=(*path, key), cls_name=self.name)
        given = {key: value for key, value in self.data.items() if key in self.shared}
        try:
            return cls.load({**given, **own}, unknown='raise')
        except ValidationError as e:
            at = e.path if e.path and e.path[0] in self.shared else (*path, *e.path)
            raise ValidationError(e.reason, path=at, cls_name=self.name) from e


def dump_chain(steps: Sequence[Command]) -> dict[str, Any]:
    """A chain's steps as a tool call's arguments, as :func:`load_chain` reads them.

    The shared fields come once, then each step tagged, its own fields as seared dumps them.

    Raises:
        TypeError: ``steps`` is empty, or they aren't one chain's.
        ValueError: They don't share the chain's fields' values.
    """
    if not steps:
        msg = "dump_chain() takes a chain's steps, one at least"
        raise TypeError(msg)
    founds = [declaration(type(step)) for step in steps]
    chain = founds[0].chain
    if chain is None or any(found.chain is not chain for found in founds):
        msg = f"dump_chain() takes one chain's steps, got {list(steps)!r}"
        raise TypeError(msg)
    attrs = _shared(chain)
    for attr in sorted(attrs):
        if any(getattr(step, attr) != getattr(steps[0], attr) for step in steps):
            msg = f"a chain's steps share {chain.__qualname__}'s fields: its steps' {attr} differ"
            raise ValueError(msg)
    wires = [type(step).dump(step) for step in steps]
    shared = {spec.wire for spec in chain.__seared_fields__}
    out: dict[str, Any] = {key: value for key, value in wires[0].items() if key in shared}
    out[STEPS] = [
        {TAG: _words(found, attrs)[0], **{key: value for key, value in wire.items() if key not in shared}}
        for found, wire in zip(founds, wires, strict=True)
    ]
    return out


def head_text(found: Declaration) -> str:
    """The shared part a step's ``PHRASE`` says, as it writes it: ``fleet {fleet}``."""
    bound = found.phrases[0]
    parts = bound.phrase.parts[: head_of(bound, _shared(found.chain or found.cls))]
    return ' '.join(part.text if isinstance(part, Word) else _slot_text(part) for part in parts)


def _words(found: Declaration, shared: frozenset[str]) -> tuple[str, str]:
    """A step's tag and its phrase after the chain's shared part, by its ``PHRASE``.

    Raises:
        DeclarationError: Its phrase says no words there.
    """
    bound = found.phrases[0]
    parts = bound.phrase.parts[head_of(bound, shared) :]
    tag = ' '.join(part.text for part in parts if isinstance(part, Word))
    if not tag:
        msg = (
            f"{found.cls.__qualname__}: {found.phrase!r} says no words after its chain's shared part, and a tool call "
            f'tells a step by them'
        )
        raise DeclarationError(msg)
    return tag, ' '.join(part.text if isinstance(part, Word) else _slot_text(part) for part in parts)
