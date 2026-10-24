"""The command line: a program's arguments, its root options first, then a line.

:meth:`parsed.app.App.main` runs a program's arguments (``prog [options…] <words…>``); this module reads them.

- **Root options** stand before the first word: the flags of the app's options class (``App(prog,
  options=Options)``), a seared class whose fields are each optional, read once and given to handlers as
  ``ctx.options``. Each is read as a command's flag is: its field's wire name, ``_`` written ``-``, a ``Bool`` a switch
  (``--no-…`` when it defaults to ``True``), a short form where its ``SHORTS`` gives one. ``--version`` (with
  ``App(version=…)``) is parsed's there, and so are its own flags (``-h`` or ``--help``, ``--json``, ``--yes``,
  ``--dry-run``), which are the line's: they stand first on it. ``--`` ends them.
- **After the first word, every flag is the line's,** never the program's: ``prog relay run --config c.toml`` gives
  the line its ``--config``.
- **The arguments are the line's words,** each as the shell gave it: one with a space quoted (``fleet f1 dock "Vesta
  Ring"``), a double quote in one escaped, so ``--args '{"station": "s1"}'`` gives the field ``{"station": "s1"}``,
  and one given as ``--name=value`` the flag, whatever its value holds (``--args='{"a": 1}'``). A single argument is
  the whole line, so a caller quotes once: ``prog "look log --n 40"``.
- **A line back to its arguments:** ``args_of(line)`` gives each word as given, the inverse of ``line_of``, for a
  handler that runs a line passed on as a process.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from seared import ValidationError
from seared.doc import is_seared_class

from ._walk._hints import close, label
from ._walk._terms import RESERVED, Arity
from ._walk._walker import _flag, _given, _is_short, _text
from ._walk._words import Token, split, word
from .command import _kinds, _shorts
from .errors import DeclarationError, ReadError
from .help import rows
from .kinds import Named, Switch, default_kind
from .tree import _FLAG, Flag, flag_name

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from seared import Field, Seared

    from .command import Command
    from .kinds import Kind

#: The flag that asks for the program's version, with ``App(version=…)``.
_VERSION = 'version'


@dataclass(frozen=True, slots=True)
class Options:
    """An app's root options, as declared: the flags before the first word, and the class they're loaded to.

    Attributes:
        prog: The program's name.
        cls: The options class; ``None`` for an app with none.
        version: The program's version, for ``--version``; ``None`` for none.
        flags: Each flag, by name.
        shorts: Each short flag, to the flag it says: ``{'c': 'config'}``.
        kinds: Each field's kind, by attribute name.
    """

    prog: str
    cls: type[Seared] | None = None
    version: str | None = None
    flags: Mapping[str, Flag] = MappingProxyType({})
    shorts: Mapping[str, str] = MappingProxyType({})
    kinds: Mapping[str, Kind] = MappingProxyType({})

    def defaults(self) -> Seared | None:
        """The options as none are given: each field's default; ``None`` for an app with no options class."""
        return None if self.cls is None else self.cls.load({})

    def usage(self) -> str:
        """How the program is said: ``farlandia [--config <path>] [--version] <command> …``."""
        fields = {spec.attr: spec.field for spec in self.cls.__seared_fields__} if self.cls is not None else {}
        said = [self.prog, *(_usage(flag, fields[flag.field]) for flag in self.flags.values())]
        if self.version is not None:
            said.append(f'[--{_VERSION}]')
        return ' '.join([*said, '<command> …'])

    def help(self) -> str:
        """The program's help, above what it may say: its usage, then a row for each root option and ``--version``."""
        fields = {spec.attr: spec.field for spec in self.cls.__seared_fields__} if self.cls is not None else {}
        shorts = {name: short for short, name in self.shorts.items()}
        said = [
            (_row(flag, shorts.get(flag.name)), _what(flag, fields[flag.field], self.kinds[flag.field]))
            for flag in self.flags.values()
        ]
        if self.version is not None:
            said.append((f'--{_VERSION}', "the program's version"))
        return '\n\n'.join([self.usage(), '\n'.join(rows(said))]) if said else self.usage()


@dataclass(frozen=True, slots=True)
class Said:
    """A program's arguments, read: its root options, what parsed's own asked for, and the line.

    Attributes:
        options: The root options, loaded; ``None`` for an app with no options class.
        own: parsed's own flags given among them, by name (``help``, ``json``, ``yes``, ``dry-run``): the line's.
        version: Whether ``--version`` stood among them, asking for the program's version.
        line: The line the words after them say.
    """

    options: Seared | None
    own: frozenset[str]
    version: bool
    line: str

    @property
    def run(self) -> str:
        """The line to run: parsed's own flags given before the first word, then the line, as a line may say them."""
        own = [f'--{name}' for name in RESERVED if name in self.own]
        return ' '.join([*own, self.line] if self.line else own)


