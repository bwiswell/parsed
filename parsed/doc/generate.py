"""A package's command reference, in Markdown, over seared's doc pipeline.

parsed reuses seared's pipeline whole, as ``zeared.doc`` does: its discovery (every seared class a package holds, and
those they reference), its paths (a page a class, mirroring the package's modules), its links, its index and its
``--check``. Only the page differs: a command gets its reference page (:func:`parsed.doc.render.render_command`),
and any other seared class (a ``REPLY``, a request a command inherits, a base's fields) seared's own.

``python -m parsed.doc <package> -o docs/commands`` writes the pages; ``--check`` exits 1 when they've drifted, for
an app's CI; ``--require-docs`` exits 1 first when a field has no ``doc=``, as seared's does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from seared.doc import document as _seared_document
from seared.doc.generate import build_docs as _seared_build_docs
from seared.doc.generate import main as _seared_main

from .introspect import is_command_class
from .render import LinkFor, _default_link, render_command

if TYPE_CHECKING:
    from seared import Seared


def render_one(cls: type[Seared], link_for: LinkFor) -> str:
    """One class's page: a command's reference page, else seared's."""
    if is_command_class(cls):
        return render_command(cls, link_for)
    return _seared_document(cls, link_for=link_for)


def document(cls: type[Seared], *, link_for: LinkFor = _default_link) -> str:
    """Markdown for one class: a command's reference page, else seared's."""
    return render_one(cls, link_for)


def build_docs(target: str) -> dict[str, str]:
    """Every page for ``target``, a module or package by name, by its path: ``{'FleetMine.md': …, 'index.md': …}``."""
    return _seared_build_docs(target, render_one=render_one)


def main(argv: list[str] | None = None) -> int:
    """``python -m parsed.doc``: the exit code."""
    return _seared_main(argv, render_one=render_one, prog='python -m parsed.doc')
