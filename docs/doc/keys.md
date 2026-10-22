# `doc/keys.py`: a command's key, for policy

`command_key(command, names=None)` gives the key an instance is said by: its phrase's words and its slots' values,
joined by `/`, as a message's topic is. So a tool's rules match commands as they match topics, with the same
patterns (`fleet/*/mine`, `fleet/*/dock/**`).

```python
command_key(FleetDock(fleet='f1', station='vesta'))          # 'fleet/f1/dock/vesta'
command_key(FleetMine(fleet='d2'), names=names)               # 'detachment/d2/mine'
```

**The phrase** is the one `Tree.render` would say the instance with: with names, the twin its values belong to.
**Each value** is written as a line writes it: a name's key, a number's digits, a span of time as `1h30m`.

**Left out**, as a request's body rather than its address:

- a slot of several words (`fleet/f1/sell`, whatever is sold);
- the rest of the line (`say`);
- an optional slot at its default (`fleet/f1/dock`);
- the flags.

**A key's safety is its reader's.** A value holding `/`, `*`, `$`, `?` or `#` makes a key no pattern can hold.
parsed writes it as it is, and the tool reading it refuses it, naming the kind whose resolver should map the value
to a key. An instance no phrase can say raises a `RenderError`, as `render` does; a value that isn't a command's,
a `TypeError`.

**Templates:** a `CommandDoc`'s `keys` are each phrase's key with a `{slot}` where each one-word slot stands:
`fleet/{fleet}/dock/{station}`, `detachment/{detachment}/mine`. An optional slot is in its template, and out of an
instance's key while it holds its default.
