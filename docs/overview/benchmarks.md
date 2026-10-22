# Benchmarks

What a command line built on parsed costs, measured on a generated tree the size of a real one. The bench lives in
[`bench/`](../../bench/): it ships with the repo, not the installable package. Every recorded run writes a
machine-readable snapshot to [`bench/results.json`](../../bench/results.json), and history lives in git.

## The tree

[`bench/tree.py`](../../bench/tree.py) declares <!-- bench:commands -->263<!-- /bench:commands --> commands, as many
as a real terminal game's command line has, in twelve sections. Each section has a base, decorated, carrying a
positional field, an effect and the kinds its commands read by. Its commands take the shapes parsed's own tests
take:

- every fourth has a twin that renames its first slot;
- one in seven has an optional last slot, and an alias that leaves it out;
- one in six takes a second positional, and one in three or five a flag;
- one in nine reads, with a typed reply; one in eleven asks first; one in twenty-three is interactive, with the
  command before it as its agent form.

Each call declares new classes, so declaring can be timed from nothing.

## Method

- **A case times one operation** over its own number of iterations, after a warmup of a twentieth of them, with
  `time.perf_counter()`, single-threaded.
- **Before each iteration,** untimed, the case builds what the operation needs, and the garbage collector runs.
  During the operation it's off, as `timeit` keeps it, so a collection set off by earlier iterations doesn't land in
  one timing.
- **With `--runs N`,** every case is timed N times, the runs interleaved across the cases so machine drift doesn't
  land on one of them, and every number below is the median of the runs. The committed results use three.
- **seared runs as pure Python** unless its optional accelerator is installed; the recorded run had none.

## Results

Recorded <!-- bench:run -->2026-10-22, Python 3.14.3, median of 3 runs; parsed 0.1.2, seared 0.4.4<!-- /bench:run -->.

### Declaring

What a tree costs before any line is read:

<!-- bench:declaring -->
| Case       | What it times                                                   | Per tree | Per command |
|------------|-----------------------------------------------------------------|----------|-------------|
| `decorate` | creating and decorating every command, as importing them does   | 62.8 ms  | 238.76 µs   |
| `declare`  | each command's first `declaration`                              | 5.0 ms   | 19.20 µs    |
| `reread`   | `declaration` again, kept on the class                          | 119.8 µs | 0.46 µs     |
| `build`    | the `Tree` from them: their phrases compiled, the whole checked | 1.1 ms   | 4.13 µs     |
<!-- /bench:declaring -->

So a module of <!-- bench:commands -->263<!-- /bench:commands --> commands costs
<!-- bench:decorate-ms -->~63 ms<!-- /bench:decorate-ms --> to import, declaring them all
<!-- bench:declare-ms -->~5 ms<!-- /bench:declare-ms --> more, and building their tree
<!-- bench:build-ms -->~1.1 ms<!-- /bench:build-ms -->, once. A command line that starts a process for each line pays
all three each time.

### Reading

A line for each command, on a tree built once: its `PHRASE`, each slot a word, and each of its flags given
([`bench/tree.py`](../../bench/tree.py)'s `lines`):

<!-- bench:reading -->
| Case   | What it times                                                     | Every line | Per line |
|--------|-------------------------------------------------------------------|------------|----------|
| `walk` | a line's flags split off, its words walked, each read by its kind | 2.4 ms     | 9.12 µs  |
| `read` | a line on to its instance, which seared loads from the values     | 3.5 ms     | 13.47 µs |
<!-- /bench:reading -->

So a line costs <!-- bench:walk-us -->~9 µs<!-- /bench:walk-us --> to walk, and
<!-- bench:read-us -->~13 µs<!-- /bench:read-us --> to read on to its instance, the difference seared's `load`.

### Spread

Every number here is <!-- bench:runs -->the median of three runs<!-- /bench:runs -->. How far each case's rate moved between runs:

<!-- bench:spread -->
| Case       | Spread |
|------------|--------|
| `decorate` | 32.7%  |
| `declare`  | 32.9%  |
| `reread`   | 42.3%  |
| `build`    | 10.0%  |
| `walk`     | 13.6%  |
| `read`     | 21.0%  |
<!-- /bench:spread -->

The widest is <!-- bench:spread-max -->~42%<!-- /bench:spread-max -->.

## Reproducing

From the repo root:

```sh
uv run python -m bench --runs 3          # how the committed artifact is recorded
uv run python -m bench --no-write        # time without recording
uv run python -m bench.tables --check    # the docs match bench/results.json
```

Recording a run to the committed artifact re-renders every number in this page from it.