def options_of(prog: str, cls: type | None, version: str | None) -> Options:
    """An app's root options, declared and checked.

    Raises:
        DeclarationError: ``cls`` isn't a seared class; a field is required, or has no word form, or is a name; a flag
            is parsed's own or isn't lowercase words; or ``version`` isn't a string.
    """
    if version is not None and (not isinstance(version, str) or not version.strip()):
        msg = f"App({prog!r}, version={version!r}): the program's version, as --version says it"
        raise DeclarationError(msg)
    if cls is None:
        return Options(prog=prog, version=version)
    if not (isinstance(cls, type) and is_seared_class(cls)):
        msg = f'App({prog!r}, options={cls!r}): a seared class, decorated, whose fields are the root options'
        raise DeclarationError(msg)
    name = cls.__qualname__
    found: type[Seared] = cls
    declared = cast('type[Command]', cls)  # read for KINDS and SHORTS as a command's are
    attrs = tuple(spec.attr for spec in found.__seared_fields__)
    given = _kinds(declared)
    kinds = {spec.attr: _kind(name, spec.attr, spec.field, given) for spec in found.__seared_fields__}
    flags: dict[str, Flag] = {}
    for spec in found.__seared_fields__:
        if spec.field.required:
            msg = f'{name}.{spec.attr} is required: a root option may be left out, so give it a default'
            raise DeclarationError(msg)
        switch = isinstance(kinds[spec.attr], Switch)
        negated = switch and spec.field.default is True
        flag = flag_name(spec.wire, negated=negated)
        if not _FLAG.fullmatch(flag):
            msg = f'{name}.{spec.attr}: its flag would be --{flag}; a flag is lowercase words, so give it a data_key'
            raise DeclarationError(msg)
        if flag in (*RESERVED, _VERSION):
            msg = f"{name}.{spec.attr}: --{flag} is parsed's, before any command; give the field another name"
            raise DeclarationError(msg)
        said = flag if switch else label(kinds[spec.attr], spec.field, flag)
        arity = Arity.SWITCH if switch else Arity.VALUE
        flags[flag] = Flag(name=flag, field=spec.attr, arity=arity, negated=negated, label=said)
    names = {flag.field: flag.name for flag in flags.values()}
    shorts = {short: names[attr] for attr, short in _shorts(declared, name, attrs).items()}
    return Options(
        prog=prog,
        cls=found,
        version=version,
        flags=MappingProxyType(flags),
        shorts=MappingProxyType(shorts),
        kinds=MappingProxyType(kinds),
    )


def _kind(name: str, attr: str, field: Field, kinds: Mapping[str, Kind]) -> Kind:
    kind = kinds.get(attr) or default_kind(field)
    if kind is None:
        msg = f'{name}.{attr} is a {type(field).__name__} field, which has no word form: give it a kind in KINDS'
        raise DeclarationError(msg)
    if isinstance(kind, Named):
        msg = f'{name}.{attr} is read as a name, and root options are read before any names: give it another kind'
        raise DeclarationError(msg)
    return kind


def read(args: Sequence[str], options: Options) -> Said:
    """``args`` read: the root options before the first word, then the line the rest say.

    Raises:
        ReadError: A root option the program doesn't take, given twice, missing its value, or holding one its field
            refuses.
    """
    tokens, at = _tokens(args), 0
    given: dict[str, list[Token | None]] = {}
    own: set[str] = set()
    shown = ' '.join(args)
    while at < len(tokens):
        token = tokens[at]
        if token.raw == '--':
            at += 1
            break
        if not (token.raw.startswith('--') or _is_short(token)):
            break
        at += 1
        found = _flag(token, options.shorts)
        name, value = found if found is not None else (token.raw[1:], None)
        if found is not None and (name in RESERVED or (name == _VERSION and options.version is not None)):
            _own(token, name, value, own, shown)
            continue
        flag = options.flags.get(name) if found is not None else None
        if flag is None:
            near = [f'--{each}' for each in close(name, [*options.flags, *RESERVED])]
            raise _refused(shown, f'{options.prog} takes no {token.raw.partition("=")[0]}', token, near=near)
        if flag.arity is Arity.VALUE and value is None:
            if at == len(tokens) or _flag(tokens[at], options.shorts) is not None:
                said = _given(token, name)
                raise _refused(shown, f'{said} needs a value', token, hint=f'{said} <{flag.label}>')
            value = tokens[at]
            at += 1
        elif flag.arity is Arity.SWITCH and value is not None:
            raise _refused(shown, f'{_given(token, name)} takes nothing after it', token)
        given.setdefault(name, []).append(value)
    loaded = _load(options, given, tokens, shown) if options.cls is not None else None
    return Said(options=loaded, own=frozenset(own - {_VERSION}), version=_VERSION in own, line=line_of(args[at:]))


def _own(token: Token, name: str, value: Token | None, own: set[str], shown: str) -> None:
    """One of parsed's own, or ``--version``, given before the first word: a switch, given once."""
    if value is not None:
        raise _refused(shown, f'{_given(token, name)} takes nothing after it', token)
    if name in own:
        raise _refused(shown, f'{_given(token, name)} is given twice', token)
    own.add(name)


