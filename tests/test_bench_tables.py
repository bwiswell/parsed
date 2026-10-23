"""Tests for ``bench/tables.py``: the generated benchmark numbers.

``bench/`` is repo-only, not part of the package. ``python -m bench.tables --check`` proves the docs match the
artifact; it can't prove the medians and spreads behind them are right. These pin that on synthetic reports, and that
the committed artifact and the docs agree.
"""

from __future__ import annotations

import pytest

from bench.harness import Measurement, Report
from bench.tables import (
    Results,
    blocks,
    declaring_table,
    load,
    reading_table,
    render,
    run_line,
    spread_table,
    update,
)

DECORATE = ('declaring', 'decorate')
DECLARE = ('declaring', 'declare')
WALK = ('reading', 'walk')
READ = ('reading', 'read')
COMPLETE = ('completing', 'complete')
RENDER = ('rendering', 'render')
RUN = ('running', 'run')
WAKE = ('waiting', 'wake')


def _m(case: tuple[str, str], us: float, run: int = 0, per: int = 100) -> Measurement:
    suite, name = case
    return Measurement(
        suite=suite,
        case=name,
        version='0.1.1',
        iterations=10,
        per=per,
        ops_per_s=1e6 / us,
        us_per_op=us,
        run=run,
    )


def _report(*measurements: Measurement, runs: int = 1) -> Report:
    return Report(
        timestamp='2026-10-21T12:00:00+00:00',
        python='3.14.3',
        platform='Linux',
        seared='0.4.4',
        runs=runs,
        measurements=list(measurements),
    )


class TestResults:
    def test_the_median_over_runs(self):
        report = _report(_m(DECORATE, 10.0, 0), _m(DECORATE, 30.0, 1), _m(DECORATE, 20.0, 2), runs=3)
        assert Results(report).us(DECORATE) == 20.0

    def test_per_command(self):
        assert Results(_report(_m(DECORATE, 500.0, per=250))).us_per_command(DECORATE) == 2.0

    def test_the_spread_needs_two_runs(self):
        assert Results(_report(_m(DECORATE, 10.0))).spread(DECORATE) is None
        two = _report(_m(DECORATE, 10.0, 0), _m(DECORATE, 20.0, 1), runs=2)
        assert Results(two).spread(DECORATE) == pytest.approx(1.0)

    def test_an_unmeasured_case_is_none(self):
        found = Results(_report(_m(DECORATE, 10.0)))
        assert not found.has(DECLARE)
        assert found.us(DECLARE) is None
        assert found.us_per_command(DECLARE) is None


class TestTables:
    def test_milliseconds_from_a_thousand_microseconds(self):
        table = declaring_table(Results(_report(_m(DECORATE, 62_700.0, per=263), _m(DECLARE, 900.0, per=263))))
        assert '62.7 ms' in table
        assert '900.0 µs' in table
        assert '238.40 µs' in table

    def test_an_unmeasured_row_is_left_out(self):
        table = declaring_table(Results(_report(_m(DECORATE, 10.0))))
        assert '`decorate`' in table
        assert '`declare`' not in table

    def test_a_suite_s_table_holds_its_own_cases(self):
        results = Results(_report(_m(DECORATE, 10.0), _m(WALK, 2_400.0, per=263), _m(READ, 3_500.0, per=263)))
        table = reading_table(results)
        assert 'Every line' in table
        assert 'Per line' in table
        assert ('`walk`' in table, '`read`' in table, '`decorate`' in table) == (True, True, False)
        assert '9.13 µs' in table
        assert '`walk`' not in declaring_table(results)

    def test_spread_reads_n_a_for_one_run(self):
        assert '| n/a ' in spread_table(Results(_report(_m(DECORATE, 10.0))))


class TestBlocks:
    def test_the_provenance_line(self):
        assert run_line(_report(_m(DECORATE, 10.0))) == '2026-10-21, Python 3.14.3, one run; parsed 0.1.1, seared 0.4.4'

    def test_the_inline_numbers(self):
        found = blocks(_report(_m(DECORATE, 62_700.0, per=263), _m(DECLARE, 5_200.0, per=263)))
        assert (found['commands'], found['decorate-ms'], found['declare-ms']) == ('263', '~63 ms', '~5 ms')
        assert found['runs'] == 'from one run'
        assert found['spread-max'] == 'n/a'

    def test_the_completing_suite(self):
        found = blocks(_report(_m(COMPLETE, 2_630.0, per=263)))
        assert '`complete`' in found['completing']
        assert found['complete-us'] == '~10 µs'

    def test_the_rendering_suite(self):
        found = blocks(_report(_m(RENDER, 1_315.0, per=263)))
        assert 'Every command' in found['rendering']
        assert found['render-us'] == '~5 µs'

    def test_the_running_suite(self):
        found = blocks(_report(_m(RUN, 7_890.0, per=263)))
        assert '`run`' in found['running']
        assert 'Every line' in found['running']
        assert found['run-us'] == '~30 µs'

    def test_the_waiting_suite(self):
        found = blocks(_report(_m(WAKE, 1_500.0, per=50)))
        assert 'Per wake' in found['waiting']
        assert found['wake-us'] == '~30 µs'

    def test_the_inline_numbers_per_line(self):
        found = blocks(_report(_m(WALK, 2_400.0, per=263), _m(READ, 3_500.0, per=263)))
        assert (found['walk-us'], found['read-us']) == ('~9 µs', '~13 µs')
        assert blocks(_report(_m(DECORATE, 10.0)))['walk-us'] == 'n/a'

    def test_render_replaces_each_body_and_keeps_the_prose(self):
        text = 'A <!-- bench:commands -->old<!-- /bench:commands --> tree.'
        assert render(text, {'commands': '263'}) == 'A <!-- bench:commands -->263<!-- /bench:commands --> tree.'

    def test_an_unknown_marker_is_an_error(self):
        with pytest.raises(KeyError):
            render('<!-- bench:nope -->x<!-- /bench:nope -->', {})


class TestUpdate:
    def test_check_reports_drift_without_writing(self, tmp_path):
        doc = tmp_path / 'doc.md'
        doc.write_text('<!-- bench:commands -->old<!-- /bench:commands -->', encoding='utf-8')
        report = _report(_m(DECORATE, 10.0, per=263))
        assert update(report, check=True, docs=[doc]) == [doc]
        assert 'old' in doc.read_text(encoding='utf-8')
        assert update(report, docs=[doc]) == [doc]
        assert update(report, check=True, docs=[doc]) == []

    def test_the_committed_artifact_matches_the_docs(self):
        assert update(load(), check=True) == []
