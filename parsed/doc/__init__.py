"""``parsed.doc``: commands as data, for the tools that read them.

Mirrors ``zeared.doc`` where the meaning matches, so a tool reads a command as it reads a message:

- :func:`is_command_class`, and :func:`introspect_command` giving a :class:`CommandDoc`, with its :class:`SlotDoc`
  and :class:`FlagDoc` entries (``introspect.py``);
- :func:`json_schema`, a command's arguments as a closed JSON Schema (``json_schema.py``).

Discovery is seared's: ``seared.doc.collect(target)`` gives a package's seared classes, and ``is_command_class``
keeps the commands.
"""

from .introspect import CommandDoc, FlagDoc, SlotDoc, introspect_command, is_command_class
from .json_schema import json_schema

__all__ = ['CommandDoc', 'FlagDoc', 'SlotDoc', 'introspect_command', 'is_command_class', 'json_schema']
