"""Performance bench for parsed: ships with the repo, not the package.

Times what a command line built on parsed costs, on a generated tree the size of a real one, and records the results
as a committed JSON artifact (``bench/results.json``). From the repo root:

    uv run python -m bench

Methodology and recorded results: ``docs/overview/benchmarks.md``.
"""
