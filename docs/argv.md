# `argv.py`: a program's arguments, its root options first, then a line

`app.main(argv)` runs a program's arguments as its command line ([`app.md`](app.md#the-command-line)); this module
reads them. The shell's tokens are the words: `prog <words…>`, as a line says them.

```
relayctl -c relay.toml run --config own.toml
         └─ root ────┘ └─ the line ────────┘
```

## Root options

Root options stand before the first word: the flags of the app's options class, a seared class given as
`App(prog, options=Options)`, read once and handed to handlers as `ctx.options` ([`context.md`](context.md)).

```python
@parsed.parsed
class Options(parsed.Parsed):
    SHORTS: ClassVar[dict[str, str]] = {'config': 'c'}

    config: Path | None = parsed.Path(default=None, doc='the config file')
    quiet: bool = parsed.Bool(default=False)


app = parsed.App('relayctl', options=Options, version='1.2.3')
```

- **Each field is a flag,** read as a command's flag is ([`tree.md`](tree.md)): its wire name with `_` written `-`,
  a `Bool` a switch (`--no-…` when it defaults to `True`), any other the word after it or after `=`, read by its
  kind ([`kinds.md`](kinds.md)). Its `KINDS` and `SHORTS` are merged along the MRO, as a command's are.
- **Each is optional:** a field with no default is refused when the app is made, so an app that runs lines without
  a command line (in-process) gets each field's default.
- **`--version`,** with `App(version=…)`, writes the program's version, `relayctl 1.2.3`, and exits 0, whatever
  follows.
- **parsed's own flags** (`-h` or `--help`, `--json`, `--yes`, `--dry-run`) may stand among them, and are the
  line's: they're put first on it (`Said.run`), so `relayctl --json -c relay.toml status` runs `--json status`.
- **`--` ends them,** so a line may begin with a word that starts with dashes.

| Refused when the app is made (a `DeclarationError`) | |
|---|---|
| an options class that isn't a seared class, decorated | |
| a required field | a root option may be left out |
| a field read as a `Name` | root options are read before any names |
| a field with no word form (`Bytes`) and no kind in `KINDS` | |
| a field whose flag is parsed's (`--help`, `--json`, `--yes`, `--dry-run`, `--version`) | |
| a `SHORTS` entry that isn't one letter, or is `h`, or two fields with one letter | |
| a `version` that isn't a string | |

| Refused when read (a `ReadError`) | The message | Exit |
|---|---|---|
| a flag the program doesn't take | `relayctl takes no --confg; did you mean --config?` | 2 |
| a flag with no value after it | `--config needs a value` | 2 |
| a switch given a value, or a flag given twice, parsed's own among them | `--quiet takes nothing after it`, `--yes is given twice` | 2 |
| a word its kind can't read | `--workers: 'many' is not a whole number` | 2 |
| a value seared refuses | `--workers: must be >= 1, got 0` | 4 |

## The line

**After the first word, every flag is the line's,** never the program's: in
`relayctl -c relay.toml run --config own.toml`, `run`'s own `--config` is `own.toml`, whatever the root options
hold.

**The arguments are the line's words,** each as the shell gave it:

| Arguments | The line |
|---|---|
| `fleet` `f1` `dock` `Vesta Ring` | `fleet f1 dock "Vesta Ring"`: a word with a space quoted, so it's a value |
| `look log --n 40` (one argument) | `look log --n 40`: a single argument is the whole line, so a caller quotes once |
| `say` `""` | `say ""`: an empty word |
| `say` `a"b` | refused: of several, one holds a double quote, which no word of a line can |

## In this module

- `options_of(prog, cls, version)` declares and checks an app's root options, giving `Options`: their flags, shorts
  and kinds, `defaults()` and `usage()` (`relayctl [--config <config>] [--quiet] [--version] <command> …`).
- `read(args, options)` reads a program's arguments to `Said`: the root options loaded, parsed's own flags given
  among them (`own`), whether `--version` stood there, the `line` the words after them say, and `run`, that line
  with the own flags first.
- `line_of(args)` is the line the arguments after the root options say.
