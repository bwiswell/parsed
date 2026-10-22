# `_walk/_render.py`: an instance back to its line

`render(tree, command, names)` writes the line that says a command's instance, so the tree reads that line back to
the same instance. `Tree.render(command, names=…)` calls it.

```python
tree.render(FleetMine(fleet='f1', for_=timedelta(seconds=5400)))
# 'fleet f1 mine --for 1h30m'
tree.render(FleetMine(fleet='d2'), names=names)
# 'detachment d2 mine'
```

## Which phrase

The first of the command's phrases, `PHRASE` and then each of `EXTRA_PHRASES`, that can say the instance:

- **a field the phrase leaves out holds its default,** and an optional slot holding its field's default is left out
  too, as the line it reads from would have (`FleetDock(fleet='f1')` is `fleet f1 dock`);
- **with names,** each slot read by a `Name` with a resolver holds a key the resolver knows, given its scope, so a
  detachment's key is said by the detachment's twin and not by the fleet's phrase. Loose, any value does.

## The words

**Each value is written by its field's kind** ([`kinds.md`](../kinds.md#writing-a-value)), from its wire value: a
literal word for a value one reads to (`None` as `off`), else the kind's own spelling (`5400.0` seconds as `1h30m`).
A list's values are written one by one, and a pair's key and value in turn. The rest of the line is written as its
words, single-spaced, or as one quoted word where its own spacing differs.

**A word is quoted** where the line would read it otherwise:

| The value | Written |
|---|---|
| spelled like a literal word that may stand there, case aside | `dock "nearest"` |
| holding a space | `"Vruba'a Belt 1"` |
| beginning with `--` | `say "--loud" now` |
| nothing at all | `""` |

A value holding a double quote can't be said, since a line has no escapes, and raises a `RenderError`.

**Then the flags,** in the order the command declares its fields, each not at its default: a switch alone
(`--quiet`, or `--no-stop` for one that defaults to `True`), a value after its name (`--for 1h30m`), and a list's
flag once for each of its values (`--tag a --tag b`).

A `RenderError` also says when the instance isn't one of the tree's commands, or when no phrase can say it: with
names, a value no resolver knows.
