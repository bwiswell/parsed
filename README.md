# parsed

Typed command trees on [seared](https://github.com/bwiswell/seared), for people and agents.

> **0.1.3 reads names and completes lines:** a tree of commands reads a line to its command's instance, its names
> read by the resolvers an app gives for each category, and offers what may come next on a line being typed. A
> line that doesn't read is one error, with a hint and what may have been meant. Writing a line back, running
> commands and help arrive in the 0.1.x releases that follow, and 0.2.0 is the first version to build a command
> line on.

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
uv add git+https://github.com/bwiswell/parsed --tag v0.1.3
```

`uv add` records the tag as the dependency's source:

```toml
[tool.uv.sources]
parsed = { git = "https://github.com/bwiswell/parsed", tag = "v0.1.3" }
```

**The tag is the pin.** uv doesn't check a version range against a git source, so a release is chosen by moving
the tag, then `uv lock --upgrade-package parsed`. parsed pins seared the same way, and a project that uses both
must pin the same seared tag: uv refuses two sources for one package.

## Quick start

`import parsed` is enough to declare a seared class: every field type, the errors, the base class as
`parsed.Parsed` and the decorator as `parsed.parsed`.

```python
import parsed


@parsed.parsed
class Mined(parsed.Parsed):
    fleet: str = parsed.Str(required=True, doc='the fleet that mined')
    tonnes: float = parsed.Float(ge=0, default=0.0, doc='what it brought up')


Mined.load({'fleet': 'prospector', 'tonnes': 12.5})
```

Command modules keep to `import parsed`, unaliased, so a field can be named anything without shadowing the module.

## Docs

- [`docs/parsed.md`](docs/parsed.md): the package root, and what it re-exports.
- [`docs/command.md`](docs/command.md): commands, and what they declare.
- [`docs/kinds.md`](docs/kinds.md): how a field's words are read.
- [`docs/names.md`](docs/names.md): an app's names, by the resolvers it gives.
- [`docs/tree.md`](docs/tree.md): every command's phrases, compiled and checked as a whole.
- [`docs/doc/index.md`](docs/doc/index.md): commands as data, for the tools that read them.
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
