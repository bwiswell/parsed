"""``python -m parsed.doc <package>``: a package's command reference pages, written or checked (``generate.py``)."""

import sys

from .generate import main

if __name__ == '__main__':
    sys.exit(main())
