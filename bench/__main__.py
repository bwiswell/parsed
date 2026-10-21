"""Bench runner. From the repo root: ``uv run python -m bench``.

Prints each case's timing and (unless ``--no-write``) records the run to ``bench/results.json``, the committed
artifact behind ``docs/overview/benchmarks.md``, then re-renders the docs' numbers from it (see ``bench.tables``).
``--runs N`` times every case N times, the runs interleaved across the cases so machine drift spreads across them
rather than landing on one; the docs quote the median.
"""

from __future__ import annotations

import argparse
import importlib
from datetime import UTC, datetime
from pathlib import Path

import seared

import parsed

from . import tables
from .harness import Report, environment, time_case

_SUITES = ['suite_declaring']
_DEFAULT_OUT = tables.RESULTS


def _collect_cases() -> list:
    cases = []
    for name in _SUITES:
        module = importlib.import_module(f'.{name}', package=__package__)
        cases.extend(module.cases())
    return cases


def main() -> None:
    """Parse args, run every suite, print and write the results."""
    parser = argparse.ArgumentParser(prog='python -m bench', description=__doc__.splitlines()[0])
    parser.add_argument(
        '--runs',
        type=int,
        default=1,
        help='time every case this many times; the docs quote the median (the committed artifact uses 3)',
    )
    parser.add_argument('--out', type=Path, default=_DEFAULT_OUT, help=f'results JSON path (default: {_DEFAULT_OUT})')
    parser.add_argument('--no-write', action='store_true', help='print the timings only; do not write the artifact')
    args = parser.parse_args()
    if args.runs < 1:
        parser.error('--runs must be at least 1')

    cases = _collect_cases()
    measurements = []
    for run in range(args.runs):
        if args.runs > 1:
            print(f'\n=== run {run + 1} of {args.runs} ===')
        for case in cases:
            m = time_case(case, parsed.__version__, run)
            measurements.append(m)
            print(f'{m.suite:<10} {m.case:<9} {m.us_per_op:>12,.1f} us/op  ({m.us_per_op / m.per:8.2f} us/command)')

    python, plat = environment()
    report = Report(
        timestamp=datetime.now(UTC).isoformat(timespec='seconds'),
        python=python,
        platform=plat,
        seared=seared.__version__,
        runs=args.runs,
        measurements=measurements,
    )
    if args.no_write:
        return
    args.out.write_text(Report.to_json(report, indent=2) + '\n')
    print(f'\nwrote {args.out}')
    # The docs quote the committed artifact, so only a run recorded *there*
    # rewrites them; a scratch ``--out`` leaves them alone.
    if args.out.resolve() == tables.RESULTS.resolve():
        for path in tables.update(report):
            print(f'updated {path}')


if __name__ == '__main__':
    main()
