"""The fixtures as whole apps, driven end to end through ``main(argv)``, as their own command lines would be run.

Cross-cutting, as an integration test is: each app (``_support_apps.py``) is built as a consumer's command line would
build it, and run with the shell's tokens, so reading, root options, running, help, exit codes and the reference
pages are checked together, beside each module's own tests.
"""

from __future__ import annotations

import json
import re

import _support_apps as apps
import pytest

from parsed.doc import build_docs, check
from parsed.doc.generate import main as doc_main


def _main(app, capsys, *argv: str) -> tuple[int, str, str]:
    code = app.main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def _column(text: str) -> list[str]:
    """A listing's said column: each line up to its summary."""
    return [re.split(r'\s{2,}', line)[0] for line in text.strip().splitlines()]


class TestAServicesCommandLine:
    # servicectl: root options before the verb, the skeleton at the root, and a command built from a protocol's request.
    @pytest.fixture
    def servicectl(self):
        return apps.servicectl()

    def test_its_version(self, servicectl, capsys):
        assert _main(servicectl, capsys, '--version') == (0, 'servicectl 1.2.3\n', '')

    @pytest.mark.parametrize(
        ('argv', 'said'),
        [
            (('run',), 'relay on port 5085, config None'),
            (('-c', 'relay.toml', 'run'), 'relay on port 5085, config relay.toml'),  # the program's
            (('-c', 'relay.toml', 'run', '-c', 'own.toml'), 'relay on port 5085, config own.toml'),  # the line's
            (('run --config own.toml',), 'relay on port 5085, config own.toml'),  # a single argument, the line
        ],
    )
    def test_root_options_then_the_line_s_own(self, servicectl, capsys, argv, said):
        assert _main(servicectl, capsys, *argv) == (0, f'{said}\n', '')

    def test_a_config_checked(self, servicectl, capsys, tmp_path):
        good, bad = tmp_path / 'good.toml', tmp_path / 'bad.toml'
        good.write_text('port = 5085\n', encoding='utf-8')
        bad.write_text('port = \n', encoding='utf-8')
        assert _main(servicectl, capsys, '-c', str(good), 'validate-config') == (0, f'{good} is valid\n', '')
        code, out, err = _main(servicectl, capsys, 'validate-config', '--config', str(bad))
        assert (code, out) == (1, '')
        assert err.startswith(f'ValueError: {bad}: ')

    def test_a_command_built_from_a_protocol_s_request(self, servicectl, capsys):
        code, out, _ = _main(
            servicectl, capsys, 'handheld', 'connect', 'dock', 'r7', '--host', 'h', '--label', 'north dock'
        )
        assert code == 0
        assert json.loads(out) == {
            'host': 'h',
            'label': 'north dock',
            'port': 5084,
            'reader_id': 'r7',
            'source': 'dock',
        }

    def test_the_protocol_s_bounds_hold(self, servicectl, capsys):
        code, _, err = _main(servicectl, capsys, 'handheld', 'connect', 'dock', 'r7', '--host', 'h', '--port', '70000')
        assert (code, err) == (4, '--port: must be <= 65535, got 70000\n')

    def test_its_help(self, servicectl, capsys):
        code, out, _ = _main(servicectl, capsys, '--help')
        program, options, listed = out.split('\n\n')
        assert (code, program) == (0, 'servicectl [--config <config>] [--version] <command> …')
        assert options.splitlines()[0] == '  -c, --config <config>  the config file; left out, the service default'
        assert _column(listed) == [
            'run [--config <config>]',
            'validate-config [--config <config>]',
            'status [--config <config>]',
            'handheld connect <source> <reader_id> --host <host> [--port <port>] [--label <label>]',
        ]

    def test_its_envelope(self, servicectl, capsys):
        code, out, _ = _main(servicectl, capsys, '--json', 'status')
        assert (code, json.loads(out)['text'], json.loads(out)['command']) == (0, 'relay is up', 'status')

    @pytest.mark.parametrize(
        ('argv', 'code', 'says'),
        [
            (('rn',), 2, "no command 'rn'; did you mean run?"),
            (('--config',), 2, '--config needs a value `--config <config>`'),
            (('handheld', 'connect', 'dock', 'r7'), 2, 'handheld connect dock r7 needs --host'),
        ],
    )
    def test_its_refusals(self, servicectl, capsys, argv, code, says):
        found, out, err = _main(servicectl, capsys, *argv)
        assert (found, out) == (code, '')
        assert err.startswith(says)


class TestAnAggregateCommandLine:
    # meshctl: one skeleton mounted twice, each mount with its own settings and its own namespace's line.
    @pytest.fixture
    def meshctl(self):
        return apps.meshctl()

    @pytest.mark.parametrize(
        ('argv', 'said'),
        [
            (('relay', 'run'), 'relay on port 5085, config None'),
            (('gateway', 'run'), 'gateway on port 8443, config None'),
            (('gateway', 'status'), 'gateway is up'),
        ],
    )
    def test_each_mount_with_its_own_settings(self, meshctl, capsys, argv, said):
        assert _main(meshctl, capsys, *argv) == (0, f'{said}\n', '')

    def test_its_namespaces_a_line_each(self, meshctl, capsys):
        code, out, _ = _main(meshctl, capsys, '--help')
        assert (code, out.split('\n\n')[-1].splitlines()) == (
            0,
            ["relay …    The relay: a site's messages, onto the mesh.", "gateway …  The gateway: the mesh's boundary."],
        )
        assert _column(_main(meshctl, capsys, 'gateway', '--help')[1]) == [
            'gateway run [--config <config>]',
            'gateway validate-config [--config <config>]',
            'gateway status [--config <config>]',
        ]

    def test_a_mount_s_command_with_no_handler(self, meshctl, capsys):
        code, _, err = _main(meshctl, capsys, 'relay', 'validate-config')
        assert (code, err) == (
            1,
            "LookupError: ValidateConfig has no handler in _support_service under 'relay': bind one with app.on\n",
        )


