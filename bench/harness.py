"""Shared bench harness: a case's timing loop, and the results schema.

``Report`` and ``Measurement`` are seared classes, as seared's own bench has them: the artifact is written by the
library parsed is built on.

A case times one operation over its own number of iterations, since declaring a whole tree and reading one line
differ by orders of magnitude. Before each iteration, untimed, its ``setup`` builds what the operation needs, and the
garbage collector runs; during the operation it's off, as ``timeit`` keeps it, so a collection set off by earlier
iterations' garbage doesn't land in one timing.
"""

from __future__ import annotations

import gc
import platform
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import seared as s

if TYPE_CHECKING:
    from collections.abc import Callable

#: The fraction of a case's iterations run first, untimed, to warm it.
WARMUP_FRACTION = 0.05


def _nothing() -> object:
    return None


@dataclass(frozen=True, slots=True)
class Case:
    """One operation to time.

    Attributes:
        suite: The suite it belongs to: what part of parsed it measures.
        name: What it times, within the suite.
        iterations: How many times to time it.
        per: How many commands one operation covers, for a figure per command.
        run: The operation, given what ``setup`` built.
        setup: Builds what the operation needs, untimed, before each iteration.
    """

    suite: str
    name: str
    iterations: int
    per: int
    run: Callable[..., object]
    setup: Callable[[], object] = _nothing


@s.seared
class Measurement(s.Seared):
    """One case, timed in one run."""

    suite: str = s.Str(required=True)
    case: str = s.Str(required=True)
    version: str = s.Str(required=True, doc="parsed's version")
    iterations: int = s.Int(required=True)
    per: int = s.Int(default=1, doc='commands one operation covers')
    ops_per_s: float = s.Float(required=True)
    us_per_op: float = s.Float(required=True)
    run: int = s.Int(default=0, doc='0-based run index within the report')


@s.seared
class Report(s.Seared):
    """The committed ``bench/results.json`` artifact."""

    timestamp: str = s.Str(required=True, doc='UTC ISO 8601')
    python: str = s.Str(required=True)
    platform: str = s.Str(required=True)
    seared: str = s.Str(required=True, doc="seared's version")
    runs: int = s.Int(default=1, doc='times every case ran; the docs quote the median')
    measurements: list[Measurement] = s.T(Measurement, many=True, required=True)


def time_case(case: Case, version: str, run: int = 0) -> Measurement:
    """Time ``case`` over its iterations, as run ``run``, after a warmup."""
    for _ in range(max(1, int(case.iterations * WARMUP_FRACTION))):
        case.run(case.setup())
    total = 0.0
    for _ in range(case.iterations):
        state = case.setup()
        gc.collect()
        gc.disable()
        try:
            started = time.perf_counter()
            case.run(state)
            total += time.perf_counter() - started
        finally:
            gc.enable()
    return Measurement(
        suite=case.suite,
        case=case.name,
        version=version,
        iterations=case.iterations,
        per=case.per,
        ops_per_s=case.iterations / total,
        us_per_op=total * 1e6 / case.iterations,
        run=run,
    )


def environment() -> tuple[str, str]:
    """(Python's version, the platform) for the report."""
    return platform.python_version(), platform.platform()


__all__ = ['WARMUP_FRACTION', 'Case', 'Measurement', 'Report', 'environment', 'time_case']
