"""Commands shaped like a rio service's, written fresh: parsed's tests depend on no service.

It grows with each release that needs more of it. So far: a protocol's request class, a plain seared class as a
protocol package declares it, and the command that inherits it, so the command's fields and their bounds are the
protocol's own.
"""

import seared

import parsed


@seared.seared
class HandheldEndpoint(seared.Seared):
    """A protocol's request: a handheld reader's endpoint to connect."""

    source: str = seared.Str(required=True, doc='the source the reader belongs to')
    reader_id: str = seared.Str(required=True, doc="the reader's id")
    host: str = seared.Str(required=True, doc='where the reader listens')
    port: int = seared.Int(default=5084, ge=1, le=65535, doc='its port')
    label: str = seared.Str(default='', doc='a label to show')


@parsed.parsed
class HandheldConnect(parsed.Command, HandheldEndpoint):
    """Connect a handheld reader."""

    PHRASE = 'handheld connect {source} {reader_id}'
    EFFECT = parsed.Effect.WRITE
