"""Tests for ``parsed/__main__.py``: ``python -m parsed``."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from parsed.__main__ import main

TESTS = Path(__file__).parent


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(TESTS), os.environ.get('PYTHONPATH', '')])}
    return subprocess.run([sys.executable, '-m', 'parsed', *argv], capture_output=True, text=True, env=env, check=False)


class TestMain:
    def test_a_clean_package(self, capsys):
        assert main(['check', '_support_farlandia', '_support_rio']) == 0
        report = json.loads(capsys.readouterr().out)
        assert (report['ok'], report['commands']) == (True, 17)

    def test_problems_exit_1(self, capsys):
        assert main(['check', '_support_check.round_trip']) == 1
        (problem,) = json.loads(capsys.readouterr().out)['problems']
        assert problem['check'] == 'round-trip'

    def test_the_schema_bound(self, capsys):
        assert main(['check', '_support_rio', '--max-schema-bytes', '100']) == 1
        assert json.loads(capsys.readouterr().out)['problems'][0]['check'] == 'schema'

    def test_the_chain_s_bound(self, capsys):
        assert main(['check', '_support_farlandia', '--max-chain-bytes', '100']) == 1
        (problem,) = json.loads(capsys.readouterr().out)['problems']
        assert (problem['check'], problem['command']) == ('chain', '_support_farlandia.FleetCommand')

    @pytest.mark.parametrize(
        ('argv', 'says'),
        [
            (['check', '_support_nowhere'], "a target doesn't import: No module named '_support_nowhere'"),
            (['check'], 'the following arguments are required: target'),
            ([], 'the following arguments are required: verb'),
            (['chek', '_support_rio'], "argument verb: invalid choice: 'chek' (choose from check)"),
            (['check', '_support_rio', '--max-schema-bytes', 'lots'], "invalid int value: 'lots'"),
        ],
    )
    def test_a_usage_error_is_json_on_stderr_exit_2(self, capsys, argv, says):
        with pytest.raises(SystemExit) as exited:
            main(argv)
        assert exited.value.code == 2
        out, err = capsys.readouterr()
        assert out == ''
        error = json.loads(err)
        assert error['error'] == 'usage'
        assert says in error['message']


def test_check_runs_as_a_module():
    found = _run('check', '_support_rio')
    assert found.returncode == 0, found.stderr
    assert json.loads(found.stdout)['ok'] is True


def test_its_exit_code_says_whether_there_are_problems():
    found = _run('check', '_support_check.examples')
    assert found.returncode == 1
    assert len(json.loads(found.stdout)['problems']) == 4
