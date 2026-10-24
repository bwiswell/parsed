"""Tests for ``parsed/argv.py``: a program's arguments, its root options first, then a line."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

import parsed
from parsed.argv import Options, args_of, line_of, options_of, read
from parsed.errors import DeclarationError, ReadError


@parsed.parsed
class Root(parsed.Parsed):
    """A program's root options: a config file, a switch, a count with a bound, and a list."""

    SHORTS: ClassVar[dict[str, str]] = {'config': 'c', 'quiet': 'q'}

    config: Path | None = parsed.Path(default=None)
    quiet: bool = parsed.Bool(default=False)
    color: bool = parsed.Bool(default=True)
    workers: int = parsed.Int(default=1, ge=1)
    tags: list[str] = parsed.Str(many=True, default_factory=list)


@pytest.fixture(scope='module')
def options() -> Options:
    return options_of('servicectl', Root, '1.2.3')


class TestDeclaring:
    def test_each_field_a_flag(self, options):
        assert list(options.flags) == ['config', 'quiet', 'no-color', 'workers', 'tags']
        assert options.flags['no-color'].negated
        assert dict(options.shorts) == {'c': 'config', 'q': 'quiet'}
        assert (options.cls, options.version) == (Root, '1.2.3')

    def test_none_for_an_app_without(self):
        found = options_of('farlandia', None, None)
        assert (found.cls, dict(found.flags), found.defaults()) == (None, {}, None)

    def test_the_defaults(self, options):
        assert options.defaults() == Root()

    def test_the_program_s_usage(self, options):
        assert options.usage() == (
            'servicectl [--config <path>] [--quiet] [--no-color] [--workers <n>] [--tags <tags> …] [--version] '
            '<command> …'
        )
        assert options_of('farlandia', None, None).usage() == 'farlandia <command> …'

    def test_the_program_s_help(self, options):
        usage, rows = options.help().split('\n\n')
        assert usage == options.usage()
        assert rows.splitlines() == [
            '  -c, --config <path>  a path',
            '  -q, --quiet          on when given',
            '  --no-color           off when given',
            '  --workers <n>        a whole number',
            '  --tags <tags>        a word',
            "  --version            the program's version",
        ]
        assert options_of('farlandia', None, None).help() == 'farlandia <command> …'

    def test_refused(self):
        @parsed.parsed
        class Required(parsed.Parsed):
            config: str = parsed.Str(required=True)

        @parsed.parsed
        class Named(parsed.Parsed):
            KINDS: ClassVar[dict[str, parsed.Kind]] = {'fleet': parsed.Name('fleet')}

            fleet: str | None = parsed.Str(default=None)

        @parsed.parsed
        class Versioned(parsed.Parsed):
            version: bool = parsed.Bool(default=False)

        @parsed.parsed
        class Helped(parsed.Parsed):
            SHORTS: ClassVar[dict[str, str]] = {'loud': 'h'}

            loud: bool = parsed.Bool(default=False)

        @parsed.parsed
        class Raw(parsed.Parsed):
            blob: bytes | None = parsed.Bytes(default=None)

        for cls, message in [
            (dict, r"App\('p', options=<class 'dict'>\): a seared class, decorated"),
            (Required, r'Required\.config is required: a root option may be left out, so give it a default'),
            (Named, r'Named\.fleet is read as a name, and root options are read before any names'),
            (Versioned, r"Versioned\.version: --version is parsed's, before any command"),
            (Helped, r"Helped\.SHORTS\['loud'\]: -h is --help's"),
            (Raw, r'Raw\.blob is a Bytes field, which has no word form'),
        ]:
            with pytest.raises(DeclarationError, match=message):
                options_of('p', cls, None)

    def test_a_version_is_a_string(self):
        with pytest.raises(DeclarationError, match=r"App\('p', version=3\): the program's version"):
            options_of('p', None, 3)


