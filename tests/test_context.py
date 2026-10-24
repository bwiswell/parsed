"""Tests for ``parsed/context.py``: what a handler is given beside its command."""

from __future__ import annotations

import typing

import _support_farlandia as farlandia
import _support_service as service
import pytest

import parsed
from parsed.app import App, Session
from parsed.context import Context


@pytest.fixture
def app() -> App:
    found = App('farlandia')
    found.names('detachment', farlandia.NAMES['detachment'])
    found.mount('_support_farlandia')
    found.mount('_support_service', under='relay', params=service.RelaySettings())
    return found


@pytest.fixture
async def session(app):
    async with app.open({'link': 'up'}, verbosity=1) as opened:
        yield opened


def _context(session: Session, line: str) -> Context:
    return session.context(session.app.walk(line))


class TestTheContext:
    def test_the_app_s_state_and_its_session(self, session):
        ctx = _context(session, 'fleet f1 mine')
        assert (ctx.session, ctx.app, ctx.state) == (session, session.app, {'link': 'up'})

    def test_the_mount_s_params_and_names(self, session):
        ctx = _context(session, 'relay run')
        assert ctx.mount.under == 'relay'
        assert ctx.params == service.RelaySettings()
        assert dict(ctx.names) == {'detachment': farlandia.NAMES['detachment']}

    def test_the_line_and_its_reading(self, session):
        ctx = _context(session, 'fleet f1 mine --for 90s')
        assert ctx.line == 'fleet f1 mine --for 90s'
        assert ctx.reading.command is farlandia.FleetMine
        assert ctx.reading.data() == {'fleet': 'f1', 'for': 90.0}

    @pytest.mark.parametrize(
        ('line', 'phrase'),
        [
            ('fleet f1 mine', 'fleet {fleet} mine'),
            ('detachment Scouts mine', 'detachment {detachment} mine'),  # a twin's wording, told from its command's
            ('fleet f1 dock nearest', 'fleet {fleet} dock nearest'),
            ('relay run', 'run'),  # as the command declares it, without its mount's prefix
        ],
    )
    def test_the_phrase_that_said_it(self, session, line, phrase):
        assert _context(session, line).phrase == phrase

    def test_a_dry_run_when_the_line_asks(self, session):
        assert _context(session, 'fleet f1 mine --dry-run').dry_run
        assert not _context(session, 'fleet f1 mine').dry_run

    def test_the_session_s_verbosity(self, session):
        assert _context(session, 'log').verbosity == 1

    async def test_whether_a_person_is_at_a_terminal(self, app, session):
        assert _context(session, 'log').terminal is False  # by default
        async with app.open(terminal=True) as opened:
            assert _context(opened, 'log').terminal is True

    def test_one_for_each_line(self, session):
        first, second = _context(session, 'log'), _context(session, 'log')
        assert first == second
        assert first is not second

    def test_its_annotations_resolve(self):
        # As the root's test pins for every class it exports: tooling evaluates them.
        assert set(typing.get_type_hints(Context)) == {'session', 'mount', 'reading'}

    def test_exported(self):
        assert parsed.Context is Context
