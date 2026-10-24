# `help.py`: how a command is said and what it does, in its own words

A line that gives `--help` runs nothing ([`app.md`](app.md#sessions)). Where it says a command, it's answered with
the command's help; short of one, with a listing of what it may still say. Both come from what the commands
declare: their phrases, their docstrings, their fields' `doc=` and their kinds.

## A command's help

`command(tree, cls, phrase=0, instead=None)` is a command's help, by the phrase a line said:

```
fleet <fleet> mine [--for <for>]

Mine until the hold is full.

  <fleet>      the fleet
  --for <for>  stop after this long

Also said:
  detachment <detachment> mine [--for <for>]

Examples:
  fleet prospector mine --for 1h30m

It is a step: then joins another after it.
```

- **its usage,** by the phrase the line said ([`tree.usage_of`](tree.md#reading-a-line));
- **its docstring;**
- **a row for each argument:** each slot of the phrase (`<fleet>`), then each flag, a short form first where it has
  one (`-c, --config <config>`), each with its field's `doc=`, or else what its kind's words are
  ([`kinds.md`](kinds.md#describing-its-words)): `a whole number`, `on when given` for a switch; last, for a command
  that may ask first, `--yes` (`answer each question it asks yes`), which its usage ends with too;
- **the other phrases** that say it (`Also said:`), and its `EXAMPLES`;
- **what it asks of the line,** a note each:

| Where | The note |
|---|---|
| it may ask first (`ASKS`) | `It asks before it acts, and --yes answers it.` |
| it can wait (a read with a `REPLY`) | `It can wait on its reply: --until <path=value>, --timeout <span>, --watch, --count <n>; 30s at most by default.` |
| it's a chain's step | `It is a step: then joins another after it.` |
| it's for a person at a terminal (`INTERACTIVE`) | ``It is for a person at a terminal: say `ships make <ship> add <part>` instead.``, with its `INSTEAD`'s usage where an app gives it |

## A listing

`listing(entries)` writes each `Entry(said, summary)` on a line of its own, the summaries in a column after the
widest:

```
relay run [--config <config>]              Run the service until it's stopped.
relay validate-config [--config <config>]  Check the config file, and say what's wrong with it.
relay status [--config <config>]           Say whether the service is up.
```

An app gives the entries ([`app.md`](app.md#sessions)): a mount whose prefix the line hasn't said yet as its
namespace's line (`relay …`, and its `doc`), and the commands beneath where the line's words go as their usages and
summaries. Where one command alone is beneath, its help is given instead of a listing of one. `rows(pairs)` writes
a help's indented rows the same way.

## Docstrings

`doc(obj)` is a docstring as help reads it, and `summary(obj)` its first line; `cleaned(text)` reads any text so:
its indent and trailing spaces cleaned, an RST role's mark left off (`` :class:`Tree` `` as `` `Tree` ``), and
double backticks written single. seared's pages read docstrings alike, so help and the reference pages
([`doc/render.md`](doc/render.md)) say a command the same way.
