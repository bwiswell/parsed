# Changelog

Each version of parsed, newest first.

A **Breaking** line means code written for the version before may fail, or behave differently.

The top entry, while it reads *unreleased*, collects what has merged for the next version; each change adds its own
lines as it lands, and the entry is dated when that version is released.

## 0.1.2 — unreleased

**Reading a line.**

### Added

- **`parsed.tree.Tree`:** every command's phrases compiled into one trie of words, from classes or from packages
  (`Tree.collect`). A literal beats a slot, a node has one slot at most, and an optional slot is compiled both ways.
  The build refuses two phrases that read the same lines, two kinds of slot at one node, a flag that's a switch in
  one command and takes a value in another, two flags of one command with one name, a flag name that isn't lowercase
  words, and a field named for one of parsed's own flags (`--help`, `--json`, `--yes`, `--dry-run`).
- **Flags are named from their fields' wire names,** `_` written `-`; a `Bool` flag is a switch, `--no-…` when it
  defaults to `True`.
- **Reading a line:** `Tree.read(line)` gives the command's instance, and `Tree.walk(line)` stops short of it, at
  a `Reading` that keeps each field's words and where they stand. Words split on whitespace, double quotes holding
  spaces; a literal matches case aside, and a quoted word is never a literal or a flag. A slot of several words
  takes them up to a literal after them. seared loads the words into the instance, and names are kept as typed.
- **Flags anywhere after the first word,** `--name=value`, and `--` to end them. A list's flag may be given again.
  parsed's own (`--help`, `--json`, `--yes`, `--dry-run`) are switches every command takes, kept apart from the
  fields.
- **`parsed.ReadError`,** for a line that doesn't read: its message says what's wrong, with the words read up to it.
- **`parsed.Tree` and `parsed.ReadError` on the package root.**
- **The declaring benchmark** times building the tree too, and a **reading benchmark** times walking and reading a
  line for each command.

## 0.1.1 — 2026-10-21

**Declaring a command.** A command is a seared class, said by its phrase, with optional class constants for the
rest. `declaration` reads and checks it: its phrases bound to its fields, every field given a kind, and anything
seared would silently leave out refused by name. Nothing reads a line yet.

### Added

- **`parsed.Command`,** the base of every command: a seared class, decorated with `@parsed.parsed`, said by its
  `PHRASE`. Its class constants say the rest: `EXTRA_PHRASES`, `EFFECT`, `ASKS`, `INTERACTIVE`, `POLYMORPHIC`,
  `INSTEAD`, `REPLY` and `KINDS`. Every one but `PHRASE` is optional, and none is inferred. Each is inherited from a
  base that declares it, and `KINDS` is merged along the class's bases. A class with no `PHRASE` is a base.
- **`parsed.command.declaration(cls)`** reads a class's constants once, checks each, and keeps the result on the
  class. What's wrong is a `DeclarationError` naming the class and the constant, and how to put it right. It
  refuses a command beneath a base that declares fields without being decorated, and a field without an annotation
  on the command or anything it inherits, since seared would leave either out; it suggests the annotation to add.
- **A command can inherit a protocol's request class,** a plain seared class, so its fields and their bounds are the
  protocol's own.
- **Phrases.** A phrase is words separated by spaces: a literal word, `{name}` for one field's value, or a last
  `{name**}` for the rest of the line. `PHRASE`'s slots name the fields that are positionals; every other field is a
  flag. A slot that may be left out, or takes several words, is followed by a word or ends the phrase.
- **`EXTRA_PHRASES`:** an alias takes `PHRASE`'s slots and may leave one out, its field keeping its default. A twin
  renames a slot, which fills the field at its place in `PHRASE` and is read by the `KINDS` entry its name keys.
  `POLYMORPHIC`, when declared, is checked both ways. `declaration` holds each phrase bound, and the flags.
- **Kinds** (`parsed.kinds`): how a field's words are read, as plain data. `parsed.Name(category, scope=…)` is one
  of an app's names, read by what the app gives for its category, a scope naming another field that narrows the
  lookup. Every other field takes its seared type's default (`Word`, `Number`, `Switch`, `Choice`, `Duration`,
  `Moment`); a type with no word form needs a `KINDS` entry, or the command is refused. `declaration` holds each
  field's kind, and `kind_of` gives a slot's.
- **`parsed.Effect` and `parsed.effect_of`:** zeared's vocabulary, value for value, ordered `READ < WRITE < ACTION`.
- **`parsed.ParsedError`,** the base of every error parsed raises, and **`parsed.DeclarationError`,** a `TypeError`
  too.
- **A benchmark,** which ships with the repo, not the package (`python -m bench`). Its first suite times declaring a
  generated tree of 263 commands: creating and decorating them, as importing them does, then each first
  `declaration`, then a re-read. Every number in `docs/overview/benchmarks.md` is generated from the committed
  `bench/results.json`, and a hook checks that the two agree.

## 0.1.0 — 2026-10-21

**The scaffold.** The family's toolchain and release model, and a package root that re-exports seared's
declaration surface. Commands arrive in the releases that follow.

### Added

- **The package root:** `import parsed` gives seared's field types and its errors, its base class as
  `parsed.Parsed` and its decorator as `parsed.parsed`, as zeared re-exports them. Every name is seared's own
  object; the rest of seared stays reachable as `seared.*`. The package ships `py.typed`.
- **The toolchain:** hatchling; ruff, ty, deptry and pytest; `prek` hooks that gate each commit on them, and refuse
  one on `master`; a release workflow that tags `v<version>` when a version merges to `master`.
- **Dependencies:** seared `>=0.4.4,<0.5.0`, pinned to `tag = "v0.4.4"`.
