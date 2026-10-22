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
  names, and a default for each seared type that has a word form.
- **The tree** ([`../tree.md`](../tree.md)): every command's phrases compiled into one trie of words, a literal
  beating a slot, with the checks across commands: no line read two ways, no flag meaning two things.
- **The walk** ([`../_walk/index.md`](../_walk/index.md)): a line split into words, its flags split off, and its
  words walked from the tree's root to a `Reading`, each field's words kept for seared to load.
- **Effects** ([`../effect.md`](../effect.md)): what running a command does, on zeared's scale.
- **Errors** ([`../errors.md`](../errors.md)): `ParsedError`, `DeclarationError` and `ReadError`.

Names read against an app's own, running a command, and the docs a command describes itself with, arrive in the
releases that follow, each adding its part here. What each part costs is in [`benchmarks.md`](benchmarks.md).
