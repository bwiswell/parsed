# `doc/generate.py`: a package's command reference

parsed reuses seared's doc pipeline whole, as `zeared.doc` does: its discovery (every seared class a package holds,
and those they reference), its paths (a page a class, mirroring the package's modules), its links, its index and
its `--check`. Only the page differs: a command gets its reference page ([`render.md`](render.md)), and any other
seared class (a `REPLY`, a request class a command inherits, a base's fields) seared's own.

- `build_docs(target)` is every page for a module or package by name, by its path:
  `{'FleetMine.md': …, 'FleetView.md': …, 'index.md': …}`. It writes nothing.
- `document(cls)` is one class's page, and `render_one(cls, link_for)` the same with the doc set's links.

## `python -m parsed.doc`

```
python -m parsed.doc farm.commands -o docs/commands
python -m parsed.doc farm.commands -o docs/commands --check
```

It writes the pages under `-o` (`docs` by default), each only where it changed. `--check` writes nothing and exits
1 when a page is missing or stale, for an app's CI. `--require-docs` exits 1 first when a field has no `doc=`,
naming each one. They're seared's options, as `python -m seared.doc` takes them. `main(argv=None)` runs it and
gives its exit code, for a script of an app's own.
