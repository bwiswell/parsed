# `tree.py`: every command's phrases, compiled and checked as a whole

`parsed.tree.Tree(commands)` declares each command class, compiles every phrase into one trie of words, and checks
the whole. `Tree.collect('pkg.commands', …)` builds one from every command in some modules or packages, their
submodules included. A base, which has no `PHRASE`, is left out, as is any class that isn't a command.

```python
from parsed.tree import Tree

tree = Tree.collect('farm.commands')
```

## How a line will walk it

A line is read from the root, a word at a time:

- **a word that is a literal child** of the node takes that branch: a literal beats a slot, so with
  `jump {system}` beside `jump nearest {ore}`, `jump nearest coal` reads the second;
- **else the node's slot** takes it: one word, several (until a word that's a literal after them, or the end), or
  the rest of the line. A node has one slot at most.

An optional slot is compiled both with it and without it, so `log {n}` ends at `log` (its `n` left at its
default) and at `log 40`. Where a walk ends, one phrase ends at most (`node.end`): the command, the phrase, and the
slots read on the way.

## Flags

Flags are split off a line before the walk, since they may stand anywhere after the first word and the walk doesn't
yet know its command. So a flag's name says whether it takes a value, across the whole tree:

- **a flag is its field's wire name,** `_` written `-`: `max_bytes` is `--max-bytes`, and a field with
  `data_key='for'` is `--for`;
- **a `Bool` flag is a switch,** written `--no-…` when its field defaults to `True`;
- **every other flag takes a value.**

`tree.flags` is the tree-wide table, name to arity; `tree.flags_of(cls)` is one command's flags, each with its name,
its field, its arity and whether it's negated.

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
