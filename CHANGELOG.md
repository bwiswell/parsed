# Changelog

Each version of parsed, newest first.

A **Breaking** line means code written for the version before may fail, or behave differently.

The top entry, while it reads *unreleased*, collects what has merged for the next version; each change adds its own
lines as it lands, and the entry is dated when that version is released.

## 0.1.6 — unreleased

**Waiting.**

### Added

- **`--until` on reads:** a command that declares `EFFECT = READ` and a `REPLY` can wait
  (`declaration(cls).can_wait`). `--until PATH=VALUE`, repeatable, is a condition on its reply in `tooled wait`'s
  grammar: a dotted path, a whole number stepping into a list, and a value read as JSON if it reads as JSON, else
  as a string, compared as JSON compares. Each path is checked against the reply's dump schema when the line is
  read, before anything runs, with what may have been meant. `--timeout` bounds it, a span of time, 30 s by
  default.
- **A wait's flags are a tree's** once any of its commands can wait (`tree.waits`): a command that can wait can't
  name a field for them, and any other command refuses `--until` with the reason, unless a field of its own takes
  it. A reading's `wait` holds the conditions and the bound (`parsed.wait.Wait`), and completion offers them.
- **`result.met`:** a session runs a line that waits once, so far, and says whether its reply met every condition;
  its handler returns its `REPLY`.
- **`parsed.kinds.span(word)`:** a span of time's seconds, as `Duration` reads one.

## 0.1.5 — 2026-10-22

**Running commands.** An app mounts trees of commands under prefixes of words, binds the handler each command
runs with, and gives the names its lines are read with. A session holds the app's state open and runs each line by
its handler, with a context made for it, between hooks; what came of it is one envelope, the same for every parsed
app, with its exit code. A handler may ask before it acts, answered by `--yes`, by a person, or left undone.

### Added

- **A tree under a prefix:** `Tree(commands, under='relay')` and `Tree.collect(…, under=…)` put every phrase after
  the prefix's words; the tree reads, completes and writes whole lines, and says the prefix in its refusals and
  hints. `tree.top` is where the phrases begin.
- **`parsed.App(prog)`:** a program's commands, as trees mounted under prefixes of words.
  `app.mount(target, under=…, params=…)` mounts a tree, or a module or package by name, and returns its `Mount`;
  one package may be mounted several times, each with its own prefix and its own `params` (a service's settings).
  A line goes to its mount by its first words, then the mount's tree reads it: `app.walk` (a `Routed`: the mount
  and the reading), `app.read`, `app.complete` and `app.render`. A mount that would make a line read two ways is
  refused, naming both.
- **Names on the app:** `app.names(category, resolver)` reads a category's names in every mount, and
  `mount.names(category, resolver)` in that mount alone, over the app's.
- **Handlers:** `app.on(Cls, handler)` binds what a command runs with, in every mount that holds it, and
  `mount.on(Cls, handler)` one for that mount alone, which wins there. A handler is a callable, or a path,
  `'pkg.module:function'`, imported when it's first looked up, so an app that gathers several packages imports none
  of their runtimes to read a line. `mount.handler(Cls)` looks one up.
- **Sessions:** `async with app.open(state, verbosity=…) as session` holds the app's state open; a state that's a
  context manager, sync or async, is entered when it opens and left when it closes. `await session.call(line)`
  runs the command a line says by its handler, `handler(command, ctx)`, awaited if it's async, and gives what the
  handler returns: its `REPLY`, text or nothing, anything else refused. A line that gives `--help` runs nothing,
  and is answered with its command's usage.
- **`parsed.Context`:** what a handler is given beside its command, made fresh for each line: the app's `state`
  (`Context[S]`), the `mount` and its `params`, the `names`, the `line` and its `reading`, the `phrase` that said
  it (a twin's wording told from its command's), `dry_run`, and the session's `verbosity`.
