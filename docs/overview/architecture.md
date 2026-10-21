# Architecture

parsed is a library of the `*eared` family: general-purpose, and domain-agnostic.

## Where it sits

```
seared  <-  parsed
seared  <-  zeared
```

- **parsed depends on seared alone.** A command is a seared class, so seared does its typing, its validation and
  its JSON Schema. parsed never imports zeared: a command line needs no mesh.
- **A sibling of zeared, not built on it.** An app may use both: zeared for the messages between its nodes, parsed
  for the commands its users type.
- **Declared to be read by tools.** An app declares its commands in a module of their own, which imports only
  parsed, so tooling (the family's [tooled](https://github.com/bwiswell/tooled), for agents) can read them
  without the app's runtime.

## What 0.1.0 holds

Only the package root ([`../parsed.md`](../parsed.md)): seared's declaration surface, re-exported. The commands,
the tree that reads a line, and the docs a command describes itself with arrive in the 0.1.x releases that follow,
each adding its part here.
