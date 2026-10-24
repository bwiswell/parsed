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
    result = await session.run('fleet f1 mine')              # mine(FleetMine(fleet='f1'), ctx)
    result.text, result.code                                 # 'f1 mines', 0

app.run('relay run', settings)                               # one line, in a session of its own
sys.exit(app.main())                                         # the program's arguments, as its command line
```

## Mounting

`app.mount(target, under='', params=None, doc=None)` mounts a tree, or a module or package of commands by name
(collected as [`Tree.collect`](tree.md) collects them), and returns its `Mount`:

- **`under`** is the prefix its lines begin with: `'relay'`, or several words, `'rio relay'`. None mounts it at the
  root. A tree with a prefix of its own keeps it, beneath `under`.
- **`params`** is what its handlers are given beside the command: a service's settings, say. It's the mount's, so
  one package can be mounted several times, each with its own prefix and its own settings: one group serves many
  apps, or one app twice.
- **`doc`** is what it's for, as help says it on its namespace's line ([sessions](#sessions)): by default its
  module's docstring, the package's named, or a tree's first command's module's.

A `Mount` has its `app`, its `tree` (under its prefix), its `under`, its `params`, its `doc` (and its `summary`,
the first line) and its `source`: the module or package named, or a tree's first command's module. Its `label`
(`service.cli under 'relay'`) is how a refusal names it, and `holds(cls)` says whether a command is one of its own.
`app.mounts` lists them, in the order they were made.

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
| `app.walk(line, subjects=(), placeholders=False)` | a `Routed`: its `mount`, its `reading` ([`Reading`](_walk/_walker.md#reading)), its `command` class, and `load()` |
| `app.read(line, subjects=())` | the command, loaded |
| `app.complete(text, subjects=())` | what may come next on a line being typed: its mount's tree's offers, or, short of a mount, the words that may follow |
| `app.subject_of(line, subjects)` | the subject a line reads under, or `None` where it's read as typed ([subjects](#subjects)) |
| `app.render(command, mount=None)` | the line that says an instance, by its mount's tree, prefix and all; or a chain's steps, in its first step's mount |

A line that reaches no mount is refused as a tree refuses one: `no command 'rela'; did you mean relay?`, or
`relay: then what? run | validate-config | status`. parsed's own flags (`--yes`, `--json`, …) may stand among the
words that route a line; a command's own flags follow them, since only its mount's tree knows whether one takes a
value.

**`render` needs the mount** where its command is mounted more than once (`mount=gateway`), and refuses a command
mounted nowhere, or not in the mount given, with a `RenderError`.

## Handlers

A handler is called as `handler(command, ctx)`, `ctx` a [`Context`](context.md), and awaited if it's async. It
returns its command's `REPLY`, text, or nothing ([`reply.md`](reply.md)).
`app.on(Cls, handler)` binds the handler a command runs with, in every mount that holds it. `mount.on(Cls, handler)`
binds one for that mount alone, which wins there, so a group mounted twice can run differently in each.

**A handler is a callable, or the path to one,** `'pkg.module:function'` (a dotted name after the colon reaches an
attribute: `'pkg.module:Service.run'`). A path is imported the first time its handler is looked up, and kept, so an
app that gathers several packages imports none of their runtimes to read a line or show help.

`mount.handler(Cls)` is the handler `Cls` runs with in that mount: its own, else the app's, else `None`.
`app.handler(Cls)` is the app's own. Looking up a path that doesn't import, or names nothing in its module, raises
an `ImportError` naming the command and the path; one that names something that isn't callable, a `TypeError`.

## Chains

`app.on_chain(Base, handler)` binds what a chain's steps run with, in every mount that holds them; `mount.on_chain`
binds one for that mount alone. It's called as `handler(steps, ctx)`, `steps` each step's instance, in order:

```python
app.on_chain(FleetCommand, orders)       # orders([FleetJump(…), FleetMove(…), FleetMine(…)], ctx)
```

- **A chain of two steps or more** runs by its chain's handler.
- **A lone step** runs by its own handler, if it has one (`app.on(FleetMine, …)`), else by its chain's, as a chain
  of one: so a step needs no handler of its own.
- **The chain's base stands for it:** hooks that name the base (`app.before(hook, FleetCommand)`) run for its
  chains, given the steps, and its reply is checked against the base's `REPLY`. A result's `command` is the chain's
  phrase (`fleet {fleet} jump {system} then move {to} then mine`).
- **Every step is loaded before any runs,** so a value one step's field refuses refuses the line, exit 4.

`app.chain_handler(Base)` and `mount.chain_handler(Base)` look one up. A chain with no handler is a `LookupError`,
as a command with none is.

## Hooks

Hooks run around each command's handler, for what every command shares: an audit line, a timer, a check:

```python
app.before(audit)                          # every command: audit(command, ctx)
app.before(check_funds, FleetBuyShip)      # that command alone
app.after(log_line)                        # log_line(command, ctx, found)
app.on_error(report)                       # report(command, ctx, error)
```

| Stage | Called as | Runs |
|---|---|---|
| `before` | `hook(command, ctx)` | before the handler; one that raises stops the line, its handler not run |
| `after` | `hook(command, ctx, found)` | after it, `found` what it came to: its reply, text, nothing, or the question it stopped at |
| `on_error` | `hook(command, ctx, error)` | when a before hook, the handler, a question's answer or an after hook raises; the error goes on after |

**The order is stated:** before hooks run the app's, then the command's; after and on-error hooks the command's,
then the app's. Each scope's run in the order they were added, and `app.hooks(Cls)` lists them so. A hook may be
async, and is awaited. Every hook of a line is given the context its handler is (the same object), so a hook sees a
dry run as the handler does.

No hook runs for a line that doesn't read, a line that gives `--help`, a command for a person at a terminal run
with none, or a command with no handler: none of them reaches a handler. Hooks are the app's; a mount's own come
later.

## Sessions

`app.open(state=None, verbosity=0, answer=None, interval=1.0, subjects=(), terminal=False, options=None)` gives a
`Session`, used once, as `async with app.open(state) as session`:

- **`state`** is the app's own (a link, a mirror), given to handlers as `ctx.state`. A context manager, sync or
  async, is entered when the session opens, and handlers see what entering it gave, as `async with x as y` does;
  it's left when the session closes, told of any error the session's body raised. Anything else is kept as it is.
- **`verbosity`** is how much handlers should say (`ctx.verbosity`): `0` by default, more for more.
- **`answer`** answers a question a line asks, when `--yes` doesn't: yes or no from the question, sync or async.
  `parsed.reply.terminal` prompts a person (`Buy a hauler for 1,200 credits? [y/N]`). With none, a question is
  left unanswered.
- **`interval`** is how often, in seconds, a wait reads again when nothing says the state moved: a second by
  default; `None` for an app that calls `session.changed()` on every change, so a wait reads only then.
- **`subjects`** are the words tried before a bare line, in turn ([subjects](#subjects)): none by default.
- **`terminal`** is whether a person is at a terminal (`ctx.terminal`): `False` by default, and anything but
  `True` or `False` is a `TypeError`. Without one, a command for a person is refused
  ([a person at a terminal](#a-person-at-a-terminal)).
- **`options`** are the program's root options (`ctx.options`), an instance of the app's options class
  ([the command line](#the-command-line)): by default, each field's default, or `None` for an app with none. An
  instance of another class, or any for an app with no options class, is a `TypeError`.

`await session.run(line)` runs the command a line says: the line goes to its mount and is loaded there, then its
handler (the mount's, else the app's) is called with a fresh context and awaited if it's async. It gives what came
of it as a [`Result`](reply.md), the envelope every parsed app answers with: its reply or text, whether it went
well, whether it was done, and any error, with its exit code. Nothing the line or its handler does is raised.

`await session.call(line)` runs it the same way and gives what the handler returned, letting every error through: a
`ReadError` for a line that doesn't read, a `RefusedError` for a command for a person at a terminal run with none,
a `LookupError` for a command with no handler, a `TypeError` for a handler that returned something besides its
`REPLY`, text, nothing or an `Ask`, and whatever the handler raises.

**A handler asks first** by returning `parsed.Ask(question, then)`, having done nothing yet
([`reply.md`](reply.md#asking-first)). Each question is answered yes by `--yes` on the line, or `yes=True` given to
`run` or `call`; else by the session's `answer`. A yes runs `then`, which may ask again. A question left unanswered,
or answered no, leaves the line undone: `run` gives a result with the question as its `asks`, exit code `0`, and
`call` gives back the `Ask` itself.

**A line that waits** (`--until`, on a read with a `REPLY`: [`wait.md`](wait.md#waiting)) reads again until its
reply meets every condition, or its bound passes: at once when `session.changed()` says the app's state moved, else
every `interval`. Met, the result is the reply with `met` true, exit 0; past the bound, the last reply with `met`
false and a `timeout` error, exit 7 ([`wait.md`](wait.md#how-it-ends)), and `call` raises `parsed.TimedOutError`.
`waited` says how long it waited. Its handler returns its `REPLY`, since a wait reads it, and hooks run once around
the whole wait.

**`session.watch(line)`** gives a result each time a watching line's reply changes (`--watch`:
[`wait.md`](wait.md#watching)), until its count, its bound, its conditions or a cancel; each one's `to_json()` is a
line of a stream. Any other line gives its one result there, and `session.run` gives a watch's last.

**`session.changed()`** says the app's state moved, from any thread: wire it where the app learns of a change
(`controls.on_change = session.changed`). Every wait on the session reads again at once; a change while a read is
under way isn't missed.

**A line that gives `--help` runs nothing,** at any depth. It's answered as `run`'s text and `call`'s result:

- **where it says a command,** with the command's help ([`help.md`](help.md#a-commands-help)), by the phrase the
  line said: its usage, its docstring, a row for each argument, its other phrases, its examples and what it asks of
  the line. Its values aren't loaded.
- **short of one,** with what it may still say ([`help.md`](help.md#a-listing)), one entry a line, each with its
  summary in a column, in the order they're mounted and declared:
  - **a mount whose prefix the line hasn't said yet** as its namespace's line, its prefix and its `doc`'s summary:
    `relay …  A service's skeleton group.` A bare `--help` gives the root's commands, then each namespace's line;
  - **any other** by each command beneath where the line's words go: a mount's for its prefix (`relay --help`), a
    phrase's for its words so far (`fleet f1 jump --help`).

  Where one command alone is beneath, short of a slot it needs (`wait --help`, before its operation), the answer is
  that command's help. The result has no `command`, and exits 0. A word that goes nowhere (`rela --help`) is still
  refused.
