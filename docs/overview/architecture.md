# Architecture

parsed is a library of the `*eared` family: general-purpose, and domain-agnostic.

## Where it sits

```
seared  <-  parsed
seared  <-  zeared
```

- **parsed depends on seared alone.** A command is a seared class, so seared does its typing, its validation and
  its JSON Schema. parsed never imports zeared: a command line needs no mesh.
- **A sibling of zeared, not built on it.** An app may use both: zeared for the messages between its nodes, parsed
  for the commands its users type.
- **Declared to be read by tools.** An app declares its commands in a module of their own, which imports only
  parsed, so tooling (the family's [tooled](https://github.com/bwiswell/tooled), for agents) can read them
  without the app's runtime.

## What it holds

- **The package root** ([`../parsed.md`](../parsed.md)): seared's declaration surface, re-exported, and parsed's
  own names.
- **Commands** ([`../command.md`](../command.md)): `Command`, the base of every command; the constants a command
  declares; and `declaration`, which reads and checks them, keeping the result on the class.
- **Phrases** ([`../_phrase/index.md`](../_phrase/index.md)): a phrase's grammar, and how a command's phrases
  bind to its fields, for `declaration` to check.
- **Kinds** ([`../kinds.md`](../kinds.md)): how a field's words are read, as plain data: a `Name` for an app's
  names, `Pairs` for a keyed field's pairs, and a default for each seared type that has a word form, reading a word
  (or one of its literal words) to the field's wire value.
- **Names** ([`../names.md`](../names.md)): the resolvers an app gives with each line, by category, a scope
  read before the names it narrows; a category with none reads as typed.
- **The tree** ([`../tree.md`](../tree.md)): every command's phrases compiled into one trie of words, a literal
  beating a slot, with the checks across commands: no line read two ways, no flag meaning two things.
- **The walk** ([`../_walk/index.md`](../_walk/index.md)): a line split into words, its flags split off, and its
  words walked from the tree's root to a `Reading`, each field's words kept for seared to load, a chain's steps
  read in turn where its shared part ends, each one's names where the steps before it have moved the chain;
  completion, what may come next on a line being typed; and rendering, an instance back to its line.
- **The app** ([`../app.md`](../app.md)): a program's trees, each mounted under a prefix of words with its own
  parameters; a line sent to its mount by its first words; the handlers commands run with, bound by callable or by
  a path imported when first looked up; the names lines are read with; and sessions, which hold the app's state
  open and call each line's handler with a fresh context ([`../context.md`](../context.md)), giving what came of
  it as one envelope, with its exit code ([`../reply.md`](../reply.md)); a handler that asks first, answered by
  `--yes`, the session's answer, or left undone with its question; hooks before and after each command, and on its
  error, in a stated order; and a session's subjects, the words tried before a bare line.
- **The command line** ([`../argv.md`](../argv.md)): `app.main(argv)`, a program's arguments run as its command
  line: its root options before the first word, read from a seared class and given to handlers, `--version` and
  `--help` there; then the line, every flag after the first word its own; a person at a terminal when stdin and
  stdout are one; each result's text written as it comes, and its exit code.
- **Waits** ([`../wait.md`](../wait.md)): a read with a `REPLY` takes `--until` conditions on its reply and a
  `--timeout`, each condition's path checked against the reply's schema before anything runs; a session reads it
  again on the app's change signal, or on an interval, until they're met or the bound passes. `--watch` streams each
  reply as it changes.
- **Docs** ([`../doc/index.md`](../doc/index.md)): a command as data, a `CommandDoc` in `zeared.doc`'s shape, and
  its arguments as a closed JSON Schema, for the tools that read commands; a chain as one tool call, its steps
  tagged by their words; and `python -m parsed check`, a package's commands and chains checked in its CI.
- **Effects** ([`../effect.md`](../effect.md)): what running a command does, on zeared's scale.
- **Errors** ([`../errors.md`](../errors.md)): `ParsedError`, `DeclarationError`; `ReadError`, one error for a line
  that doesn't read, with where it stands, a hint and what may have been meant; `RefusedError`, for a command for a
  person at a terminal run with none; and `RenderError`, for an instance no line can say.

Help arrives next, adding its part here. What each part costs is in
[`benchmarks.md`](benchmarks.md).
