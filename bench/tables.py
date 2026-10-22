"""Render the benchmark numbers in the docs from ``bench/results.json``.

The README and ``docs/overview/benchmarks.md`` carry them between ``<!-- bench:NAME -->`` / ``<!-- /bench:NAME -->``
markers: everything inside a pair is generated, everything outside it is prose. A *table block* sits on lines of its
own; an *inline block* wraps just a number in a sentence (HTML comments don't render), so the prose stays
hand-written and only the number is generated. ``python -m bench`` re-renders them after recording a run;
``python -m bench.tables`` does it from the committed artifact alone, and ``--check`` exits non-zero when a doc has
drifted from it. This is seared's scheme, lifted: hand-copied numbers were the likeliest way for a doc to disagree
with its own artifact.

Every number is a median over the report's runs (``python -m bench --runs N``).
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from .harness import Report

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from .harness import Measurement

_ROOT = Path(__file__).parent.parent
RESULTS = Path(__file__).parent / 'results.json'
DOCS = (_ROOT / 'README.md', _ROOT / 'docs' / 'overview' / 'benchmarks.md')

#: ``(suite, case, what it times)`` in display order. A case the run has no measurement for is left out.
_ROWS = (
    ('declaring', 'decorate', 'creating and decorating every command, as importing them does'),
    ('declaring', 'declare', "each command's first `declaration`"),
    ('declaring', 'reread', '`declaration` again, kept on the class'),
    ('declaring', 'build', 'the `Tree` from them: their phrases compiled, the whole checked'),
    ('reading', 'walk', "a line's flags split off, its words walked, each read by its kind"),
    ('reading', 'read', 'a line on to its instance, which seared loads from the values'),
    ('completing', 'complete', "what may come after a line's words but its last"),
    ('rendering', 'render', 'an instance back to its line: its phrase picked, its values spelled, its flags given'),
)

#: Run counts the prose spells out; anything else stays a numeral.
_WORDS = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five'}

#: What a number the report can't supply renders as.
_NA = 'n/a'

#: Runs a spread needs: one run has nothing to move against.
_SPREAD_MIN_RUNS = 2

#: A time at or above this many microseconds reads in milliseconds.
_MS_FROM = 1_000.0

_BLOCK = re.compile(r'(<!-- bench:(?P<name>[\w-]+) -->)(?P<body>.*?)(<!-- /bench:(?P=name) -->)', re.DOTALL)

#: One case: ``(suite, case)``.
type Case = tuple[str, str]


class Results:
    """A report's measurements as medians and spread over its runs."""

    def __init__(self, report: Report) -> None:
        """Group ``report``'s measurements by ``(suite, case)``, one per run."""
        grouped: dict[Case, list[Measurement]] = defaultdict(list)
        for m in report.measurements:
            grouped[m.suite, m.case].append(m)
        self.report = report
        self._grouped = dict(grouped)

    def has(self, case: Case) -> bool:
        """Whether ``case`` was measured at all."""
        return case in self._grouped

    def us(self, case: Case) -> float | None:
        """The median microseconds one operation of ``case`` took, or ``None`` if unmeasured."""
        runs = self._grouped.get(case)
        return statistics.median(m.us_per_op for m in runs) if runs else None

    def per(self, case: Case) -> int | None:
        """How many commands one operation of ``case`` covers, or ``None`` if unmeasured."""
        runs = self._grouped.get(case)
        return runs[0].per if runs else None

    def us_per_command(self, case: Case) -> float | None:
        """The median microseconds per command, or ``None`` if unmeasured."""
        us, per = self.us(case), self.per(case)
        return None if us is None or not per else us / per

    def spread(self, case: Case) -> float | None:
        """How far ``case``'s rate moved across the runs: ``max / min - 1``; ``None`` for fewer than two runs."""
        rates = [m.ops_per_s for m in self._grouped.get(case, [])]
        if len(rates) < _SPREAD_MIN_RUNS or min(rates) <= 0:
            return None
        return max(rates) / min(rates) - 1


def _fmt[V](value: V | None, render: Callable[[V], str]) -> str:
    """``render(value)``, or ``n/a`` for a value the report couldn't supply."""
    return _NA if value is None else render(value)


def _time(us: float) -> str:
    """A time for a table: milliseconds from a thousand microseconds up, else microseconds."""
    return f'{us / 1_000:.1f} ms' if us >= _MS_FROM else f'{us:.1f} µs'


def _table(rows: list[list[str]]) -> str:
    """A padded Markdown table; the first row is the header."""
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]

    def line(cells: list[str]) -> str:
        return '| ' + ' | '.join(c.ljust(w) for c, w in zip(cells, widths, strict=True)) + ' |'

    rule = '|' + '|'.join('-' * (w + 2) for w in widths) + '|'
    return '\n'.join([line(rows[0]), rule, *(line(r) for r in rows[1:])])


def _suite_table(results: Results, suite: str, whole: str, each: str) -> str:
    """One suite: each case's median time for the whole, and for each command or line in it."""
    rows = [['Case', 'What it times', whole, each]]
    rows.extend(
        [
            f'`{case}`',
            what,
            _fmt(results.us((found, case)), _time),
            _fmt(results.us_per_command((found, case)), lambda v: f'{v:.2f} µs'),
        ]
        for found, case, what in _ROWS
        if found == suite and results.has((found, case))
    )
    return _table(rows)


