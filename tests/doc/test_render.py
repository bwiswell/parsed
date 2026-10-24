"""Tests for ``parsed/doc/render.py``: a command's reference page, in Markdown."""

from __future__ import annotations

import _support_farlandia as farlandia
import _support_protocol as protocol
import _support_service as service

from parsed.doc import render_command
from parsed.doc.render import GENERATED


def _sections(page: str) -> dict[str, str]:
    """A page's sections, by heading; the header's under ``''``."""
    found: dict[str, str] = {}
    heading = ''
    for part in page.split('\n## '):
        title, _, body = part.partition('\n')
        if heading == '' and not found:
            found[''] = part
            heading = '?'
            continue
        found[title] = body.strip()
    return found


class TestAPage:
    def test_its_header_what_it_declares_and_its_doc(self):
        page = render_command(farlandia.FleetMine)
        assert page.startswith(
            '# FleetMine\n\n`write` · a step of [`FleetCommand`](FleetCommand.md)\n\nMine until the hold is full.\n'
        )
        assert page.endswith(f'{GENERATED}\n')

    def test_its_phrases_with_their_keys(self):
        assert _sections(render_command(farlandia.FleetMine))['Phrases'] == '\n'.join(
            [
                '| phrase | key |',
                '|--------|-----|',
                '| `fleet {fleet} mine` | `fleet/{fleet}/mine` |',
                '| `detachment {detachment} mine` (extra) | `detachment/{detachment}/mine` |',
            ]
        )

    def test_its_usage_by_each_phrase(self):
        usage = _sections(render_command(farlandia.FleetMine))['Usage']
        assert usage == '```\nfleet <fleet> mine [--for <span>]\ndetachment <detachment> mine [--for <span>]\n```'

    def test_its_usage_ends_with_yes_when_it_asks(self):
        usage = _sections(render_command(farlandia.FleetsMerge))['Usage']
        assert usage == '```\nfleets merge <fleet> --into <fleet> [--quiet] [--yes]\n```'

    def test_its_arguments_and_what_their_words_are(self):
        arguments = _sections(render_command(service.Run))['Arguments']
        assert arguments.splitlines()[-1] == '| `-c`, `--config <path>` | `config` | a path |'
        merge = _sections(render_command(farlandia.FleetsMerge))['Arguments'].splitlines()
        assert merge[-2:] == ['| `--into <fleet>` | `into` | a fleet |', '| `--quiet` | `quiet` | on when given |']

    def test_its_examples(self):
        assert _sections(render_command(farlandia.FleetMine))['Examples'].splitlines()[-2] == (
            'fleet prospector mine --for 1h30m'
        )

    def test_links_to_its_reply_its_instead_and_where_its_fields_come_from(self):
        assert 'Reply [`FleetView`](FleetView.md)' in render_command(farlandia.FleetsShow)
        fit = render_command(farlandia.ShipFit)
        assert '`for a person at a terminal`' not in fit
        assert 'for a person at a terminal' in _sections(fit)['']
        assert 'Instead [`ShipsMakeAdd`](ShipsMakeAdd.md)' in fit
        assert 'Fields from [`HandheldEndpoint`](HandheldEndpoint.md)' in render_command(protocol.HandheldConnect)

    def test_seared_s_fields_after(self):
        assert _sections(render_command(farlandia.FleetMine))['Fields'].startswith(
            '| field | wire key | type | required | default | notes |'
        )

    def test_its_links_as_the_doc_set_gives_them(self):
        page = render_command(farlandia.FleetsShow, lambda cls: f'../replies/{cls.__name__}.md')
        assert 'Reply [`FleetView`](../replies/FleetView.md)' in page
