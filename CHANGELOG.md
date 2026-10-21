# Changelog

Each version of parsed, newest first.

A **Breaking** line means code written for the version before may fail, or behave differently.

The top entry, while it reads *unreleased*, collects what has merged for the next version; each change adds its own
lines as it lands, and the entry is dated when that version is released.

## 0.1.1 — unreleased

**Declaring a command.**

### Added

- **`parsed.Command`,** the base of every command: a seared class, decorated with `@parsed.parsed`, said by its
  `PHRASE`. Its class constants say the rest: `EXTRA_PHRASES`, `EFFECT`, `ASKS`, `INTERACTIVE`, `POLYMORPHIC`,
  `INSTEAD`, `REPLY` and `KINDS`. Every one but `PHRASE` is optional, and none is inferred. Each is inherited from a
  base that declares it, and `KINDS` is merged along the class's bases. A class with no `PHRASE` is a base.
- **`parsed.command.declaration(cls)`** reads a class's constants once, checks each, and keeps the result on the
  class. What's wrong is a `DeclarationError` naming the class and the constant, and how to put it right. It
  refuses a command beneath a base that declares fields without being decorated, since seared would drop them.
- **A command can inherit a protocol's request class,** a plain seared class, so its fields and their bounds are the
  protocol's own.
- **Phrases.** A phrase is words separated by spaces: a literal word, `{name}` for one field's value, or a last
  `{name**}` for the rest of the line. `PHRASE`'s slots name the fields that are positionals; every other field is a
  flag. A slot that may be left out, or takes several words, is followed by a word or ends the phrase.
- **`EXTRA_PHRASES`:** an alias takes `PHRASE`'s slots and may leave one out, its field keeping its default. A twin
  renames a slot, which fills the field at its place in `PHRASE` and is read by the `KINDS` entry its name keys.
  `POLYMORPHIC`, when declared, is checked both ways. `declaration` holds each phrase bound, and the flags.
- **`parsed.Effect` and `parsed.effect_of`:** zeared's vocabulary, value for value, ordered `READ < WRITE < ACTION`.
- **`parsed.ParsedError`,** the base of every error parsed raises, and **`parsed.DeclarationError`,** a `TypeError`
  too.

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
