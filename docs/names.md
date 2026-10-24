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
| `lookup(word, scope)` | the key `word` names, or `None` when it names nothing; or it [says why](#saying-why) |
| `suggest(word, scope)` | the names close to `word`, the closest first, for a did-you-mean |
| `options(scope)` | every name it may be, for completion |

How a word matches (case, keys as well as names, spaces) is the resolver's to say. parsed passes the word as the
line gives it, its quotes left off, and keeps the key it returns.

## Saying why

A resolver often knows more than parsed of why a word names nothing: where to look, or every name there is. Its
`lookup` may raise a `ValueError` whose message is the reason, and parsed refuses the word with it, as it refuses a
word its kind can't read:

```python
class Blueprints:
    def lookup(self, word, scope):
        found = self.held(scope).get(word.lower())
        if found is None:
            raise ValueError(f'no blueprint {word!r} here: inquire blueprints, docked')
        return found
```

```
fleet f1 acquire <blueprint>: no blueprint 'shield-9' here: inquire blueprints, docked `fleet <fleet> acquire <blueprint>`
```

The refusal has the command's usage as its hint and no suggestions, since the reason says what's near. A resolver
that gives `None` is refused as before (`no blueprint 'shield-9'`, with its `suggest`), so one that never raises
reads as it did. A `PairsResolver`'s `lookup`, and the resolver its `values` gives, may say why alike. Completion
and rendering take a reason as a word that names nothing.

## Scopes

`Name('station', scope='fleet')` narrows a station by the command's `fleet` field. The resolver is given the scope
as the fleet field's value once it's read, as a string: its key, when the fleet is itself a name with a resolver.

- **A scope is read first,** whatever its place on the line: `board ceres --fleet Hauler` reads the fleet, then the
  station within its reach.
- **A scope the line leaves out** is `None`, and so is a name with no scope: the lookup is across every name of the
  category.
- **A command whose scopes go round** (a station scoped by a berth that's scoped by the station) is refused when
  it's declared, since neither could be read first.

## A chain's place

A name whose scope follows its chain (`Name('station', scope='fleet', follows=True)`) is looked for where the fleet
will be. A chain's steps may move it on ([`MOVES`](command.md#a-chains-place)), and a later step's name is given the
place as its scope:

| The line | `dock`'s station looked for with the scope |
|---|---|
| `fleet Prospector dock vesta` | `'f1'`, the fleet's key, as any scope |
| `fleet Prospector mine then dock vesta` | `'f1'`: mining moves nothing |
| `fleet Prospector jump sol then dock ceres` | `'sol'`, where the jump took it |
| `fleet Prospector move "Vruba Rings" then dock vesta` | `'vruba-rings'`, the site's key |
| `fleet Prospector jump nearest iron then dock ceres` | `None`: somewhere the line doesn't say, so every station |

So a resolver given a scope that follows a chain is given a fleet's key or a place's (a system's, a site's), and
tells them apart as it tells its keys apart: a site's system is the resolver's to know. A word no name answers to
there says where it was looked: `no station 'vesta' for fleet 'Prospector', once at 'sol'`.

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
--into: no fleet 'Haulr'; did you mean Hauler? `fleets merge <fleet> --into <fleet> [--quiet] [--yes]`
fleet Hauler dock <station>: no station 'vesta' for fleet 'Hauler' `fleet <fleet> dock [<station>]`
```

A name is refused by its [term](kinds.md#name), its label or else its category:
`Name('good_in_deposit', label='ore')` says `no ore 'lab'`. A slot by an alias reads by its own category, so a
polymorphic twin's word is refused as that category's: `detachment <detachment>: no detachment 'Prospector'`. A
pair's key is refused by its category's term (`no variable 'hme' for routine 'mining'`), and its value by its key
(`no home 'mars'`). A resolver that [says why](#saying-why) is refused with its reason instead.

A [literal word](kinds.md#literal-words) comes before the resolver: `Name('station', words={'here': None})` reads
`here` as `None`, and only `"here"`, quoted, is looked up.
