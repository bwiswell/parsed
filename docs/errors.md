# `errors.py`: what can go wrong

Every error parsed raises is a `parsed.ParsedError`. seared's own errors (a value that fails its field, a
`seared.ValidationError`) stay seared's and pass through as they are.

| Error | Raised when |
|---|---|
| `ParsedError` | the base of every error below |
| `DeclarationError` | a command is declared in a way parsed can't use ([`command.md`](command.md)): it names the class and the constant, and says how to put it right. It's a `TypeError` too, as a mistake in a class's definition is in Python |
| `ReadError` | a line doesn't read ([`_walk/_walker.md`](_walk/_walker.md#what-it-refuses)): a word no command says, a slot left empty, a flag the command doesn't take. Its message says what's wrong, with the words read up to it. It's a `ValueError` too, as a value Python can't read is |
