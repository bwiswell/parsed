# Changelog

Each version of parsed, newest first.

A **Breaking** line means code written for the version before may fail, or behave differently.

The top entry, while it reads *unreleased*, collects what has merged for the next version; each change adds its own
lines as it lands, and the entry is dated when that version is released.

## 0.1.3 — unreleased

**Names and completion.**

### Added

- **Names read by the app's resolvers:** `tree.read(line, names={'fleet': …})` and `tree.walk(…, names=…)` read
  each `Name` by the resolver given for its category, to the key it returns. `parsed.Resolver` is the protocol:
  `lookup(word, scope)`, `suggest(word, scope)` and `options(scope)`. A category with no resolver reads as typed.
- **Scopes read first:** a scoped name's resolver is given its scope's value, read before it whatever their order on
  the line; a scope the line leaves out is `None`. A renamed slot reads by its own category.
- **A word no name answers to** is a `ReadError` at that word, with the resolver's suggestions and the command's
  usage.
- **A command whose scopes go round is refused** when it's declared.
- **Literal words:** any kind may take `words`, each a word read to a value of its own before the kind's form, case
  aside and never quoted (`Number(suffix='%', words={'off': None})` reads `off` as `None`). A literal for `None`
  wants a `nullable` field. A kind of an app's own overrides `form`; `read` keeps the literals first.
- **A number's suffix:** `Number(suffix='%')` reads `30%` as `30`.
- **Pairs:** `parsed.kinds.Pairs(category, scope=…)` reads a keyed field's words, said as the rest of the line, as
  `key value` pairs: each key by the app's `PairsResolver`, and each value by the resolver it gives that key. A
  command is refused when `Pairs` reads a field that isn't keyed or isn't the rest of the line.

## 0.1.2 — 2026-10-21

**Reading a line.** A tree compiles every command's phrases and checks them as a whole, then reads a line to its
command's instance: the flags split off, the words walked, each read by its field's kind, and seared loading the
values. A line that doesn't read is one error, with where it stands, a hint and what may have been meant. Names are
kept as typed, and nothing runs a command yet.

### Added

- **`parsed.Tree`:** every command's phrases compiled into one trie of words, from classes or from packages
  (`Tree.collect`). A literal beats a slot, a node has one slot at most, and an optional slot is compiled both ways.
  The build refuses two phrases that read the same lines, two kinds of slot at one node, a flag that's a switch in
  one command and takes a value in another, two flags of one command with one name, a flag name that isn't lowercase
  words, and a field named for one of parsed's own flags (`--help`, `--json`, `--yes`, `--dry-run`).
- **Flags are named from their fields' wire names,** `_` written `-`; a `Bool` flag is a switch, `--no-…` when it
  defaults to `True`.
- **Reading a line:** `Tree.read(line)` gives the command's instance, and `Tree.walk(line)` stops short of it, at
  a `Reading` that keeps each field's words and where they stand. Words split on whitespace, double quotes holding
  spaces; a literal matches case aside, and a quoted word is never a literal or a flag. A slot of several words
  takes them up to a literal after them. seared loads the instance, and names are kept as typed.
- **Flags anywhere after the first word,** `--name=value`, and `--` to end them. A list's flag may be given again.
  parsed's own (`--help`, `--json`, `--yes`, `--dry-run`) are switches every command takes, kept apart from the
  fields.
- **Word forms:** each word is read by its field's kind to the field's wire value, before seared checks it. A number
  may group its thousands by commas (`1,000`); a span of time says its units (`90s`, `10m`, `1h30m`); an `Enum`'s
  value reads case aside; `true` or `false` for a `Bool` said as a word; ISO 8601 for dates and times; a `UUID`
  checked. `Kind.read(word, field)` is each kind's.
- **One error for a line that doesn't read,** `parsed.ReadError`, whichever part refused it. Its message says
  what's wrong with the words read up to it, then any did-you-mean
  (`no command 'fleet f1 mien'; did you mean mine?`) and a hint, a usage with a `<slot>` for each value
  (``fleet f1 jump: which system? `fleet f1 jump <system>` ``). As data: its `kind`, `line`, `column`, `word`,
  `field`, `hint` and `suggestions`, and `to_json()`.
- **seared's refusals come back as the word that gave the value:** a value out of its bounds, lengths or pattern is
  a `ReadError` of kind `'validation'`, at that word (`log {n}: must be >= 1, got 0`).
- **A required flag left out is refused by the walk,** with the line it's missing from as the hint.
- **`Reading.load` refuses a key the command doesn't know.**
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