class TestReading:
    def test_before_the_first_word(self, options):
        said = read(['-c', 'r.toml', '--workers', '4', '--no-color', 'relay', 'run', '--config', 'own.toml'], options)
        assert said.options == Root(config=Path('r.toml'), workers=4, color=False)
        assert said.line == 'relay run --config own.toml'  # after the first word, the line's
        assert (said.own, said.version) == (frozenset(), False)
        assert said.run == said.line

    def test_none_given_the_defaults(self, options):
        assert read(['status'], options).options == Root()

    def test_a_value_after_an_equals_a_switch_a_list(self, options):
        said = read(['--workers=2', '-q', '--tags', 'a', '--tags', 'b', 'status'], options)
        assert said.options == Root(workers=2, quiet=True, tags=['a', 'b'])

    def test_two_dashes_end_them(self, options):
        assert read(['-q', '--', '--weird', 'line'], options).line == '--weird line'

    def test_parsed_s_own_are_the_line_s_first(self, options):
        said = read(['--json', '-q', '--dry-run', '--yes', 'relay', 'run', '--config', 'own.toml'], options)
        assert (said.own, said.options) == ({'json', 'dry-run', 'yes'}, Root(quiet=True))
        assert said.run == '--json --yes --dry-run relay run --config own.toml'  # as a line may say them, in order
        assert read(['-h'], options).run == '--help'
        assert read(['--help', 'status'], options).run == '--help status'

    def test_version(self, options):
        assert read(['--version'], options).version
        with pytest.raises(ReadError, match=r'farlandia takes no --version'):
            read(['--version'], options_of('farlandia', None, None))  # with no version, none

    @pytest.mark.parametrize(
        ('args', 'says', 'kind'),
        [
            (['--confg', 'a', 'run'], r'servicectl takes no --confg; did you mean --config\?', 'usage'),
            (['-x', 'run'], r'servicectl takes no -x', 'usage'),
            (['--config'], r'--config needs a value `--config <path>`', 'usage'),
            (['-c', '-q', 'run'], r'-c needs a value `-c <path>`', 'usage'),
            (['--quiet=yes', 'run'], r'--quiet takes nothing after it', 'usage'),
            (['--help=yes'], r'--help takes nothing after it', 'usage'),
            (['--yes', '--yes', 'run'], r'--yes is given twice', 'usage'),
            (['--jsn', 'run'], r'servicectl takes no --jsn; did you mean --json\?', 'usage'),
            (['-q', '--quiet', 'run'], r'--quiet is given twice', 'usage'),
            (['--workers', 'many', 'run'], r"--workers: 'many' is not a whole number", 'usage'),
            (['--workers', '0', 'run'], r'--workers: must be >= 1', 'validation'),
        ],
    )
    def test_refused(self, options, args, says, kind):
        with pytest.raises(ReadError, match=says) as caught:
            read(args, options)
        assert caught.value.kind == kind
        assert caught.value.line == ' '.join(args)

    def test_a_refusal_points_at_its_word(self, options):
        with pytest.raises(ReadError) as caught:
            read(['-q', '--workers', '0', 'run'], options)
        assert (caught.value.column, caught.value.word) == (13, '0')


class TestTheLine:
    def test_a_single_argument_is_the_whole_line(self):
        assert line_of(['look log --n 40']) == 'look log --n 40'
        assert line_of(['fleet "Vruba\'a Belt 1" mine']) == 'fleet "Vruba\'a Belt 1" mine'

    def test_several_each_a_word_one_with_a_space_quoted(self):
        assert line_of(['fleet', 'f1', 'dock', 'Vesta Ring']) == 'fleet f1 dock "Vesta Ring"'
        assert line_of(['say', '', 'x']) == 'say "" x'
        assert line_of([]) == ''

    def test_a_double_quote_among_several_escaped(self):
        assert line_of(['call', 't', '--args', '{"station": "s1"}']) == r'call t --args "{\"station\": \"s1\"}"'
        assert line_of(['say', 'a"b']) == r'say a\"b'

    @pytest.mark.parametrize(
        ('arg', 'said'),
        [
            ('--args={"a": 1}', r'--args="{\"a\": 1}"'),
            ('--param=k=v w', '--param="k=v w"'),
            ('--config=C:\\My Dir\\', '--config="C:\\My Dir"\\'),
            ('--args=x', '--args=x'),
            ('--args=', '--args=""'),
        ],
    )
    def test_a_flag_given_with_its_value_the_flag_whatever_it_holds(self, arg, said):
        assert line_of(['call', arg]) == f'call {said}'

    @pytest.mark.parametrize(
        ('arg', 'said'), [('--a b=c', '"--a b=c"'), ('--"x"=y', r'--\"x\"=y'), ('-c=x y', '"-c=x y"')]
    )
    def test_no_long_flag_s_head_a_word_as_before(self, arg, said):
        assert line_of(['call', arg]) == f'call {said}'


class TestALineBackToItsArguments:
    @pytest.mark.parametrize(
        'args',
        [
            [],
            ['fleet', 'f1', 'dock', 'Vesta Ring'],
            ['say', '', 'x'],
            ['call', 't', '--args', '{"station": "s1"}'],
            ['say', 'a"b', '"', '""', 'a\\"b'],
            ['cd', 'C:\\dir\\', 'C:\\My Dir\\', '\\'],
            ['fleet', 'f1', 'jump', 'sol', 'then', 'mine', '--', '-h', '--yes', '--x=a b'],
            ['tab\there', 'a\nnew line', ' padded '],
            ["Vruba'a Belt 1", 'é', '='],
            ['call', 't', '--args={"a": 1}', '--param=k=v w', '--x=', '--y=C:\\My Dir\\', '--', '--z=a b'],
        ],
    )
    def test_the_inverse_of_line_of(self, args):
        assert args_of(line_of(args)) == args

    def test_a_single_argument_the_line_s_words(self):
        assert args_of(line_of(['look log --n 40'])) == ['look', 'log', '--n', '40']
        assert args_of(line_of(['look'])) == ['look']

    def test_a_line_as_typed(self):
        line = r'fleet f1 dock "Vesta Ring" --until name=\"40\" --x="a b" then'
        assert args_of(line) == ['fleet', 'f1', 'dock', 'Vesta Ring', '--until', 'name="40"', '--x=a b', 'then']

    def test_a_quote_left_open_refused(self):
        with pytest.raises(ReadError, match='never closed') as caught:
            args_of('fleet "f1')
        assert (caught.value.line, caught.value.column) == ('fleet "f1', 6)
