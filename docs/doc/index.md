# `parsed.doc`: commands as data

For the tools that read commands (the family's [tooled](https://github.com/bwiswell/tooled), for agents), in the
shape of `zeared.doc` wherever the meaning matches, so a tool reads a command as it reads a message:

- [`introspect.py`](introspect.md): `is_command_class(obj)`, and `introspect_command(cls)`, a `CommandDoc`;
- [`json_schema.py`](json_schema.md): `json_schema(cls)`, a command's arguments as a closed JSON Schema;
- [`keys.py`](keys.md): `command_key(command)`, an instance's key for policy, slashed as a topic is, and
  `chain_keys(steps)`, each of a chain's steps';
- [`chains.py`](chains.md): a chain as one tool call: `introspect_chain(tree, base)`, a `ChainDoc`;
  `chain_schema(tree, base)`, its arguments' schema; `load_chain` and `dump_chain`, its arguments to its steps and
  back;
- [`check.py`](check.md): `check(targets)`, and `python -m parsed check`, a package's commands checked in its CI;
- [`render.py`](render.md): `render_command(cls)`, a command's reference page in Markdown;
- [`generate.py`](generate.md): `document(cls)` and `build_docs(target)`, a package's reference pages over seared's
  pipeline, and `python -m parsed.doc`, which writes or checks them.

```python
import parsed.doc

parsed.doc.introspect_command(FleetDock).slots      # each slot, its field and its kind
parsed.doc.json_schema(FleetDock)['x-phrase']       # 'fleet {fleet} dock {station}'
```

`import parsed` doesn't import it. Discovery is seared's: `seared.doc.collect(target)` gives a package's seared
classes, and `is_command_class` keeps the commands among them.
