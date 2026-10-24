"""A service's skeleton group, as each service of a family carries one: mounted by many apps, each with its settings.

- `run`, `validate-config` and `status`, each reading `--config`, or `-c`;
- two settings classes, for two services that mount it, each its mount's parameters.
"""

# At runtime: tooling evaluates a command's annotations (`typing.get_type_hints`).
from pathlib import Path  # noqa: TC003
from typing import ClassVar

import parsed


@parsed.parsed
class ServiceCommand(parsed.Command):
    """A base: the config file every command of the skeleton reads."""

    SHORTS: ClassVar[dict[str, str]] = {'config': 'c'}

    config: Path | None = parsed.Path(default=None, doc='the config file; left out, the service default')


@parsed.parsed
class Run(ServiceCommand):
    """Run the service until it's stopped."""

    PHRASE = 'run'
    EFFECT = parsed.Effect.ACTION


@parsed.parsed
class ValidateConfig(ServiceCommand):
    """Check the config file, and say what's wrong with it."""

    PHRASE = 'validate-config'
    EFFECT = parsed.Effect.READ


@parsed.parsed
class Status(ServiceCommand):
    """Say whether the service is up."""

    PHRASE = 'status'
    EFFECT = parsed.Effect.READ


@parsed.parsed
class RelaySettings(parsed.Parsed):
    """One service's settings: a relay's."""

    port: int = parsed.Int(default=5085)


@parsed.parsed
class GatewaySettings(parsed.Parsed):
    """Another's: a gateway's."""

    port: int = parsed.Int(default=8443)
