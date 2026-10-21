# `parsed/__init__.py`: the package root

`import parsed` gives seared's declaration surface, re-exported as zeared re-exports it, so a module that declares
commands needs no other import:

| Group | Names |
|---|---|
| The model | `Parsed` (seared's `Seared`), `parsed` (seared's `seared` decorator) |
| Fields | `Bool`, `Bytes`, `Date`, `DateTime`, `Decimal`, `Dict`, `Enum`, `Float`, `Int`, `Path`, `Str`, `T`, `Time`, `TimeDelta`, `Tuple`, `Union`, `UUID`, and the optional `NDArray`, `PandasFrame`, `PolarsFrame` (each needs seared's extra only when used) |
| Errors | `SearedError`, `ValidationError` |
| Version | `__version__` |

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

## See also

- [seared's own docs](https://github.com/bwiswell/seared), for every field type and its options.
- [`overview/architecture.md`](overview/architecture.md): how parsed sits in the family.