def line_of(args: Sequence[str]) -> str:
    r"""The line a program's arguments say: a single one as it is; several each a word, as given.

    Each of several is written so the line reads it back as given (:func:`parsed._walk._words.word`): quoted where it
    holds a space or is empty, each double quote in it written ``\"``. One given as ``--name=value`` is the flag
    whatever its value holds: ``--name=``, then the value as a word (``--args="{\"a\": 1}"``).
    """
    if len(args) == 1:
        return args[0]
    return ' '.join(_word(arg) for arg in args)


def _word(arg: str) -> str:
    """An argument as a line's word: one shaped ``--name=value`` as the flag, its value a word of its own."""
    head, eq, value = arg.partition('=')
    if eq and head.startswith('--') and len(head) > len('--') and not any(ch.isspace() or ch == '"' for ch in head):
        return f'{head}={word(value)}'  # the walk reads `--args="a b"` as the flag, its value `a b`
    return word(arg)


def args_of(line: str) -> list[str]:
    """The arguments a line says: each of its words as given, its quotes and escapes taken off.

    The inverse of :func:`line_of` for several arguments: ``args_of(line_of(args)) == args``. A single argument is
    the whole line, so it comes back as the line's words. ``then``, ``--`` and flags are words like any other, as no
    tree reads the line. A line passed on (a ``Line`` slot's) is a line too, so its handler gives a process the
    arguments it was given: ``args_of(command.line)``.

    Raises:
        ReadError: A quote is left open.
    """
    return [token.text for token in split(line)]


def _tokens(args: Sequence[str]) -> list[Token]:
    """Each argument as a word, where it stands in the arguments joined by spaces, for a refusal to point at."""
    tokens: list[Token] = []
    start = 0
    for arg in args:
        tokens.append(Token(text=arg, start=start, raw=arg))
        start += len(arg) + 1
    return tokens


def _load(options: Options, given: Mapping[str, list[Token | None]], tokens: list[Token], shown: str) -> Seared:
    """The root options given, each word read by its field's kind, then loaded by seared."""
    cls = cast('type[Seared]', options.cls)
    specs = {spec.attr: spec for spec in cls.__seared_fields__}
    data: dict[str, object] = {}
    words: dict[str, Token] = {}
    for name, values in given.items():
        flag = options.flags[name]
        spec = specs[flag.field]
        if len(values) > 1 and not spec.field.many:
            raise _refused(shown, f'--{name} is given twice', _second(tokens, name, options))
        if flag.arity is Arity.SWITCH:
            data[spec.wire] = not flag.negated
            continue
        read = [_read(options, flag, spec.field, cast('Token', value), shown) for value in values]
        data[spec.wire] = read if spec.field.many else read[0]
        words[spec.wire] = cast('Token', values[0])
    try:
        return cls.load(data, unknown='raise')
    except ValidationError as e:
        head = e.path[0] if e.path else None
        word = words.get(head) if isinstance(head, str) else None
        flag = next((flag for flag in options.flags.values() if specs[flag.field].wire == head), None)
        where = f'--{flag.name}' if flag is not None else options.prog
        message = f'{where}: {e.reason}'
        column = len(shown) if word is None else word.start
        raise ReadError(
            message, kind='validation', line=shown, column=column, word=None if word is None else word.raw
        ) from e


def _read(options: Options, flag: Flag, field: Field, value: Token, shown: str) -> object:
    try:
        return options.kinds[flag.field].read(value.text, field, quoted=value.quoted)
    except ValueError as e:
        raise _refused(shown, f'--{flag.name}: {e}', value) from None


def _second(tokens: list[Token], name: str, options: Options) -> Token:
    """The second word that gives ``--name``, for a refusal to point at."""
    giving = [token for token in tokens if (found := _flag(token, options.shorts)) is not None and found[0] == name]
    return giving[1]


def _row(flag: Flag, short: str | None) -> str:
    said = f'--{flag.name}' if flag.arity is Arity.SWITCH else f'--{flag.name} <{flag.label}>'
    return f'-{short}, {said}' if short else said


def _what(flag: Flag, field: Field, kind: Kind) -> str:
    if field.doc and field.doc.strip():
        return field.doc.strip()
    if flag.arity is Arity.SWITCH:
        return 'off when given' if flag.negated else 'on when given'
    return kind.describe(field)


def _usage(flag: Flag, field: Field) -> str:
    if flag.arity is Arity.SWITCH:
        return f'[--{flag.name}]'
    said = f'--{flag.name} <{flag.label}>'
    return f'[{said} …]' if field.many else f'[{said}]'


def _refused(shown: str, message: str, token: Token, *, hint: str | None = None, near: Sequence[str] = ()) -> ReadError:
    """A root option refused, at its word, as the walk refuses a line's flag."""
    return ReadError(
        _text(message, near=near, hint=hint),
        line=shown,
        column=token.start,
        word=token.raw,
        hint=hint,
        suggestions=near,
    )
