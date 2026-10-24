# `tree.py`: every command's phrases, compiled and checked as a whole, and the lines it reads

`parsed.Tree(commands)` declares each command class, compiles every phrase into one trie of words, and checks the
whole. `Tree.collect('pkg.commands', …)` builds one from every command in some modules or packages, their
submodules included. A base, which has no `PHRASE`, is left out, as is any class that isn't a command.

The commands are compiled in the order given; `Tree.collect` gives them in the order they're declared (each target
in turn, its modules by name, and a module's by where each class begins). A node's words follow that order, so a
refusal lists them, and completion offers them, as the commands that say them were written.

```python
import parsed

tree = parsed.Tree.collect('farm.commands')
tree.read('fleet prospector mine --for 1h30m')
# FleetMine(fleet='prospector', for_=datetime.timedelta(seconds=5400))
```

## Under a prefix

`Tree(commands, under='relay')`, or `Tree.collect('service.cli', under='relay')`, puts every phrase after the
prefix's words. The tree then reads, completes and writes whole lines, and says the prefix in its refusals and
hints:

```python
tree = parsed.Tree.collect('service.cli', under='relay')
tree.read('relay run')        # Run(config=None)
tree.read('relay')            # ReadError: relay: then what? run | validate-config | status
```

A prefix is words, as a phrase's are; several are spaced once (`tree.under == 'rio relay'`). `tree.root` is where a
line's walk begins, and `tree.top` where every phrase does, past the prefix. An [app](app.md) mounts each tree it
holds under one.

## Reading a line

