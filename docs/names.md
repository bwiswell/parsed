# `names.py`: an app's names, by the resolvers it gives

A [`Name`](kinds.md#name) declares only a category: `fleet`, `station`, `good`. The names behind it are the app's,
and change while it runs, so the app passes its resolvers with each line it reads, by category:

```python
tree.read('fleet Prospector dock vesta', names={'fleet': fleets, 'station': stations})
# FleetDock(fleet='f1', station='vesta')
```

## A resolver

`parsed.Resolver` is a protocol: any object with its three methods is one, with no base of parsed's to subclass.

| Method | Gives |
|---|---|
| `lookup(word, scope)` | the key `word` names, or `None` when it names nothing |
| `suggest(word, scope)` | the names close to `word`, the closest first, for a did-you-mean |
| `options(scope)` | every name it may be, for completion |

How a word matches (case, keys as well as names, spaces) is the resolver's to say. parsed passes the word as the
line gives it, its quotes left off, and keeps the key it returns.

## Scopes

`Name('station', scope='fleet')` narrows a station by the command's `fleet` field. The resolver is given the scope
as the fleet field's value once it's read, as a string: its key, when the fleet is itself a name with a resolver.

- **A scope is read first,** whatever its place on the line: `board ceres --fleet Hauler` reads the fleet, then the
  station within its reach.
- **A scope the line leaves out** is `None`, and so is a name with no scope: the lookup is across every name of the
  category.
- **A command whose scopes go round** (a station scoped by a berth that's scoped by the station) is refused when
  it's declared, since neither could be read first.

## Pairs

A [`Pairs`](kinds.md#pairs) category's resolver is a `parsed.names.PairsResolver`: a resolver for the keys (a
routine's variables, scoped by the routine), with one method more.

| Method | Gives |
|---|---|
| `values(key, scope)` | the resolver for `key`'s values, or `None` to keep them as typed |

Which names a value may be depends on its key, and on the scope: `ore` takes a good and `home` a station. Each value
is read by the resolver `values` gives, with no scope of its own, since `values` knew the key and the scope when it
gave it. A plain `Resolver` given for a `Pairs` category is a mistake in the app, and raises a `TypeError`.

## With no resolver

A category with no resolver reads as typed. parsed never invents a key: a normalization it guessed would drift from
the app's own. So a line read with no names at all keeps every name as its words say it, which is what a check or a
render of a line needs.

## What a refusal says

A word no name answers to is a [`ReadError`](errors.md#readerror) at that word, with the resolver's suggestions and
the command's usage:

```
--into: no fleet 'Haulr'; did you mean Hauler? `fleets merge <fleet> --into <into> [--quiet]`
fleet {fleet} dock {station}: no station 'vesta' for fleet 'Hauler' `fleet <fleet> dock [<station>]`
```

A slot by an alias reads by its own category, so a polymorphic twin's word is refused as that category's:
`detachment {detachment} mine: no detachment 'Prospector'`. A pair's key is refused as its category's
(`no variable 'hme' for routine 'mining'`), and its value by its key (`no home 'mars'`).

A [literal word](kinds.md#literal-words) comes before the resolver: `Name('station', words={'here': None})` reads
`here` as `None`, and only `"here"`, quoted, is looked up.
