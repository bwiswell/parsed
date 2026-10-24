# `_walk/_hints.py`: a refusal's hint and did-you-mean

**`usage(bound, flags, fields, *, start=0, asks=False)`** is how a command is said by one of its phrases: its
words, a `<slot>` for each slot, then its flags. A refusal gives it as its hint.

| Part | Written |
|---|---|
| a slot | `<fleet>` |
| an optional slot | `[<n>]` |
| a slot of several words | `<goods> …` |
| the rest of the line | `<message …>` |
| a required flag | `--into <into>`; a list's `--until <until> …` |
| any other flag | `[--for <for>]`; a list's `[--tags <tags> …]` |
| a switch | `[--quiet]`, or `[--no-stop]` for one negated |
| last, for a command that may ask first (`asks=True`, its `ASKS`) | `[--yes]`, which answers it |

So `fleets merge {fleet}`, with a required `into` and a `quiet` switch, asked first, is
`fleets merge <fleet> --into <into> [--quiet] [--yes]`. `usage(…, start=n)` begins at the phrase's `n`th part, for
the rest of a line that has said the parts before it. Any other command's usage leaves `--yes` out, though every
command takes it: a usage says what's worth knowing.

Where a line stops at a slot, the hint is the line so far, then:

- **where one command lies past the slot,** the rest of its usage, flags and all: `fleets init` hints
  `fleets init <ships> … [--name <name>]`, and `fleet f1 jump` hints `fleet f1 jump <system>`;
- **where several do,** the slot's `<…>`, then `…` if more must follow: `fleet <fleet> …`.

**`close(word, candidates)`** is up to three candidates close to a word, the closest first, by the standard
library's `difflib`: the did-you-mean of a word no command says, or a flag no command takes.

**`either(words)`** joins words for a sentence: `mine`, `fleet or fleets`, `a, b or c`.
