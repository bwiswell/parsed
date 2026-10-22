"""``python -m parsed``: parsed's own command line.

::

    python -m parsed check <target> [<target> …] [--max-schema-bytes N]

``check`` runs :func:`parsed.doc.check` on a package's commands, for its CI, and writes the report as JSON on
stdout. It exits ``0`` when every check passed and ``1`` when one didn't. A usage that doesn't read, or a target
that doesn't import, is a JSON error on stderr, ``{"error": "usage", "message": …}``, and exit ``2``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING, NoReturn

from parsed.doc import check
from parsed.doc.check import MAX_SCHEMA_BYTES

if TYPE_CHECKING:
    from collections.abc import Sequence


class _Parser(argparse.ArgumentParser):
    """argparse, its usage errors written as JSON on stderr, exit 2."""

    def error(self, message: str) -> NoReturn:
        _fail(message)


def _fail(message: str) -> NoReturn:
    sys.stderr.write(json.dumps({'error': 'usage', 'message': message}) + '\n')
    raise SystemExit(2)


def main(argv: Sequence[str] | None = None) -> int:
    """Run a verb, as the module's docstring describes, and give its exit code.

    Raises:
        SystemExit: A usage that doesn't read, or a target that doesn't import, exit 2.
    """
    parser = _Parser(prog='python -m parsed', description="parsed's own commands.")
    verbs = parser.add_subparsers(dest='verb', required=True, parser_class=_Parser)
    checking = verbs.add_parser(
        'check',
        help="check a package's commands, for its CI",
        description='Check every command in the targets: the tree, round trips, examples and schemas.',
    )
    checking.add_argument('targets', nargs='+', metavar='target', help='a module or package of commands, by name')
    checking.add_argument(
        '--max-schema-bytes',
        type=int,
        default=MAX_SCHEMA_BYTES,
        help=f"the most bytes a command's schema may take, written compactly (default: {MAX_SCHEMA_BYTES})",
    )
    args = parser.parse_args(argv)
    try:
        report = check(args.targets, max_schema_bytes=args.max_schema_bytes)
    except ImportError as e:
        _fail(f"a target doesn't import: {e}")
    sys.stdout.write(json.dumps(report.to_json(), indent=2) + '\n')
    return 0 if report.ok else 1


if __name__ == '__main__':
    sys.exit(main())