- **`parsed.Result`:** `await session.run(line)` gives what came of a line as one envelope, the same for every
  parsed app: the `command` that said it, `ok`, `done`, the `reply`, its `text` (a reply's `str()`), and any
  `error` as data, raising nothing. `result.code` is its exit code: 2 for a line that doesn't read, 4 for a value
  its field refuses, 1 for a handler's failure. `result.to_json()` writes every key.
- **`app.run(line, state)`** runs one line in a session of its own, for a program that runs one and exits.
- **Asking first:** a handler returns `parsed.Ask(question, then)`, having done nothing yet, and `then` acts on a
  yes, which may ask again. `--yes` on the line, or `yes=True` to `run`, `call` and `app.run`, answers every
  question yes, on any command; else the session's `answer` does (`app.open(state, answer=…)`), and
  `parsed.reply.terminal` prompts a person. A question left unanswered, or answered no, leaves the line undone: the
  result's `asks` holds it, with exit code 0, and `call` gives the `Ask` back.
- **Hooks:** `app.before(hook)`, `app.after(hook)` and `app.on_error(hook)` run around each command's handler, or,
  with commands named, around theirs alone, in a stated order: before hooks the app's then the command's, after
  and on-error hooks the command's then the app's, each scope's in the order added (`app.hooks(Cls)`). An after hook
  sees what the handler came to; an on-error hook sees a failure in any of them, which then goes on.
- **`tree.usage(end)`:** how the command a walk ended at is said, prefix and flags and all.
- **The running benchmark** times a line run in a session, routed, read, its handler called between hooks, and its
  envelope made.

### Changed

- **`DeclarationError`** covers a tree's and an app's mistakes too: mounts that would read a line two ways, and a
  handler or a resolver bound twice.

## 0.1.4 — 2026-10-22

**Writing back and describing.** An instance is written back to the line that says it, which reads back to it.
`parsed.doc` describes each command as data, for the tools that read commands: a `CommandDoc`, a closed JSON
Schema, and a key for policy. `parsed check` checks a package's commands in its CI, each command's new `EXAMPLES`
among them.

### Added

- **Rendering:** `tree.render(command, names=…)` writes the line that says an instance, which reads back to it. It
  takes the first of the command's phrases that can say it (with names, one whose names the resolvers know, so a
  twin's key is said by its twin), writes each value by its field's kind, quotes a word where the line would read
  it otherwise (`dock "nearest"`), and gives the flags not at their defaults. `parsed.RenderError` for an instance
  no phrase can say.
- **`Kind.write(value, field)`:** a wire value as the words a line says it in, a literal word first, else
  `Kind.spell`, each kind's own (`5400.0` seconds as `1h30m`).
- **`parsed.doc`:** commands as data, for the tools that read them, in `zeared.doc`'s shape. `is_command_class`;
  `introspect_command(cls)`, a `CommandDoc` of seared's `SchemaDoc`, the phrases, each slot (its field and kind),
  the flags, each field's kind, the constants, and `fields_from`, the seared classes it takes fields from that
  aren't commands (a protocol's request class it inherits). `json_schema(cls)`: seared's load schema, closed, with
  `x-kind` and `x-scope` on a name's property and the command's own `x-` keys (`x-phrase`, `x-effect`, `x-asks` and
  the rest).
- **Command keys, for policy:** `parsed.doc.command_key(command, names=…)`, an instance's key by the phrase that
  says it, its words and its slots' values slashed as a topic is (`fleet/f1/dock/vesta`); a slot of several words,
  the rest of the line, an optional slot at its default and the flags left out. `CommandDoc.keys` holds each
  phrase's template (`fleet/{fleet}/dock/{station}`).
- **`parsed check`, for an app's CI:** `python -m parsed check <target> …` builds the tree of a package's commands
  and checks each one. Two instances made from its fields' types and constraints each render and read back to
  themselves; each line of its `EXAMPLES` reads to it; and its schema takes its example, is closed, has `enum`s a
  constrained decoder can hold, and stays compact (`--max-schema-bytes`, 2048 by default). The report is JSON on
  stdout, exit `1` with problems, and a usage that doesn't read is a JSON error on stderr, exit `2`.
  `parsed.doc.check(targets)` gives the same as a `CheckReport`.
- **`EXAMPLES`:** an optional tuple of lines that say a command, a `<name>` standing for any value, for help and
  for `parsed check` to read. `CommandDoc.examples` holds them.
- **Placeholders:** `tree.walk(line, placeholders=True)` reads an unquoted `<name>` as any value, by no kind and no
  resolver.
- **A rendering benchmark** times writing an instance of each command back to its line.

## 0.1.3 — 2026-10-21

**Names and completion.** A line is read with the app's own names, by the resolver it gives for each category, a
scope read before the names it narrows. Any kind may take literal words, and a keyed field its pairs. Completion
offers what may come next on a line being typed, from the same tree. A slot's other name is an alias now, declared
in `ALIASES`, where 0.1.2 took it from its place.

### Added

- **Names read by the app's resolvers:** `tree.read(line, names={'fleet': …})` and `tree.walk(…, names=…)` read
  each `Name` by the resolver given for its category, to the key it returns. `parsed.Resolver` is the protocol:
  `lookup(word, scope)`, `suggest(word, scope)` and `options(scope)`. A category with no resolver reads as typed.
- **Scopes read first:** a scoped name's resolver is given its scope's value, read before it whatever their order on
  the line; a scope the line leaves out is `None`. A slot by an alias reads by its own category.
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
- **Completion:** `tree.complete(text, names=…)` offers what may come next on a line being typed, up to the cursor:
  the words that may follow, a slot's values (its kind's literal words and offers, a name's resolver's `options`,
  given its scope), a whole command's flags (in the rest of the line too), a flag's values, and a pair's keys, then
  a key's values. It gives the candidates, quoted where one holds a space, and how many characters each replaces.
  `Kind.offers(field)` is each kind's; `split(line, partial=True)` holds an open quote's word.
- **The completing benchmark** times completing a line for each command.

### Changed

- **Breaking: `ALIASES` replaces renaming a slot by its place.** A slot named after no field is an alias in
  `ALIASES` (`{'detachment': 'fleet'}`), merged along the bases as `KINDS` is, and fills the field it gives by
  name. So a twin may leave out an optional slot (`detachment {detachment} dock nearest`), slots may come in any
  order, and `PHRASE` may say one (`detachment {detachment} rejoin`). An alias reads by its own `KINDS` entry, if it
  has one, else by its field's kind. A twin written for 0.1.2 needs its base's `ALIASES`.
- **A slot left empty hints the rest of the command's usage,** flags and all, where one command lies past it:
  ``fleets merge: which fleet? `fleets merge <fleet> --into <into> [--quiet]` `` (the hint was the slot alone).
  Where several commands lie past it, the hint is the slot and `…`, as before.

### Fixed

- **`Tree.collect` takes commands in the order they're declared,** not by class name, so the words a refusal lists
  and completion offers come as written (`mine | dock | jump`, where they read `buy | dock | jump`).

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