def declaring_table(results: Results) -> str:
    """The declaring suite: each case's median time per tree and per command."""
    return _suite_table(results, 'declaring', 'Per tree', 'Per command')


def reading_table(results: Results) -> str:
    """The reading suite: each case's median time for a line of each command, and per line."""
    return _suite_table(results, 'reading', 'Every line', 'Per line')


def completing_table(results: Results) -> str:
    """The completing suite: its case's median time for a line of each command, and per line."""
    return _suite_table(results, 'completing', 'Every line', 'Per line')


def rendering_table(results: Results) -> str:
    """The rendering suite: its case's median time for an instance of each command, and per command."""
    return _suite_table(results, 'rendering', 'Every command', 'Per command')


def spread_table(results: Results) -> str:
    """How far each case's rate moved between runs; ``n/a`` for one run."""
    rows = [['Case', 'Spread']]
    rows.extend(
        [f'`{case}`', _fmt(results.spread((suite, case)), lambda v: f'{v * 100:.1f}%')]
        for suite, case, _ in _ROWS
        if results.has((suite, case))
    )
    return _table(rows)


def _largest_spread(results: Results) -> float | None:
    """The widest run-to-run spread of any case, or ``None`` for one run."""
    spreads = [s for suite, case, _ in _ROWS if (s := results.spread((suite, case))) is not None]
    return max(spreads, default=None)


def _runs_phrase(report: Report) -> str:
    """What every number is, for a sentence: ``from one run`` / ``the median of three runs``."""
    if report.runs == 1:
        return 'from one run'
    return f'the median of {_WORDS.get(report.runs, str(report.runs))} runs'


def run_line(report: Report) -> str:
    """When, on what, against which versions and over how many runs: the provenance of every number."""
    version = report.measurements[0].version if report.measurements else _NA
    runs = 'one run' if report.runs == 1 else f'median of {report.runs} runs'
    return f'{report.timestamp[:10]}, Python {report.python}, {runs}; parsed {version}, seared {report.seared}'


def blocks(report: Report) -> dict[str, str]:
    """Every generated block by marker name. Table blocks sit on lines of their own."""
    r = Results(report)
    decorate, declare, build = ('declaring', 'decorate'), ('declaring', 'declare'), ('declaring', 'build')
    walk, read = ('reading', 'walk'), ('reading', 'read')
    return {
        # Table blocks.
        'declaring': f'\n{declaring_table(r)}\n',
        'reading': f'\n{reading_table(r)}\n',
        'completing': f'\n{completing_table(r)}\n',
        'rendering': f'\n{rendering_table(r)}\n',
        'spread': f'\n{spread_table(r)}\n',
        # Inline blocks: the provenance, then the numbers the prose quotes.
        'run': run_line(report),
        'runs': _runs_phrase(report),
        'spread-max': _fmt(_largest_spread(r), lambda v: f'~{v * 100:.0f}%'),
        'commands': _fmt(r.per(decorate), str),
        'decorate-ms': _fmt(r.us(decorate), lambda v: f'~{v / 1_000:.0f} ms'),
        'declare-ms': _fmt(r.us(declare), lambda v: f'~{v / 1_000:.0f} ms'),
        'build-ms': _fmt(r.us(build), lambda v: f'~{v / 1_000:.1f} ms'),
        'walk-us': _fmt(r.us_per_command(walk), lambda v: f'~{v:.0f} µs'),
        'read-us': _fmt(r.us_per_command(read), lambda v: f'~{v:.0f} µs'),
        'complete-us': _fmt(r.us_per_command(('completing', 'complete')), lambda v: f'~{v:.0f} µs'),
        'render-us': _fmt(r.us_per_command(('rendering', 'render')), lambda v: f'~{v:.0f} µs'),
    }


def render(text: str, generated: dict[str, str]) -> str:
    """``text`` with every marker pair's body replaced by its generated block.

    Raises:
        KeyError: a marker names a block this module doesn't generate.
    """

    def replace(match: re.Match[str]) -> str:
        return f'{match[1]}{generated[match["name"]]}{match[4]}'

    return _BLOCK.sub(replace, text)


def update(report: Report, *, check: bool = False, docs: Sequence[Path] = DOCS) -> list[Path]:
    """Re-render ``docs`` from ``report``; return the files that differed.

    With ``check=True`` nothing is written: the return value is the drift.
    """
    generated = blocks(report)
    drifted = []
    for path in docs:
        text = path.read_text(encoding='utf-8')
        new = render(text, generated)
        if new != text:
            drifted.append(path)
            if not check:
                path.write_text(new, encoding='utf-8')
    return drifted


def load(path: Path = RESULTS) -> Report:
    """The report at ``path``, the committed artifact by default."""
    return Report.from_json(path)


def main() -> None:
    """Re-render the docs' numbers from the committed results, or check them."""
    parser = argparse.ArgumentParser(prog='python -m bench.tables', description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true', help='exit 1 if a doc has drifted from results.json')
    args = parser.parse_args()

    drifted = update(load(), check=args.check)
    for path in drifted:
        print(f'{"drifted" if args.check else "updated"}: {path.relative_to(_ROOT)}')
    if args.check and drifted:
        sys.exit(1)


if __name__ == '__main__':
    main()
