# `tree.py`: every command's phrases, compiled and checked as a whole, and the lines it reads

`parsed.Tree(commands)` declares each command class, compiles every phrase into one trie of words, and checks the
whole. `Tree.collect('pkg.commands', …)` builds one from every command in some modules or packages, their
submodules included. A base, which has no `PHRASE`, is left out, as is any class that isn't a command.

```python
import parsed

tree = parsed.Tree.collect('farm.commands')
tree.read('fleet prospector mine --for 1h30m')
# FleetMine(fleet='prospector', for_=datetime.timedelta(seconds=5400))
```

## Reading a line

`tree.read(line)` reads a line to its command's instance. `tree.walk(line)` stops short of it, at a
[`Reading`](_walk/_walker.md#reading): the command, and each field's words.

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
`1,000` to `1000`, `1h30m` to `5400.0` seconds, `GREEN` to an `Enum`'s `'green'`. A name is kept as typed. Then
seared loads the values, so a field's bounds and pattern hold on a line too.

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

## Flags

A flag stands anywhere after the line's first word: `--for 10m`, or `--for=10m`. `--` ends the flags, so every word
after it is a word. Flags are split off a line before the walk, which doesn't yet know its command, so a flag's name
says whether it takes a value, across the whole tree:

- **a flag is its field's wire name,** `_` written `-`: `max_bytes` is `--max-bytes`, and a field with
  `data_key='for'` is `--for`;
- **a `Bool` flag is a switch,** written `--no-…` when its field defaults to `True`;
- **every other flag takes a value.**

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

A command whose own declaration doesn't check is refused as `declaration` refuses it
([`command.md`](command.md#declarationcls)).
