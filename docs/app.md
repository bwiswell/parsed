# `app.py`: a program's trees, mounted, with their handlers and names, and the sessions that run them

`parsed.App(prog)` holds a program's commands, each tree of them mounted under a prefix of words. It binds the
handler each command runs with, and the resolvers its lines are read with; a session runs lines against the app's
state:

```python
import parsed

app = parsed.App('farlandia')
app.names('fleet', Fleets())

app.mount('farm.commands')                                   # at the root: `fleet f1 mine`
relay = app.mount('service.cli', under='relay', params=RelaySettings())
gateway = app.mount('service.cli', under='gateway', params=GatewaySettings())

app.on(FleetMine, mine)                                      # in every mount that holds it
app.on(Run, 'service.runtime:run')                           # imported when it's first looked up
gateway.on(Run, 'gateway.runtime:run')                       # this mount's own, which wins here

app.read('relay run --config relay.toml')                    # Run(config=PosixPath('relay.toml'))

async with app.open(Link(galaxy)) as session:                # the link is opened, and closed after
    await session.call('fleet f1 mine')                      # mine(FleetMine(fleet='f1'), ctx)
```

## Mounting

`app.mount(target, under='', params=None)` mounts a tree, or a module or package of commands by name (collected as
[`Tree.collect`](tree.md) collects them), and returns its `Mount`:

- **`under`** is the prefix its lines begin with: `'relay'`, or several words, `'rio relay'`. None mounts it at the
  root. A tree with a prefix of its own keeps it, beneath `under`.
- **`params`** is what its handlers are given beside the command: a service's settings, say. It's the mount's, so
  one package can be mounted several times, each with its own prefix and its own settings: one group serves many
  apps, or one app twice.

A `Mount` has its `app`, its `tree` (under its prefix), its `under`, its `params` and its `source`: the module or
package named, or a tree's first command's module. Its `label` (`service.cli under 'relay'`) is how a refusal names
it, and `holds(cls)` says whether a command is one of its own. `app.mounts` lists them, in the order they were made.

**A mount that would make a line read two ways is refused** with a `DeclarationError` naming both mounts and the
words they share ([`_walk/_route.md`](_walk/_route.md)):

```
service.cli under 'relay' and service.cli under 'relay' both say 'relay run': a line would read two ways
logs is mounted where farm.commands at the root says 'fleet': a line would read two ways
```

Two mounts may share a prefix, the root among them, as long as no word begins a command in both.

## Reading a line

A line goes to its mount by its first words, then the mount's tree reads the whole line, with the mount's names:

| Call | Gives |
|---|---|
| `app.walk(line, placeholders=False)` | a `Routed`: its `mount`, its `reading` ([`Reading`](_walk/_walker.md#reading)), its `command` class, and `load()` |
| `app.read(line)` | the command, loaded |
| `app.complete(text)` | what may come next on a line being typed: its mount's tree's offers, or, short of a mount, the words that may follow |
| `app.render(command, mount=None)` | the line that says an instance, by its mount's tree, prefix and all |

A line that reaches no mount is refused as a tree refuses one: `no command 'rela'; did you mean relay?`, or
`relay: then what? run | validate-config | status`. parsed's own flags (`--yes`, `--json`, …) may stand among the
words that route a line; a command's own flags follow them, since only its mount's tree knows whether one takes a
value.

**`render` needs the mount** where its command is mounted more than once (`mount=gateway`), and refuses a command
mounted nowhere, or not in the mount given, with a `RenderError`.

## Handlers

A handler is called as `handler(command, ctx)`, `ctx` a [`Context`](context.md), and awaited if it's async.
`app.on(Cls, handler)` binds the handler a command runs with, in every mount that holds it. `mount.on(Cls, handler)`
binds one for that mount alone, which wins there, so a group mounted twice can run differently in each.

**A handler is a callable, or the path to one,** `'pkg.module:function'` (a dotted name after the colon reaches an
attribute: `'pkg.module:Service.run'`). A path is imported the first time its handler is looked up, and kept, so an
app that gathers several packages imports none of their runtimes to read a line or show help.

`mount.handler(Cls)` is the handler `Cls` runs with in that mount: its own, else the app's, else `None`.
`app.handler(Cls)` is the app's own. Looking up a path that doesn't import, or names nothing in its module, raises
an `ImportError` naming the command and the path; one that names something that isn't callable, a `TypeError`.

## Sessions

`app.open(state=None, verbosity=0)` gives a `Session`, used once, as `async with app.open(state) as session`:

- **`state`** is the app's own (a link, a mirror), given to handlers as `ctx.state`. A context manager, sync or
  async, is entered when the session opens, and handlers see what entering it gave, as `async with x as y` does;
  it's left when the session closes, told of any error the session's body raised. Anything else is kept as it is.
- **`verbosity`** is how much handlers should say (`ctx.verbosity`): `0` by default, more for more.

`await session.call(line)` runs the command a line says: the line goes to its mount and is loaded there, then its
handler (the mount's, else the app's) is called with a fresh context and awaited if it's async. It gives what the
handler returns. It raises a `ReadError` for a line that doesn't read, a `LookupError` for a command with no
handler, and whatever the handler raises.

`session.state` is the state, `session.is_open` whether it's open, and `session.context(routed)` the context a
line's handler would be given. Outside `async with`, before it or after, each is refused with a `RuntimeError`, as
is opening a session twice.

## Names

`app.names(category, resolver)` gives the resolver a category's names are read by ([`names.md`](names.md)), in every
mount; `mount.names(category, resolver)` gives one for that mount alone, which wins there. `app.resolvers` and
`mount.resolvers` are read-only views: the app's, and the mount's merged over them. Resolvers given after mounting
count, as each line is read with them as they stand.

## What it refuses

Each is a `DeclarationError`, made when the app is put together:

| Refused | Because |
|---|---|
| `App('')`, or a `prog` that isn't a string | it's the program's name, as it's typed |
| a target that isn't a tree or a module's name; a tree with no commands | |
| an `under` that isn't words (`'Relay'`, `'relay {x}'`) | a prefix is words, as a phrase's are |
| a mount that would make a line read two ways | it names both mounts and the words they share |
| `on` of a class that isn't a command, or a handler that isn't a callable or a path (`'pkg.module:function'`) | |
| `mount.on` of a command the mount doesn't hold | bind it on the app, or on the mount that has it |
| a second handler for a command, or a second resolver for a category, on the app or on one mount | bind each once |
| `names` of a category that isn't a name, or a resolver without `lookup`, `suggest` and `options` | |

A module named that doesn't import raises its `ImportError`.
