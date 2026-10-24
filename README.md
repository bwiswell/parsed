# parsed

Typed command trees on [seared](https://github.com/bwiswell/seared), for people and agents.

> **0.2.0 is the first version to build on,** its public surface settled. `app.main(argv)` runs a program's
> arguments as its command line, and a refusal says the line's own words, each flag's value by its kind and each
> name by what a person calls it (`--into <fleet>`, `no ore 'lab'`); an app's resolvers may say why a word names
> nothing. Help says each command in its own words, and a package's commands get reference pages. A line says a
> chain of steps, joined by `then`, run as one order and called as one tool; an app mounts trees of commands under
> prefixes of words and runs each line by its handler, giving one envelope with an exit code; a read waits on its
> reply; lines are completed as they're typed, written back from an instance, and described as data for the tools
> that read commands.

## Why parsed

A command line is a tree of commands, and each command is a set of typed values: positionals, flags, their kinds
and their bounds. parsed declares each command once, as a seared class, in the way zeared declares a message: a
phrase in place of a topic, and class constants for the rest. From that one declaration come:

- **reading a line** into a validated instance, with refusals that say what was wrong and how to say it;
- **help, usage and completion;**
- **a JSON Schema** for each command, and the way back from its values to its line, so an agent can call a
  command as a tool, through [tooled](https://github.com/bwiswell/tooled), as a person types it.

## Setup

Each release is tagged `v<version>` on GitHub. Install one by its tag:

```sh
uv add git+https://github.com/bwiswell/parsed --tag v0.2.0
```

`uv add` records the tag as the dependency's source:

```toml
[tool.uv.sources]
parsed = { git = "https://github.com/bwiswell/parsed", tag = "v0.2.0" }
```

**The tag is the pin.** uv doesn't check a version range against a git source, so a release is chosen by moving
the tag, then `uv lock --upgrade-package parsed`. parsed pins seared the same way, and a project that uses both
must pin the same seared tag: uv refuses two sources for one package.

## Quick start

A command is a seared class: its `PHRASE` says how a line says it, and its fields are the values the line gives. An
app mounts the commands, binds each one's handler, and runs a program's arguments as its command line:

```python
import sys
from datetime import timedelta

import parsed


@parsed.parsed
class FleetMine(parsed.Command):
    """Mine until the hold is full, or for as long as it's told."""

    PHRASE = 'fleet {fleet} mine'
    EFFECT = parsed.Effect.ACTION
    EXAMPLES = ('fleet prospector mine --for 1h30m',)

    fleet: str = parsed.Str(required=True, doc='the fleet that mines')
    for_: timedelta | None = parsed.TimeDelta(data_key='for', default=None, doc='stop after this long')


def mine(command: FleetMine, ctx: parsed.Context) -> str:
    return f'{command.fleet} mines' + (f' for {command.for_}' if command.for_ else '')


app = parsed.App('fleets')
app.mount(parsed.Tree([FleetMine]))
app.on(FleetMine, mine)

if __name__ == '__main__':
    sys.exit(app.main())
```

```
$ fleets fleet prospector mine --for 1h30m
prospector mines for 1:30:00
$ fleets fleet prospector mine --for soon
--for: 'soon' is not a span of time: say 90s, 10m, 2h or 1h30m
$ fleets fleet prospector mien
no command 'fleet prospector mien'; did you mean mine?
$ fleets fleet prospector mine --help
fleet <fleet> mine [--for <span>]

Mine until the hold is full, or for as long as it's told.

  <fleet>       the fleet that mines
  --for <span>  stop after this long

Examples:
  fleet prospector mine --for 1h30m
```

A refusal exits `2`. The same declaration reads a line to its instance, writes one back, and describes itself for a
tool:

```python
import parsed.doc

app.read('fleet prospector mine --for 1h30m')    # FleetMine(fleet='prospector', for_=timedelta(seconds=5400))
app.render(FleetMine(fleet='prospector', for_=timedelta(minutes=90)))    # 'fleet prospector mine --for 1h30m'
parsed.doc.json_schema(FleetMine)                # a closed JSON Schema, its x-phrase and x-effect beside
```

`import parsed` is enough to declare commands: every seared field type, the errors, `parsed.Parsed` and
`parsed.parsed` for a plain seared class, and parsed's own. Command modules keep to `import parsed`, unaliased, so a
field can be named anything without shadowing the module.

## Docs

- [`docs/parsed.md`](docs/parsed.md): the package root, and what it re-exports.
- [`docs/command.md`](docs/command.md): commands, and what they declare.
- [`docs/kinds.md`](docs/kinds.md): how a field's words are read.
- [`docs/names.md`](docs/names.md): an app's names, by the resolvers it gives.
- [`docs/tree.md`](docs/tree.md): every command's phrases, compiled and checked as a whole.
- [`docs/app.md`](docs/app.md): a program's trees mounted under prefixes, with their handlers and names.
- [`docs/argv.md`](docs/argv.md): a program's arguments as its command line, its root options first.
- [`docs/help.md`](docs/help.md): how a command is said and what it does, in its own words.
- [`docs/context.md`](docs/context.md): what a handler is given beside its command.
- [`docs/reply.md`](docs/reply.md): what running a line comes to, and its exit code.
- [`docs/wait.md`](docs/wait.md): a read that waits on its reply.
- [`docs/doc/index.md`](docs/doc/index.md): commands as data, for the tools that read them, and `parsed check`,
  for an app's CI.
- [`docs/effect.md`](docs/effect.md): what running a command does.
- [`docs/errors.md`](docs/errors.md): what can go wrong.
- [`docs/overview/benchmarks.md`](docs/overview/benchmarks.md): what a command line built on parsed costs.
- [`docs/overview/architecture.md`](docs/overview/architecture.md): how parsed sits in the family.
- [`CHANGELOG.md`](CHANGELOG.md): each version, newest first.

## Development

```sh
uv sync
uv run pytest tests/
```

Six checks gate every commit, wired as `prek` hooks — run `uv run prek install` once per clone:

```sh
uv run ruff check                        # lint
uv run ruff format                       # format
uv run deptry .                          # dependency hygiene
uv run ty check                          # type check
uv run python -m bench.tables --check    # benchmark numbers match bench/results.json
```

The sixth refuses any commit on `master`.

**Branches and releases.**
- **`master` holds released commits only,** and moves only by merge.
- **A release is a `version/x.y.z` branch** off `master`.
- **Work on it happens in `feat/…` and `fix/…` branches,** each a pull request squash-merged into the version
  branch. Each adds its own lines to the `unreleased` entry at the top of `CHANGELOG.md`.
- **Once those are all in, a `chore/version-bump-and-benches` branch** makes two commits:
  1. it bumps the version, in `pyproject.toml` and `parsed/__init__.py` together (a test checks that they agree),
     refreshes the lockfile, and dates the changelog entry;
  2. it re-records the benchmarks.
- **The version branch then merges into `master`.** There, the `Release Tag` workflow
  (`.github/workflows/release-tag.yml`) tags it `v<version>` and publishes a GitHub release.

The benchmarks are repo-only, in [`bench/`](bench/). Every benchmark number in
[`docs/overview/benchmarks.md`](docs/overview/benchmarks.md) is generated from the committed `bench/results.json`,
as the median of its runs; recording a run re-renders them:

```sh
uv run python -m bench --runs 3          # how the committed artifact is recorded
```
