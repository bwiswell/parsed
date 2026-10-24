"""Tests for ``parsed/doc/__main__.py``: ``python -m parsed.doc``."""

import os
import subprocess
import sys
from pathlib import Path

TESTS = Path(__file__).parent.parent


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(TESTS), os.environ.get('PYTHONPATH', '')])}
    command = [sys.executable, '-m', 'parsed.doc', *argv]
    return subprocess.run(command, capture_output=True, text=True, env=env, check=False)


def test_it_writes_a_package_s_pages_then_checks_them(tmp_path):
    out = str(tmp_path / 'commands')
    written = _run('_support_protocol', '-o', out)
    assert (written.returncode, written.stdout.split(' written')[0]) == (0, '3')
    assert _run('_support_protocol', '-o', out, '--check').returncode == 0
    assert (tmp_path / 'commands' / 'HandheldConnect.md').exists()
