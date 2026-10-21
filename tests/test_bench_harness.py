"""Tests for ``bench/harness.py``: a case's timing loop."""

from __future__ import annotations

from bench.harness import Case, Report, time_case


def test_a_case_is_timed_after_its_setup_and_warmup():
    calls: list[str] = []

    def setup() -> object:
        calls.append('setup')
        return 'state'

    def run(state: object) -> None:
        assert state == 'state'
        calls.append('run')

    found = time_case(Case(suite='s', name='c', iterations=20, per=5, run=run, setup=setup), '0.1.1', run=2)
    # One warmup iteration (a twentieth of twenty), then twenty timed: each after its own setup.
    assert calls == ['setup', 'run'] * 21
    assert (found.suite, found.case, found.version, found.iterations, found.per, found.run) == (
        's',
        'c',
        '0.1.1',
        20,
        5,
        2,
    )
    assert found.ops_per_s > 0
    assert found.us_per_op > 0


def test_a_report_round_trips_through_json():
    found = time_case(Case(suite='s', name='c', iterations=1, per=1, run=lambda _: None), '0.1.1')
    report = Report(timestamp='t', python='3.14', platform='p', seared='0.4.4', measurements=[found])
    assert Report.from_json(Report.to_json(report)) == report
