# Benchmarks

What a command line built on parsed costs, measured on a generated tree the size of a real one. The bench lives in
[`bench/`](../../bench/): it ships with the repo, not the installable package. Every recorded run writes a
machine-readable snapshot to [`bench/results.json`](../../bench/results.json), and history lives in git.

## The tree

[`bench/tree.py`](../../bench/tree.py) declares <!-- bench:commands -->263<!-- /bench:commands --> commands, as many
as a real terminal game's command line has, in twelve sections. Each section has a base, decorated, carrying a
positional field, an effect and the kinds its commands read by. Its commands take the shapes parsed's own tests
take:

- every fourth has a twin that says its first slot by an alias;
- one in seven has an optional last slot, and another wording that leaves it out;
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
- **The suites' own trees are frozen** (`gc.freeze()`) once every case is built, so the collection before each
  iteration sweeps only what the iterations left, not every tree. Before 0.1.6 it swept them all, which flushed
  the processor's caches before each operation: the smaller cases read slower in earlier records for it, and a run
  took minutes, where it now takes seconds.
- **With `--runs N`,** every case is timed N times, the runs interleaved across the cases so machine drift doesn't
  land on one of them, and every number below is the median of the runs. The committed results use three.
- **seared runs as pure Python** unless its optional accelerator is installed; the recorded run had none.

## Results

Recorded <!-- bench:run -->2026-10-23, Python 3.14.3, median of 3 runs; parsed 0.1.5, seared 0.4.4<!-- /bench:run -->.

### Declaring

What a tree costs before any line is read:

<!-- bench:declaring -->
| Case       | What it times                                                   | Per tree | Per command |
|------------|-----------------------------------------------------------------|----------|-------------|
| `decorate` | creating and decorating every command, as importing them does   | 65.0 ms  | 247.29 µs   |
| `declare`  | each command's first `declaration`                              | 7.0 ms   | 26.50 µs    |
| `reread`   | `declaration` again, kept on the class                          | 24.3 µs  | 0.09 µs     |
| `build`    | the `Tree` from them: their phrases compiled, the whole checked | 1.1 ms   | 4.01 µs     |
<!-- /bench:declaring -->

So a module of <!-- bench:commands -->263<!-- /bench:commands --> commands costs
<!-- bench:decorate-ms -->~65 ms<!-- /bench:decorate-ms --> to import, declaring them all
<!-- bench:declare-ms -->~7 ms<!-- /bench:declare-ms --> more, and building their tree
<!-- bench:build-ms -->~1.1 ms<!-- /bench:build-ms -->, once. A command line that starts a process for each line pays
all three each time.

### Reading

A line for each command, on a tree built once: its `PHRASE`, each slot a word, and each of its flags given
([`bench/tree.py`](../../bench/tree.py)'s `lines`):

<!-- bench:reading -->
| Case   | What it times                                                     | Every line | Per line |
|--------|-------------------------------------------------------------------|------------|----------|
| `walk` | a line's flags split off, its words walked, each read by its kind | 3.3 ms     | 12.45 µs |
| `read` | a line on to its instance, which seared loads from the values     | 5.2 ms     | 19.60 µs |
<!-- /bench:reading -->

So a line costs <!-- bench:walk-us -->~12 µs<!-- /bench:walk-us --> to walk, and
<!-- bench:read-us -->~20 µs<!-- /bench:read-us --> to read on to its instance, the difference seared's `load`.

### Completing

What Tab offers after each line's words but its last, on the same tree: the line walked loosely, then the slot's
values, the literal words and the flags offered there:

<!-- bench:completing -->
| Case       | What it times                                   | Every line | Per line |
|------------|-------------------------------------------------|------------|----------|
| `complete` | what may come after a line's words but its last | 2.6 ms     | 9.94 µs  |
<!-- /bench:completing -->

So a completion costs <!-- bench:complete-us -->~10 µs<!-- /bench:complete-us -->.

### Rendering

An instance of each command, read from its line, written back to a line on the same tree: its phrase picked, its
values spelled by their kinds and quoted where they must be, its flags given:

<!-- bench:rendering -->
| Case     | What it times                                                                        | Every command | Per command |
|----------|--------------------------------------------------------------------------------------|---------------|-------------|
| `render` | an instance back to its line: its phrase picked, its values spelled, its flags given | 2.2 ms        | 8.34 µs     |
<!-- /bench:rendering -->

So writing a command back costs <!-- bench:render-us -->~8 µs<!-- /bench:render-us -->.

### Running

A line of each command run in an open session: routed to its mount, read and loaded, its handler called with a fresh
context between a before and an after hook, and what came of it put in its envelope. The handler and the hooks do
nothing, so this is parsed's own part of running a line:

<!-- bench:running -->
| Case  | What it times                                                                              | Every line | Per line |
|-------|--------------------------------------------------------------------------------------------|------------|----------|
| `run` | a line run in a session: routed, read, its handler called between hooks, its envelope made | 10.8 ms    | 40.98 µs |
<!-- /bench:running -->

So running a line costs <!-- bench:run-us -->~41 µs<!-- /bench:run-us -->, of which reading it is the most.

### Waiting

A watch on one of the tree's reads, woken by a change: the app says its state moved, the read runs again, and its
next reply is given, its envelope made. The session polls not at all (`interval=None`), so this is the time from a
change to the wake, fifty times an operation:

<!-- bench:waiting -->
| Case   | What it times                                                                         | Every wake | Per wake |
|--------|---------------------------------------------------------------------------------------|------------|----------|
| `wake` | a change to its wake: a watch reads again and gives its next reply, its envelope made | 579.3 µs   | 11.59 µs |
<!-- /bench:waiting -->

So a wait wakes <!-- bench:wake-us -->~12 µs<!-- /bench:wake-us --> after a change.

### Spread

Every number here is <!-- bench:runs -->the median of three runs<!-- /bench:runs -->. How far each case's rate moved between runs:

<!-- bench:spread -->
| Case       | Spread |
|------------|--------|
| `decorate` | 0.8%   |
| `declare`  | 4.0%   |
| `reread`   | 2.4%   |
| `build`    | 14.1%  |
| `walk`     | 7.2%   |
| `read`     | 8.1%   |
| `complete` | 10.9%  |
| `render`   | 10.7%  |
| `run`      | 7.1%   |
| `wake`     | 2.0%   |
<!-- /bench:spread -->

The widest is <!-- bench:spread-max -->~14%<!-- /bench:spread-max -->.

## Reproducing

From the repo root:

```sh
uv run python -m bench --runs 3          # how the committed artifact is recorded
uv run python -m bench --no-write        # time without recording
uv run python -m bench.tables --check    # the docs match bench/results.json
```

Recording a run to the committed artifact re-renders every number in this page from it.
