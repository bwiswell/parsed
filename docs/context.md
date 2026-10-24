# `context.py`: what a handler is given beside its command

A handler is `handler(command, ctx)`. `ctx` is a `parsed.Context`, made fresh for each line a
[session](app.md#sessions) calls, with nothing global behind it: two apps, or two sessions of one, never share one.

```python
async def mine(command: FleetMine, ctx: parsed.Context[Controls]) -> str:
    fleet = ctx.state.mirror.fleets[command.fleet]
    if ctx.phrase.startswith('detachment'):
        ...                                    # said of a detachment, by the twin's wording
    if ctx.dry_run:
        return f'{fleet.name} would mine'
    ...
```

| Attribute | Holds |
|---|---|
| `state` | the app's state, as the session opened it: typed by the app, `Context[Controls]` |
| `session`, `app` | the session that called the line (`ctx.session.use(…)` sets its subjects: [`app.md`](app.md#subjects)), and its app |
| `mount` | the mount the line went to |
| `params` | the mount's parameters: what the app gave it when it mounted it (a service's settings) |
| `names` | the resolvers the line was read with, by category: the app's, and the mount's over them |
| `line` | the line called, as read: a subject's words before it, where one was tried |
| `reading` | what the line was read to ([`Reading`](_walk/_walker.md#reading)): each field's words and value, parsed's own flags, and a chain's `steps` |
| `phrase` | the phrase that said the line, as its command declares it, without its mount's prefix: `'detachment {detachment} mine'`, so a handler tells a twin's wording from its command's |
| `dry_run` | whether the line gave `--dry-run`: what the command would do, done by nothing |
| `verbosity` | how much to say, as the session was opened with: `0` by default, more for more |
| `terminal` | whether a person is at a terminal, as the session was opened with: `False` by default, so a viewer gives text where it would draw ([`app.md`](app.md#a-person-at-a-terminal)) |

`state` is the session's while it's open. A context kept past its session's close refuses it with a
`RuntimeError`, as the session does, since the state has been left by then.
