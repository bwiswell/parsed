"""The fixtures as whole apps, as their command lines would build them: each a fresh ``App``, its handlers bound.

- ``servicectl()``: a service's command line. Root options before the verb (``-c/--config``, ``--version``), the
  service's skeleton at the root with its settings, and ``handheld connect``, built from a protocol's request class.
- ``meshctl()``: an aggregate command line, the same skeleton mounted twice, each mount with its own settings and its
  own namespace's line.
- ``tooled()``: an agent's tooling's verbs, each handler saying what the line was read to.
"""

import json
import tomllib

# At runtime: tooling evaluates a class's annotations (`typing.get_type_hints`).
from pathlib import Path  # noqa: TC003
from typing import ClassVar

import _support_protocol as protocol
import _support_service as service
import _support_tooled as tooled_verbs

import parsed


@parsed.parsed
class RelayOptions(parsed.Parsed):
    """A relay's root options, before its verb."""

    SHORTS: ClassVar[dict[str, str]] = {'config': 'c'}

    config: Path | None = parsed.Path(default=None, doc='the config file; left out, the service default')


def _config(command: service.ServiceCommand, ctx: parsed.Context) -> Path | None:
    """The config a service's command reads: its own ``--config``, else the program's."""
    options = ctx.options
    return command.config if command.config is not None else getattr(options, 'config', None)


def _run(command: service.Run, ctx: parsed.Context) -> str:
    return f'{ctx.mount.under or "relay"} on port {ctx.params.port}, config {_config(command, ctx)}'


def _validate(command: service.ValidateConfig, ctx: parsed.Context) -> str:
    """Read the config as TOML: valid, or the reason it isn't, raised."""
    path = _config(command, ctx)
    if path is None:
        return 'no config: the service default holds'
    try:
        tomllib.loads(path.read_text(encoding='utf-8'))
    except (OSError, tomllib.TOMLDecodeError) as e:
        msg = f'{path}: {e}'
        raise ValueError(msg) from None
    return f'{path} is valid'


def _status(command: service.Status, ctx: parsed.Context) -> str:
    return f'{ctx.mount.under or "relay"} is up'


def _connect(command: protocol.HandheldConnect, ctx: parsed.Context) -> str:
    """The protocol's request the command is, on the wire: what a service would send."""
    return json.dumps(protocol.HandheldEndpoint.dump(command), sort_keys=True)


def servicectl() -> parsed.App:
    """A service's command line: ``servicectl -c service.toml run``."""
    app = parsed.App('servicectl', options=RelayOptions, version='1.2.3')
    app.mount('_support_service', params=service.RelaySettings())
    app.mount('_support_protocol')
    app.on(service.Run, _run)
    app.on(service.ValidateConfig, _validate)
    app.on(service.Status, _status)
    app.on(protocol.HandheldConnect, _connect)
    return app


def meshctl() -> parsed.App:
    """An aggregate command line, a service's skeleton twice: ``meshctl relay run``, ``meshctl gateway run``."""
    app = parsed.App('meshctl', version='1.2.3')
    app.mount(
        '_support_service',
        under='relay',
        params=service.RelaySettings(),
        doc="The relay: a site's messages, onto the mesh.",
    )
    app.mount(
        '_support_service', under='gateway', params=service.GatewaySettings(), doc="The gateway: the mesh's boundary."
    )
    app.on(service.Run, _run)
    app.on(service.Status, _status)
    return app


def _read(command: parsed.Command, ctx: parsed.Context) -> str | tooled_verbs.Described:
    """What the line was read to, by its verb, as JSON: what tooled would act on."""
    if isinstance(command, tooled_verbs.Describe):
        return tooled_verbs.Described(operation=command.operation, reply=command.reply)
    said = json.dumps(type(command).dump(command), sort_keys=True)
    return f'{ctx.phrase.split()[0]} {said}' + (' (a dry run)' if ctx.dry_run else '')


def tooled() -> parsed.App:
    """An agent's tooling's command line: ``tooled wait FleetState fleet=f1 --until docked=true``."""
    app = parsed.App('tooled', version='0.2.4')
    app.mount('_support_tooled')
    for found in app.mounts[0].tree.commands:
        app.on(found.cls, _read)
    return app