class TestAnAgentsTooling:
    # tooled: its verbs read by parsed, durations, counts and slot=value words among them.
    @pytest.fixture
    def tooled(self):
        return apps.tooled()

    def _read(self, tooled, capsys, *argv: str) -> tuple[str, dict]:
        code, out, err = _main(tooled, capsys, *argv)
        assert (code, err) == (0, '')
        verb, _, said = out.strip().partition(' ')
        return verb, json.loads(said.removesuffix(' (a dry run)'))

    def test_a_wait_s_conditions_and_its_bound(self, tooled, capsys):
        verb, said = self._read(
            tooled,
            capsys,
            'wait',
            'FleetState',
            'fleet=f1',
            '--until',
            'docked=true',
            '--until',
            'ships[].hull=frigate',
            '--timeout',
            '2m',
        )
        assert verb == 'wait'
        assert (said['slots'], said['until'], said['timeout']) == (
            ['fleet=f1'],
            ['docked=true', 'ships[].hull=frigate'],
            120.0,
        )

    def test_a_listen_s_count_span_and_switch(self, tooled, capsys):
        _, said = self._read(tooled, capsys, 'listen', 'FleetState', '--count', '3', '--for', '30s', '--meta')
        assert (said['count'], said['for'], said['meta'], said['slots']) == (3, 30.0, True, [])

    def test_an_invoke_s_dry_run_and_its_negated_switch(self, tooled, capsys):
        code, out, _ = _main(tooled, capsys, 'invoke', 'FleetOrder', 'fleet=f1', '--dry-run', '--no-retry')
        assert (code, out.strip().endswith('(a dry run)')) == (0, True)
        assert json.loads(out.split(' ', 1)[1].removesuffix(' (a dry run)\n'))['retry'] is False

    def test_a_choice_and_its_shared_flags(self, tooled, capsys):
        _, said = self._read(tooled, capsys, 'tools', '--format', 'anthropic', '--policy', 'p.toml', '--select', 'a.b')
        assert (said['format'], said['policy'], said['select']) == ('anthropic', 'p.toml', 'a.b')

    def test_a_reply_in_its_envelope(self, tooled, capsys):
        code, out, _ = _main(tooled, capsys, '--json', 'describe', 'FleetState', '--reply')
        assert (code, json.loads(out)['reply']) == (0, {'operation': 'FleetState', 'reply': True})

    @pytest.mark.parametrize(
        ('argv', 'code', 'says'),
        [
            (
                ('fetch', 'FleetState', 'fleet'),
                2,
                "fetch {operation} {slots}: 'fleet' is not slot=value, such as fleet=f1",
            ),
            (('wait', 'FleetState'), 2, 'wait FleetState needs --until'),
            (('wait', 'X', '--until', 'docked'), 2, "--until: 'docked' is not path=value, such as docked=true"),
            (('listen', 'X', '--count', '0'), 4, '--count: must be >= 1, got 0'),
            (('tools', '--format', 'html'), 2, "--format: 'html' is not one of openai, anthropic or mcp"),
        ],
    )
    def test_its_refusals(self, tooled, capsys, argv, code, says):
        found, out, err = _main(tooled, capsys, *argv)
        assert (found, out) == (code, '')
        assert err.startswith(says)

    def test_its_help_in_its_own_words(self, tooled, capsys):
        listed = _main(tooled, capsys, '--help')[1].split('\n\n')[-1]
        assert _column(listed)[:3] == [
            'check [--policy <policy>] [--pretty] [--select <select>] [--connect] [--no-resolve]',
            'operations [--policy <policy>] [--pretty] [--select <select>]',
            'describe <operation> [--policy <policy>] [--pretty] [--select <select>] [--variant <variant>] [--reply]',
        ]
        said = _main(tooled, capsys, 'wait', '--help')[1]  # short of its operation, the one command beneath: its help
        assert said.startswith(
            'wait <operation> [<slots> …] [--policy <policy>] [--pretty] [--select <select>] '
            '--until <until> … [--timeout <timeout>] [--meta]\n\nWait for a retained contract'
        )
        assert re.search(
            r'^  --until <until> …\s+a path and the value it must equal; all must hold$', said, re.MULTILINE
        )
        assert 'Examples:\n  wait FleetState fleet=f1 --until docked=true --timeout 2m' in said


class TestTheirReferencePages:
    @pytest.mark.parametrize('target', ['_support_tooled', '_support_protocol', '_support_service'])
    def test_each_package_checks_clean(self, target):
        report = check([target])
        assert (report.ok, report.problems) == (True, ())

    def test_a_page_for_each_verb(self):
        docs = build_docs('_support_tooled')
        assert {'Wait.md', 'Listen.md', 'Described.md', 'Verb.md', 'index.md'} <= set(docs)
        arguments = docs['Wait.md'].split('## Arguments')[1].split('##')[0]
        assert '| `--until <until>` | `until` | path=value, such as docked=true |' in arguments

    def test_written_and_checked_for_ci(self, tmp_path, capsys):
        out = str(tmp_path / 'commands')
        assert doc_main(['_support_tooled', '-o', out]) == 0
        assert doc_main(['_support_tooled', '-o', out, '--check']) == 0
        assert 'up to date' in capsys.readouterr().out