`tree.read(line)` reads a line to its command's instance. `tree.walk(line)` stops short of it, at a
[`Reading`](_walk/_walker.md#reading): the command, and each field's words. With `placeholders=True`, it reads an
unquoted `<name>` as any value, as in the lines help shows ([`_walk/_walker.md`](_walk/_walker.md#placeholders)).
`tree.usage(reading.end)` says how the command is said by the phrase it ended at, prefix and flags and all:
`fleets merge <fleet> --into <into> [--quiet]`. `tree.usage_of(cls)` says one of its commands by its `PHRASE` alike
(`fleet <fleet> dock [<station>]`), and raises a `KeyError` for a class that isn't one of them.

The line is split into words, double quotes holding a name with spaces (`"Vruba'a Belt 1"`), and its flags are
split off. Then it's read from the root, a word at a time:

- **a word that is a literal child** of the node takes that branch, case aside: a literal beats a slot, so with
  `jump {system}` beside `jump nearest {ore}`, `jump nearest coal` reads the second. A quoted word is never a
  literal, so `jump "nearest"` reads the first;
- **else the node's slot** takes it: one word, several (up to a word that's a literal after them, or the end), or
  the rest of the line. A node has one slot at most.

An optional slot is compiled both with it and without it, so `log {n}` ends at `log` (its `n` left at its
default) and at `log 40`. Where a walk ends, one phrase ends at most (`node.end`): the command, the phrase, and the
slots read on the way.

**Each word is read by its field's kind** ([`kinds.md`](kinds.md#reading-a-word)) to the field's wire value:
`1,000` to `1000`, `1h30m` to `5400.0` seconds, `GREEN` to an `Enum`'s `'green'`. Then seared loads the values, so
a field's bounds and pattern hold on a line too.

**A name is read by the app's resolver** for its category, given with the line: `tree.read(line, names={…})`
([`names.md`](names.md)). A scoped name is read after its scope, and a category with no resolver reads as typed.

**A line that doesn't read raises one error,** a `ReadError`, whichever part refused it: the walk, a kind, or
seared, whose refusal comes back as the word that gave the value. Its message says what's wrong, with the words
read up to it, then any did-you-mean and a hint; the same parts are there as data, with where on the line it stands
([`errors.md`](errors.md#readerror)):

```
fleet f1 jump: which system? `fleet f1 jump <system>`
no command 'fleet f1 mien'; did you mean mine?
log {n}: must be >= 1, got 0
```

[`_walk/_walker.md`](_walk/_walker.md#what-it-refuses) has each refusal.

## Chains

A chain's steps (the commands beneath a base declaring `STEPS = True`: [`command.md`](command.md#chains)) are said
on one line, joined by `then`:

```python
reading = tree.walk('fleet prospector jump sol then move belt then mine')
[step.command for step in reading.steps]   # [FleetJump, FleetMove, FleetMine]
reading.phrase                             # 'fleet {fleet} jump {system} then move {to} then mine'
```

- **The line is cut at each unquoted `then`,** never at a flag's value or after `--`. The first piece is read as
  any line is. A piece after `then` is read where the first step's shared part ends: its phrase up to its last slot
  of the base's own fields (`fleet {fleet}`, or a twin's `detachment {detachment}`). So a later step says only its
  own words, and its shared fields are the first step's.
- **`then` only joins steps:** where the first piece isn't a step, the line is read as one command, `then` a word
  of it (`say hello then goodbye`). A step's phrase can't say `then`.
- **A step may move the chain on** (`MOVES`), so a later step's names whose scope follows the chain are looked for
  where the fleet will be: `jump sol then dock ceres` looks for ceres in sol
  ([`command.md`](command.md#a-chains-place)).
- **Refused:** `then` with no step on one side, a first piece that isn't a step where the line doesn't read as one
  command, a later step that isn't one of the chain's, and a wait (`--until`, `--watch`) in a chain.

`tree.chains` holds each chain's base, to its steps among the tree's commands. As one tool call, a chain is the
shared fields and its steps tagged by their words ([`doc/chains.md`](doc/chains.md)), and `tree.render(steps)`
writes the steps back to their line.

## Completing a line

`tree.complete(text, names=…)` offers what may come next on a line being typed, up to the cursor: the words that
may follow, a slot's values (a name's from its resolver's `options`), the command's flags, a flag's values, and a
pair's keys and values. It gives the candidates, as they'd be typed, and how many characters before the cursor each
replaces ([`_walk/_complete.md`](_walk/_complete.md)):

```python
tree.complete('fleet f1 mine --f')
# Completion(words=['--for'], replace=3)
```

## Writing a line back

`tree.render(command, names=…)` is reading's other way: the line that says an instance, which reads back to it. It
takes the first of the command's phrases that can say the instance (with names, one whose names the resolvers
know), writes each value by its field's kind, quoting a word where the line would read it otherwise, then the flags
not at their defaults ([`_walk/_render.md`](_walk/_render.md)):

```python
tree.render(FleetDock(fleet='f1', station='nearest'))
# 'fleet f1 dock "nearest"'
```

Given a chain's steps in a list, it writes them on one line joined by `then`, each step's names where the chain will
be by then: `fleet f1 jump sol then dock ceres` ([`_walk/_render.md`](_walk/_render.md#a-chain)).

## Flags

A flag stands anywhere after the line's first word: `--for 10m`, or `--for=10m`. `--` ends the flags, so every word
after it is a word. Flags are split off a line before the walk, which doesn't yet know its command, so a flag's name
says whether it takes a value, across the whole tree:

- **a flag is its field's wire name,** `_` written `-`: `max_bytes` is `--max-bytes`, and a field with
  `data_key='for'` is `--for`;
- **a `Bool` flag is a switch,** written `--no-…` when its field defaults to `True`;
- **every other flag takes a value.**

**A wait's flags** join the table once any command can wait: `--until`, `--timeout` and `--count`, each taking a
value, and `--watch`, a switch ([`wait.md`](wait.md)). A field of another command may take one of their names only
as the wait's does. `tree.waits` says whether any command can wait.

`tree.flags` is the tree-wide table, name to arity; `tree.flags_of(cls)` is one command's flags, each with its name,
its field, its arity and whether it's negated. parsed's own, `--help`, `--json`, `--yes` and `--dry-run`, are
switches every command takes, kept apart from its fields (`Reading.own`).

## What the build refuses

Each is a `DeclarationError` naming the commands and the phrases:

| Refused | Because |
|---|---|
| two phrases that end at one node | they read the same lines; an optional slot left out counts |
| two kinds of slot at one node: one word, several, the rest of the line | a line would read two ways |
| a flag that's a switch in one command and takes a value in another | flags are read before the command is |
| two flags of one command with one name (`n`, and a field with `data_key='n'`) | |
| a flag name that isn't lowercase words (`--Count`) | give the field a `data_key` |
| a field whose flag is one of parsed's own: `--help`, `--json`, `--yes`, `--dry-run` | parsed takes them for every command |
| a field whose flag is `--until`, `--timeout`, `--watch` or `--count`, on a command that can wait | a wait takes them there |
| a step whose phrase says `then` | it joins a chain's steps |

A command whose own declaration doesn't check is refused as `declaration` refuses it
([`command.md`](command.md#declarationcls)).
