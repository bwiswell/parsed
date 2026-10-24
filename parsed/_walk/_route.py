"""Routing a line to the mount whose commands say it, by its first words.

An app holds several trees, each mounted under a prefix of words (:mod:`parsed.app`). :class:`Routes` is a trie of
those words: each mount's prefix, then each word its commands may begin with, which is the mount's. A line's words
are followed from the root until one is a mount's, and that mount's tree reads the whole line, prefix and all.

**The routes refuse a mount that would make a line read two ways:** a prefix that runs through another mount's
words, or a first word another mount begins a command with, or one where other mounts stand. So two mounts may share
a prefix, if no word begins a command in both.

**A line that reaches no mount is refused** as a tree refuses a line: no command, with what may have been meant, or
the words that may come next. parsed's own flags (``--yes``, ``--json``, …) may stand among the words that route it,
and a field's flag ends them, since only a mount's tree knows whether it takes a value.

**For a session's subjects** (:mod:`parsed.app`), :meth:`Routes.begins` says whether a word begins a line, and
:meth:`Routes.reach` how far words go: to a mount, part of the way along a prefix, or nowhere. **For help** short of
a command, :meth:`Routes.beneath` gives every mount the words may still go to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from parsed.errors import DeclarationError, ReadError

from ._complete import Completion, being_typed
from ._hints import close
from ._terms import RESERVED
from ._walker import _flag, _said, _text
from ._words import split

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from parsed.tree import Tree

    from ._words import Token


class Mounted(Protocol):
    """What the routes hold: a tree under its prefix, and how a refusal names it."""

    @property
    def tree(self) -> Tree:
        """The tree, under its prefix."""
        ...

    @property
    def label(self) -> str:
        """The mount as a refusal names it: its source, and where it's mounted."""
        ...


@dataclass(slots=True)
class _Stop[M: Mounted]:
    """A word on the way to a mount: the words that may follow it, or the mount whose line it is from here."""

    words: dict[str, _Stop[M]] = field(default_factory=dict)
    held: M | None = None