- **An `INTERACTIVE` command is left out of a listing** when no one is at a terminal
  ([a person at a terminal](#a-person-at-a-terminal)), or the line gives `--json`, as a tool would: it's not theirs
  to run. Where that leaves nothing (`ship s1 --help`), each one's refusal is the answer, naming its `INSTEAD`. Its
  own help, asked by its whole line, is answered whoever asks.

parsed's own flags (`--help` or `-h`, `--json`, `--yes`, `--dry-run`) may stand anywhere on a line, the first word's
place among them: `--yes fleet f1 buy ship hauler`.

**`app.run(line, state=None, …)`** runs one line in a session of its own, opened around it and closed after, and
gives its `Result`: for a program that runs one line and exits. It takes `yes=False`, as `run` does, and the rest as
`app.open` does. It runs an event loop of its own, so it's refused inside one with a `RuntimeError`; there,
open a session.

`session.state` is the state, `session.is_open` whether it's open, and `session.context(routed)` the context a
line's handler would be given. Outside `async with`, before it or after, each is refused with a `RuntimeError`, as
is opening a session twice. An error the session's body raises goes on past it, whatever the state makes of it.
`session.subjects` are its subjects, and `session.complete(text)` what may come next on a line being typed, with
them; neither needs it open.

## A person at a terminal

Whether a person is at a terminal is the front end's to say, as the session opens: `app.open(state, terminal=True)`,
or `app.run(line, terminal=True)`. It's `False` by default, so a program that runs lines in-process, as an agent's
tooling does, needn't say so. `session.terminal` holds it. `app.main` says it from stdin and stdout
([the command line](#the-command-line)).

- **A handler reads it** as `ctx.terminal`, so a viewer gives text where it would draw.
- **Without one, a command for a person is refused** (`INTERACTIVE = True`: [`command.md`](command.md)). It's
  refused once the line reads, before its values are loaded or any hook runs, so nothing is done and no value is
  checked for a command that can't run.
  - `run` gives a `refused` error, exit 3 ([`reply.md`](reply.md#errors-and-exit-codes)), naming what's said in its
    place where the command declares that (`INSTEAD`); `call` raises `parsed.RefusedError`.
  - `--help` is still answered. A dry run is refused too, since its handler would run.
  - A chain is refused where any of its steps is for a person.

```
ship {ship} fit is for a person at a terminal: say `ships make <ship> add <part>` instead
```

What's said in its place is said as the mount the line went to says it, else as the first mount that holds it does,
else by its phrase alone. The error's `instead` is that phrase after its mount's prefix,
`'ships make {ship} add {part}'`, as a result's `command` is.

Nothing is inferred from it: a terminal doesn't make `parsed.reply.terminal` the session's `answer`. A front end at
one gives both, as `app.main` does.

## The command line

`app.main(argv=None, state=None, verbosity=0, interval=1.0, subjects=())` runs a program's arguments as its command
line and gives its exit code, so a program's entry point is one line:

```python
app = parsed.App('relayctl', options=Options, version='1.2.3')
app.mount('relay.cli')


def main() -> None:
    sys.exit(app.main())                                     # relayctl -c relay.toml run
```

- **The arguments** (`sys.argv[1:]` by default) are the root options, then a line ([`argv.md`](argv.md)). After
  the first word, every flag is the line's, and a single argument is the whole line:
  `relayctl "run --config own.toml"`.
- **Root options** are the fields of `App(prog, options=Options)`, a seared class whose fields are each optional:
  read once and given to handlers as `ctx.options`. `App(prog, version='1.2.3')` gives `--version`, which exits 0.
- **parsed's own flags** given among the root options are the line's, put first on it: `relayctl --json status`
  runs `--json status`. A bare `--help` writes the program's own help (its usage, then a row for each root option
  and `--version`) above the root's listing.
- **A person is at a terminal** when stdin and stdout both are one. There, a line's `INTERACTIVE` command runs and
  a question a line asks is put to them (`parsed.reply.terminal`); elsewhere, under a pipe or a tool, the command is
  refused and the question left unanswered.
- **What it writes:** each result's text as it comes, a watch's at each change: to stdout when it went well, else to
  stderr. With `--json` anywhere on the line, or before it, each result's envelope instead
  ([`reply.md`](reply.md#as-json)), a line of JSON on stdout, a refusal's too, so a tool reads one stream. Its exit
  code is the last result's ([`reply.md`](reply.md#errors-and-exit-codes)), or 130 when it's interrupted (Ctrl-C).

It runs an event loop of its own, as `app.run` does, so it's refused inside one with a `RuntimeError`.

## Subjects

A subject is the words a session tries before a bare line: with `fleet prospector`, `mine` reads as
`fleet prospector mine`, as a player who has said `use prospector` goes on:

```python
async with app.open(controls, subjects=('fleet prospector',)) as session:
    await session.run('mine')                  # FleetMine(fleet='f1'), read as 'fleet prospector mine'
    await session.run('fleet hauler mine')     # as typed
    session.use('detachment scouts')           # in place of the subjects it had
```

- **The line as typed first.** Only where its first word begins no command (no mount's prefix, nor a command's
  first word at the root) is each subject tried, in turn, and the first whose words go on into that word reads the
  line: `log 5` stays `log 5`, and `fit`, with subjects `ship s1` and `fleet prospector`, reads under the ship.
- **Its refusals are the line's as read:** `mine --for soon` is refused as `fleet prospector mine --for soon` is,
  at its column there. A line no subject goes on into is read as typed, and refused so (`no command 'mien'`).
- **A result's `line` is the line as read** ([`reply.md`](reply.md)), and so is `ctx.line`: an agent that said
  `mine` sees what it was read as.
- **They stay out of schemas and keys:** a bare line reads to the instance the whole line does, and its key is that
  instance's.
- **Chains, `--help` and waits** read as the whole line would: `jump sol then mine` is the fleet's chain.

`session.use(*subjects)` makes them the session's, in place of those it had; none, for none. A handler says it as
`ctx.session.use(f'fleet {command.fleet}')`, so a `use` command of the app's sets the subject for the lines after
it. `app.walk`, `app.read` and `app.complete` take `subjects=` too, for a front end that holds its own.

**Completing** a line's first word offers the commands' first words, then each subject's next words (`mine`, `dock`,
…); after it, a line whose first word begins no command is completed under the subject that would read it.

**A subject is words a command begins with:** a string, no flags among its words, that goes along a mount's prefix
or into its commands (`relay`, `fleet prospector`, `ship s1`). Anything else is refused with a `ValueError`, when
the session is opened or `use` is called:
`subject 'flet prospector': no command of farlandia begins with its words`. Several subjects are a sequence
(`('fleet prospector',)`, not the string).

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
| `before`, `after` or `on_error` of a hook that isn't callable, or for a class that isn't a command or a chain's base | |
| `on_chain` of a class that isn't a chain's base; `mount.on_chain` of a chain none of whose steps it holds | |
| `mount.on` of a command the mount doesn't hold | bind it on the app, or on the mount that has it |
| a second handler for a command, or a second resolver for a category, on the app or on one mount | bind each once |
| `names` of a category that isn't a name, or a resolver without `lookup`, `suggest` and `options` | |
| `App(prog, options=…)` of root options it can't read, or a `version` that isn't a string | each named in [`argv.md`](argv.md#root-options) |

A module named that doesn't import raises its `ImportError`.
