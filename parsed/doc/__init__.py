"""``parsed.doc``: commands as data, for the tools that read them.

Mirrors ``zeared.doc`` where the meaning matches, so a tool reads a command as it reads a message:

- :func:`is_command_class`, and :func:`introspect_command` giving a :class:`CommandDoc`, with its :class:`SlotDoc`
  and :class:`FlagDoc` entries (``introspect.py``);
- :func:`json_schema`, a command's arguments as a closed JSON Schema (``json_schema.py``);
- :func:`command_key`, an instance's key for policy, slashed as a topic is, and each phrase's template in
  ``CommandDoc.keys``; :func:`chain_keys`, each of a chain's steps' (``keys.py``);
- a chain as one tool call: :func:`introspect_chain` giving a :class:`ChainDoc`, with its :class:`StepDoc` entries;
  :func:`chain_schema`, its arguments' schema; :func:`load_chain` and :func:`dump_chain`, its arguments to its steps
  and back (``chains.py``);
- :func:`check`, a conformance check of a package's commands for its CI, and ``python -m parsed check``
  (``check.py``);
- a package's reference pages: :func:`render_command`, a command's page (``render.py``); :func:`document`, any class's,
  and :func:`build_docs`, the whole set over seared's pipeline, with ``python -m parsed.doc`` (``generate.py``).

Discovery is seared's: ``seared.doc.collect(target)`` gives a package's seared classes, and ``is_command_class``
keeps the commands.
"""

from .chains import ChainDoc, StepDoc, chain_schema, dump_chain, introspect_chain, load_chain
from .check import CheckReport, Problem, check
from .generate import build_docs, document
from .introspect import CommandDoc, FlagDoc, SlotDoc, introspect_command, is_command_class
from .json_schema import json_schema
from .keys import chain_keys, command_key
from .render import render_command

__all__ = [
    'ChainDoc',
    'CheckReport',
    'CommandDoc',
    'FlagDoc',
    'Problem',
    'SlotDoc',
    'StepDoc',
    'build_docs',
    'chain_keys',
    'chain_schema',
    'check',
    'command_key',
    'document',
    'dump_chain',
    'introspect_chain',
    'introspect_command',
    'is_command_class',
    'json_schema',
    'load_chain',
    'render_command',
]