class Routes[M: Mounted]:
    """Each mount's prefix and first words, in one trie: the mount a line goes to (see the module)."""

    def __init__(self) -> None:
        """No mounts yet."""
        self.root: _Stop[M] = _Stop()

    def add(self, mount: M) -> None:
        """Route the words ``mount``'s commands begin with, after its prefix, to it.

        Raises:
            DeclarationError: Its tree has no commands, or a line would read two ways: the message names both
                mounts and the words they share.
        """
        under = mount.tree.under.split()
        firsts = list(mount.tree.top.words)
        if not firsts:
            msg = f'{mount.label} has no commands to mount'
            raise DeclarationError(msg)
        self._check(mount, under, firsts)
        stop = self.root
        for word in under:
            stop = stop.words.setdefault(word, _Stop())
        for word in firsts:
            stop.words[word] = _Stop(held=mount)

    def _check(self, mount: M, under: list[str], firsts: list[str]) -> None:
        stop = self.root
        for at, word in enumerate(under):
            found = stop.words.get(word)
            if found is None:
                return  # a prefix no other mount's words go along
            if found.held is not None:
                said = ' '.join(under[: at + 1])
                msg = f'{mount.label} is mounted where {found.held.label} says {said!r}: a line would read two ways'
                raise DeclarationError(msg)
            stop = found
        for word in firsts:
            found = stop.words.get(word)
            if found is None:
                continue
            said = ' '.join([*under, word])
            if found.held is not None:
                msg = f'{mount.label} and {found.held.label} both say {said!r}: a line would read two ways'
                raise DeclarationError(msg)
            beneath = next(_held(found))
            msg = f'{mount.label} says {said!r}, where {beneath.label} is mounted: a line would read two ways'
            raise DeclarationError(msg)

    def route(self, line: str) -> M:
        """The mount whose tree reads ``line``.

        Raises:
            ReadError: Its words reach no mount: no command, or the words that may come next.
        """
        tokens = split(line)
        first = _flag(tokens[0]) if tokens else None
        if first is not None and first[0] not in RESERVED:
            msg = f'{tokens[0].raw} comes before a command: a flag follows the first word'
            raise _refused(line, msg, word=tokens[0])
        stop, said = self.root, []
        for token in tokens:
            found = _flag(token)
            if found is not None and found[0] in RESERVED:
                continue
            if found is not None or token.raw == '--':
                raise _refused(line, *_next(stop, said), word=token)
            following = None if token.quoted else stop.words.get(token.text.lower())
            if following is None:
                raise _unknown(line, stop, said, token)
            stop = following
            said.append(token)
            if stop.held is not None:
                return stop.held
        if not said:
            raise _refused(line, 'no command: the line has no words', suggestions=list(stop.words))
        raise _refused(line, *_next(stop, said))

    def begins(self, token: Token) -> bool:
        """Whether ``token`` begins a line: the first word of a mount's prefix, or of a command at the root."""
        return not token.quoted and token.text.lower() in self.root.words

    def reach(self, tokens: Sequence[Token]) -> M | bool:
        """How far ``tokens``, words without flags, go: the mount they reach, or whether they go at all.

        ``True`` where they stop along a prefix, short of a mount; ``False`` where a word goes nowhere.
        """
        stop = self.root
        for token in tokens:
            following = None if token.quoted else stop.words.get(token.text.lower())
            if following is None:
                return False
            if following.held is not None:
                return following.held
            stop = following
        return True

    def beneath(self, tokens: Sequence[Token]) -> list[M]:
        """Every mount ``tokens``, words without flags, may still go to, in the order they were mounted.

        The one they reach; each beneath where they stop along a prefix; none where a word goes nowhere.
        """
        stop = self.root
        for token in tokens:
            following = None if token.quoted else stop.words.get(token.text.lower())
            if following is None:
                return []
            if following.held is not None:
                return [following.held]
            stop = following
        return list(dict.fromkeys(_held(stop)))

    def complete(self, text: str) -> M | Completion:
        """The mount whose tree completes ``text``, a line up to the cursor; short of one, what may follow there.

        What may follow a prefix is offered as a tree offers words: those that begin with the word being typed, and
        how much of it each replaces.
        """
        tokens, partial = being_typed(text)
        stop = self.root
        for token in tokens:
            found = _flag(token)
            if found is not None and found[0] in RESERVED:
                continue
            following = None if found is not None or token.quoted else stop.words.get(token.text.lower())
            if following is None:
                return Completion(words=[], replace=0 if partial is None else len(text) - partial.start)
            stop = following
            if stop.held is not None:
                return stop.held
        if partial is None:
            return Completion(words=list(stop.words), replace=0)
        said = partial.text.lower()
        words = [] if partial.quoted else [word for word in stop.words if word.startswith(said)]
        return Completion(words=words, replace=len(text) - partial.start)


def _held[M: Mounted](stop: _Stop[M]) -> Iterator[M]:
    """Every mount beneath ``stop``, in the order their words were routed."""
    for following in stop.words.values():
        if following.held is not None:
            yield following.held
        else:
            yield from _held(following)


def _next[M: Mounted](stop: _Stop[M], said: list[Token]) -> tuple[str, Sequence[str]]:
    """A refusal where a mount's words stop short: the words that may come next."""
    words = list(stop.words)
    return f'{_said(said)}: then what? {" | ".join(words)}', words


def _unknown[M: Mounted](line: str, stop: _Stop[M], said: list[Token], word: Token) -> ReadError:
    """A word no mount says here, as a tree refuses one."""
    asked = _said([*said, word])
    near = [] if word.quoted else close(word.text.lower(), stop.words)
    if near:
        return _refused(line, f'no command {asked!r}', word=word, near=near)
    words = list(stop.words)
    return _refused(line, f'no command {asked!r}: {" | ".join(words)}', word=word, suggestions=words)


def _refused(
    line: str,
    what: str,
    suggestions: Sequence[str] = (),
    *,
    word: Token | None = None,
    near: Sequence[str] = (),
) -> ReadError:
    """A refusal at ``word``, or at the line's end, as the walk makes one."""
    return ReadError(
        _text(what, near=near),
        line=line,
        column=len(line) if word is None else word.start,
        word=None if word is None else word.raw,
        suggestions=near or suggestions,
    )
