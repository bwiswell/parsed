"""A command whose field no generated word fits: the check skips its round trips, and still reads its examples."""

import parsed


@parsed.parsed
class Hail(parsed.Command):
    """Hail a ship by its call sign: three capitals."""

    PHRASE = 'hail {sign}'
    EXAMPLES = ('hail ABC',)

    sign: str = parsed.Str(required=True, pattern='[A-Z]{3}')
