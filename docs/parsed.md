# `parsed/__init__.py`: the package root

`import parsed` gives parsed's own names, and seared's declaration surface, re-exported as zeared re-exports it,
so a module that declares commands needs no other import.

**parsed's own:**

| Group | Names |
|---|---|
| Commands | `Command` ([`command.md`](command.md)), `Effect` and `effect_of` ([`effect.md`](effect.md)) |
| The app | `App` ([`app.md`](app.md)), a program's trees mounted under prefixes, with their handlers and names; `Context` ([`context.md`](context.md)), what a handler is given beside its command; `Result` ([`reply.md`](reply.md)), what running a line comes to; `Ask`, a handler's question, asked before it acts |
| Kinds | `Kind` and `Name` ([`kinds.md`](kinds.md)); the default kinds stay `parsed.kinds.*` |
| Names | `Resolver` ([`names.md`](names.md)), what an app gives for a category of its names |
| The tree | `Tree` ([`tree.md`](tree.md)) |
| Errors | `ParsedError`, `DeclarationError`, `ReadError`, `RenderError`, `TimedOutError` ([`errors.md`](errors.md)) |
| Version | `__version__` |

**seared's:**

| Group | Names |
|---|---|
| The model | `Parsed` (seared's `Seared`), `parsed` (seared's `seared` decorator) |
| Fields | `Bool`, `Bytes`, `Date`, `DateTime`, `Decimal`, `Dict`, `Enum`, `Float`, `Int`, `Path`, `Str`, `T`, `Time`, `TimeDelta`, `Tuple`, `Union`, `UUID`, and the optional `NDArray`, `PandasFrame`, `PolarsFrame` (each needs seared's extra only when used) |
| Errors | `SearedError`, `ValidationError` |

Each is seared's own object, not a copy: `parsed.Str is seared.Str`, and `parsed.Parsed is seared.Seared`. The
rest of seared's surface (`Field`, `FieldKind`, `FieldSpec`, `unknown_keys`, `accel_status`, `document`,
`introspect`) stays reachable as `seared.*`.

```python
import parsed


@parsed.parsed
class Mined(parsed.Parsed):
    fleet: str = parsed.Str(required=True, doc='the fleet that mined')
    tonnes: float = parsed.Float(ge=0, default=0.0, doc='what it brought up')
```

**Import it unaliased** (`import parsed`, not `import parsed as p`) in a module that declares, so a field can take
any name without shadowing the module, as the family's message modules do with `import zeared`.

**`python -m parsed` is parsed's own command line** (`__main__.py`): `check <target> …` checks a package's commands
in its CI ([`doc/check.md`](doc/check.md)).

## See also

- [seared's own docs](https://github.com/bwiswell/seared), for every field type and its options.
- [`overview/architecture.md`](overview/architecture.md): how parsed sits in the family.
