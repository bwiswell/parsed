"""Tests for ``parsed/doc/generate.py``: a package's command reference, over seared's doc pipeline."""

from __future__ import annotations

import _support_farlandia as farlandia
from seared.doc import document as seared_document

from parsed.doc import build_docs, document
from parsed.doc.generate import main
from parsed.doc.render import GENERATED


class TestTheDocSet:
    def test_a_page_for_each_class_and_an_index(self):
        docs = build_docs('_support_farlandia')
        assert {'FleetMine.md', 'FleetView.md', 'FleetCommand.md', 'ShipFit.md', 'index.md'} <= set(docs)
        assert '[FleetMine](FleetMine.md)' in docs['index.md']

    def test_a_command_s_page_and_seared_s_for_any_other(self):
        docs = build_docs('_support_farlandia')
        assert docs['FleetMine.md'].endswith(f'{GENERATED}\n')
        assert docs['FleetView.md'] == seared_document(farlandia.FleetView)  # a reply
        assert docs['FleetCommand.md'] == seared_document(farlandia.FleetCommand)  # a base

    def test_one_class_s(self):
        assert document(farlandia.FleetMine).startswith('# FleetMine\n')
        assert document(farlandia.FleetView) == seared_document(farlandia.FleetView)


class TestTheCommandLine:
    def test_written_then_checked(self, tmp_path, capsys):
        out = tmp_path / 'commands'
        assert main(['_support_rio', '-o', str(out)]) == 0
        assert (out / 'HandheldConnect.md').read_text(encoding='utf-8').startswith('# HandheldConnect\n')
        assert main(['_support_rio', '-o', str(out), '--check']) == 0
        (out / 'HandheldConnect.md').write_text('stale', encoding='utf-8')
        assert main(['_support_rio', '-o', str(out), '--check']) == 1
        assert 'stale:   HandheldConnect.md' in capsys.readouterr().err

    def test_a_field_without_a_doc_refused_when_asked(self, tmp_path, monkeypatch, capsys):
        (tmp_path / 'undocumented_commands.py').write_text(
            'import parsed\n\n\n'
            '@parsed.parsed\n'
            'class Hail(parsed.Command):\n'
            '    """Hail a ship."""\n\n'
            "    PHRASE = 'hail {ship}'\n\n"
            '    ship: str = parsed.Str(required=True)\n',
            encoding='utf-8',
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        assert main(['undocumented_commands', '--require-docs', '-o', str(tmp_path / 'docs')]) == 1
        assert 'undocumented_commands.Hail.ship' in capsys.readouterr().err
