"""Tests for ``parsed/_walk/_walker.py``: a line's flags split off, its words walked, each field's words kept."""

from __future__ import annotations

from datetime import timedelta

import _support_farlandia as farlandia
import _support_rio as rio
import pytest

import parsed
from parsed.command import Command
from parsed.errors import ReadError
from parsed.tree import Flag, Tree


def _command(phrase: str, **fields: object) -> type[Command]:
    """A decorated command with ``phrase`` and ``fields``, each annotated as an ``object``."""
    namespace: dict[str, object] = {'PHRASE': phrase, '__annotations__': dict.fromkeys(fields, object)}
    namespace.update(fields)
    return parsed.parsed(type('Cmd', (Command,), namespace))


def _one(phrase: str, **fields: object) -> Tree:
    return Tree([_command(phrase, **fields)])


@pytest.fixture(scope='module')
def tree() -> Tree:
    return Tree.collect('_support_farlandia', '_support_rio')


class TestEveryFixture:
    # Each fixture command, read from a line to the instance, its names kept as typed.
    @pytest.mark.parametrize(
        ('line', 'expected'),
        [
            ('fleet prospector mine', farlandia.FleetMine(fleet='prospector')),
            ('detachment d2 mine --for 90s', farlandia.FleetMine(fleet='d2', for_=timedelta(seconds=90))),
            ('fleet f1 dock', farlandia.FleetDock(fleet='f1')),
            ('fleet f1 dock nearest', farlandia.FleetDock(fleet='f1')),
            ('fleet f1 dock vesta', farlandia.FleetDock(fleet='f1', station='vesta')),
            ('fleet f1 jump sol', farlandia.FleetJump(fleet='f1', system='sol')),
            ('fleet f1 jump nearest iron', farlandia.FleetJumpNearest(fleet='f1', ore='iron')),
            ('fleet f1 sell iron coal', farlandia.FleetSell(fleet='f1', goods=['iron', 'coal'])),
            ('log', farlandia.Log()),
            ('log 40', farlandia.Log(n=40)),
            ('say hello there', farlandia.Say(message='hello there')),
            ('fleet "Vruba\'a 1" buy ship hauler', farlandia.FleetBuyShip(fleet="Vruba'a 1", hull='hauler')),
            ('fleets merge f1 --into f2', farlandia.FleetsMerge(fleet='f1', into='f2')),
            ('fleets show f1', farlandia.FleetsShow(fleet='f1')),
            ('ships make s1 add drill', farlandia.ShipsMakeAdd(ship='s1', part='drill')),
            ('ship s1 fit', farlandia.ShipFit(ship='s1')),
            (
                'handheld connect dock r7 --host 10.0.0.2 --port 5085',
                rio.HandheldConnect(source='dock', reader_id='r7', host='10.0.0.2', port=5085),
            ),
        ],
    )
    def test_a_line_reads_to_its_instance(self, tree, line, expected):
        assert tree.read(line) == expected


class TestWords:
    def test_literals_match_case_aside_and_values_keep_theirs(self, tree):
        assert tree.read('FLEET Prospector Mine') == farlandia.FleetMine(fleet='Prospector')

    def test_a_literal_beats_a_slot(self, tree):
        assert tree.walk('fleet f1 jump nearest iron').command is farlandia.FleetJumpNearest
        assert tree.walk('fleet f1 jump nearer').command is farlandia.FleetJump

    def test_a_quoted_word_is_never_a_literal(self, tree):
        assert tree.read('fleet f1 jump "nearest"') == farlandia.FleetJump(fleet='f1', system='nearest')
        assert tree.read('fleet f1 dock "nearest"') == farlandia.FleetDock(fleet='f1', station='nearest')

    def test_a_renamed_slot_fills_its_field(self, tree):
        given = tree.walk('detachment d2 mine').given['fleet']
        assert (given.by.slot, given.field, given.value) == ('detachment', 'fleet', 'd2')

    def test_several_words_up_to_a_literal_after_them(self):
        sell = _one('sell {goods} now', goods=parsed.Str(many=True, required=True))
        assert sell.read('sell iron coal now').goods == ['iron', 'coal']
        assert sell.read('sell "now" now').goods == ['now']

    def test_the_rest_of_the_line_single_spaced(self, tree):
        assert tree.read('say hello   there  galaxy').message == 'hello there galaxy'

    def test_the_rest_of_the_line_into_a_list(self):
        note = _one('note {words**}', words=parsed.Str(many=True, required=True))
        assert note.read('note one two').words == ['one', 'two']

    def test_a_field_left_out_keeps_its_default(self, tree):
        reading = tree.walk('log')
        assert dict(reading.given) == {}
        assert reading.load() == farlandia.Log(n=20)


class TestWordForms:
    # Each kind's own words are `tests/test_kinds.py`'s; these pin the walk reading by them.
    def test_a_slot_s_word_read_by_its_kind(self, tree):
        reading = tree.walk('log 1,000')
        assert reading.data() == {'n': 1000}
        assert reading.load() == farlandia.Log(n=1000)

    def test_a_flag_s_word_read_by_its_kind(self, tree):
        assert tree.walk('fleet f1 mine --for 1h30m').data() == {'fleet': 'f1', 'for': 5400.0}
        assert tree.walk('handheld connect dock r7 --host h --port 5,085').given['port'].value == 5085

    def test_a_list_s_words_each_read(self):
        tag = _one('tag {ns}', ns=parsed.Int(many=True, required=True))
        assert tag.read('tag 1 2,000 3').ns == [1, 2000, 3]
        flagged = _one('tag', ns=parsed.Int(many=True, default_factory=list))
        assert flagged.read('tag --ns 1 --ns 2').ns == [1, 2]

    def test_the_rest_of_the_line_read_once(self, tree):
        assert tree.walk('say 1,000 ships').given['message'].value == '1,000 ships'

    def test_a_bool_said_as_a_word(self, tree):
        assert tree.read('fleets start FALSE') == farlandia.FleetsStart(on=False)

    @pytest.mark.parametrize(
        ('line', 'says'),
        [
            ('log many', r"log \{n\}: 'many' is not a whole number"),
            ('fleet f1 mine --for soon', r"--for: 'soon' is not a span of time: say 90s, 10m, 2h or 1h30m"),
            ('fleet f1 mine --for 90', r"--for: '90' is not a span of time"),
            ('fleets start maybe', r"fleets start \{on\}: 'maybe' is not true or false"),
            ('handheld connect dock r7 --host h --port 1,00', r"--port: '1,00' is not a whole number"),
        ],
    )
    def test_a_word_its_kind_can_t_read_says_where_it_stands(self, tree, line, says):
        with pytest.raises(ReadError, match=says):
            tree.walk(line)

    def test_a_kind_s_bounds_are_seared_s_to_check(self, tree):
        reading = tree.walk('log 0')
        assert reading.data() == {'n': 0}
        with pytest.raises(ReadError, match=r'log \{n\}: must be >= 1, got 0'):
            reading.load()

    def test_load_refuses_a_key_the_command_doesn_t_know(self, tree, monkeypatch):
        reading = tree.walk('log 40')
        monkeypatch.setattr(type(reading), 'data', lambda _: {'n': 40, 'lines': 3})
        with pytest.raises(ReadError, match=r'log \{n\}: unknown key') as caught:
            reading.load()
        assert (caught.value.kind, caught.value.field) == ('validation', None)


class TestFlags:
    def test_anywhere_after_the_first_word(self, tree):
        expected = farlandia.FleetsMerge(fleet='f1', into='f2')
        assert tree.read('fleets merge --into f2 f1') == expected
        assert tree.read('fleets --into f2 merge f1') == expected

    def test_a_value_after_an_equals_quoted_or_not(self, tree):
        assert tree.read('fleet f1 mine --for=90s').for_ == timedelta(seconds=90)
        found = tree.read('handheld connect dock r7 --host=h --label="north dock"')
        assert found.label == 'north dock'

    def test_a_switch_and_a_negated_one(self, tree):
        assert tree.read('fleets merge f1 --into f2 --quiet').quiet is True
        stop = _one('mine', stop=parsed.Bool(default=True))
        assert stop.read('mine --no-stop').stop is False

    def test_names_are_lowercased(self, tree):
        assert tree.read('fleet f1 mine --FOR 90s').for_ == timedelta(seconds=90)

    def test_a_value_the_tree_would_take_for_a_literal(self, tree):
        assert tree.read('fleets merge f1 --into merge').into == 'merge'

    def test_a_value_that_starts_with_one_dash(self):
        move = _one('move', by=parsed.Int(default=0))
        assert move.read('move --by -3').by == -3

    def test_a_list_s_flag_given_again_adds_to_it(self):
        tag = _one('tag', tags=parsed.Str(many=True, default_factory=list))
        assert tag.read('tag --tags a --tags b').tags == ['a', 'b']

    def test_two_dashes_end_the_flags(self, tree):
        assert tree.read('say -- use --force -- now').message == 'use --force -- now'

    def test_a_quoted_flag_is_a_word(self, tree):
        assert tree.read('say "--loud" now').message == '--loud now'

    def test_parsed_s_own_on_any_command(self, tree):
        reading = tree.walk('fleet f1 buy ship hauler --yes --json')
        assert reading.own == {'yes', 'json'}
        assert reading.data() == {'fleet': 'f1', 'hull': 'hauler'}
        assert tree.walk('log --help --dry-run').own == {'help', 'dry-run'}


class TestReading:
    def test_each_field_s_words_and_what_took_them(self, tree):
        reading = tree.walk('fleets merge f1 --into f2 --quiet')
        assert list(reading.given) == ['fleet', 'into', 'quiet']
        fleet, into, quiet = reading.given.values()
        assert (fleet.by.slot, [w.text for w in fleet.words], fleet.value) == ('fleet', ['f1'], 'f1')
        assert into.by == Flag(name='into', field='into', arity=parsed.tree.Arity.VALUE)
        assert ([w.raw for w in into.words], into.value) == (['--into', 'f2'], 'f2')
        assert ([w.start for w in quiet.words], quiet.value) == ([26], True)

    def test_a_value_after_an_equals_starts_after_it(self, tree):
        given = tree.walk('fleet f1 mine --for=90s').given['for_']
        assert [(w.text, w.start) for w in given.words] == [('--for=90s', 14), ('90s', 20)]

    def test_data_is_by_wire_name(self, tree):
        assert tree.walk('fleet f1 mine --for 90s').data() == {'fleet': 'f1', 'for': 90.0}

    def test_where_the_walk_ended(self, tree):
        reading = tree.walk('fleet f1 dock nearest')
        assert reading.command is farlandia.FleetDock
        assert reading.end.bound.phrase.text == 'fleet {fleet} dock nearest'

    def test_the_line_it_was_read_from(self, tree):
        assert tree.walk('  log 40 ').line == '  log 40 '


class TestRefusals:
    @pytest.mark.parametrize(
        ('line', 'says'),
        [
            ('', r'no command: the line has no words'),
            ('--', r'no command: the line has no words'),
            ('frobnicate', r"no command 'frobnicate'"),
            ('fleet', r'fleet: which fleet\?'),
            ('fleet f1', r'fleet f1: then what\? buy \| dock \| jump \| mine \| sell'),
            ('fleet f1 jump', r'fleet f1 jump: which system\?'),
            ('fleet f1 jump nearest', r'fleet f1 jump nearest: which ore\?'),
            ('fleet f1 progrms', r"no command 'fleet f1 progrms'"),
            ('log 40 50', r"log 40: '50' is left over"),
            ('fleet f1 dock nearest now', r"fleet f1 dock nearest: 'now' is left over"),
            ('--yes log', r'--yes comes before a command: a flag follows the first word'),
            ('say "hello', r'the quote at column 5 is never closed'),
            ('log --n 3', r'no command takes --n'),
            ('log --into f2', r'log takes no --into `log \[<n>\]`'),
            ('fleet f1 mine --into f2', r'fleet f1 mine takes no --into `fleet <fleet> mine \[--for <for>\]`'),
            ('fleets merge f1', r'fleets merge f1 needs --into `fleets merge f1 --into <into>`'),
            ('fleet f1 mine --for', r'--for needs a value'),
            ('fleet f1 mine --for --yes', r'--for needs a value'),
            ('fleet f1 mine --for -- 90', r'--for needs a value'),
            ('fleet f1 mine --for 1 --for 2', r'--for is given twice'),
            ('fleets merge f1 --into f2 --quiet=no', r'--quiet takes nothing after it'),
            ('fleets merge f1 --into f2 --quiet --quiet', r'--quiet is given twice'),
            ('log --yes=no', r'--yes takes nothing after it'),
            ('log --json --json', r'--json is given twice'),
        ],
    )
    def test_a_line_that_doesn_t_read_says_why(self, tree, line, says):
        with pytest.raises(ReadError, match=says):
            tree.walk(line)

    def test_several_words_need_one(self, tree):
        with pytest.raises(ReadError, match=r'fleet f1 sell: which goods\?'):
            tree.walk('fleet f1 sell')


def _refusal(tree: Tree, line: str, *, load: bool = False) -> ReadError:
    with pytest.raises(ReadError) as caught:
        tree.read(line) if load else tree.walk(line)
    return caught.value


class TestRefusalsAsData:
    # What each refusal says besides its message: where it stands, its hint and what may have been meant.
    @pytest.mark.parametrize(
        ('line', 'column', 'word'),
        [
            ('', 0, None),
            ('say "hello', 4, None),
            ('--yes log', 0, '--yes'),
            ('log --fro 3', 4, '--fro'),
            ('fleets merge f1 --into f2 --quiet=no', 26, '--quiet=no'),
            ('fleet f1 mien', 9, 'mien'),
            ('log 40 50', 7, '50'),
            ('fleet f1 jump', 13, None),
            ('fleet f1 mine --into f2', 14, '--into'),
            ('fleet f1 mine --for 1m --for 2m', 23, '--for'),
            ('fleets merge f1', 15, None),
        ],
    )
    def test_where_it_stands(self, tree, line, column, word):
        found = _refusal(tree, line)
        assert (found.line, found.column, found.word, found.kind) == (line, column, word, 'usage')

    @pytest.mark.parametrize(
        ('line', 'hint'),
        [
            ('say "hello', 'say "hello"'),
            ('fleet', 'fleet <fleet> …'),
            ('fleet f1 jump', 'fleet f1 jump <system>'),
            ('fleet f1 jump nearest', 'fleet f1 jump nearest <ore>'),
            ('log 40 50', 'log [<n>]'),
            ('log --into f2', 'log [<n>]'),
            ('fleet f1 mine --for', '--for <for>'),
            ('fleets merge f1 --quiet', 'fleets merge f1 --quiet --into <into>'),
        ],
    )
    def test_a_hint_says_how_to_say_it(self, tree, line, hint):
        found = _refusal(tree, line)
        assert found.hint == hint
        assert str(found).endswith(f' `{hint}`')

    @pytest.mark.parametrize(
        ('line', 'suggestions'),
        [
            ('flet f1 mine', ('fleet', 'fleets')),
            ('fleet f1 mien', ('mine',)),
            ('fleet f1 xyz', ('buy', 'dock', 'jump', 'mine', 'sell')),
            ('fleet f1', ('buy', 'dock', 'jump', 'mine', 'sell')),
            ('log --fro 3', ('--for',)),
            ('log --jsno', ('--json',)),
        ],
    )
    def test_what_may_have_been_meant(self, tree, line, suggestions):
        assert _refusal(tree, line).suggestions == suggestions

    def test_did_you_mean_is_in_the_text_and_a_list_isn_t_doubled(self, tree):
        assert str(_refusal(tree, 'log --fro 3')) == 'no command takes --fro; did you mean --for?'
        assert str(_refusal(tree, 'fleet f1 xyz')) == "no command 'fleet f1 xyz': buy | dock | jump | mine | sell"

    def test_the_field_where_the_walk_knows_it(self, tree):
        assert _refusal(tree, 'log many').field == 'n'
        assert _refusal(tree, 'fleet f1 mine --for soon').field == 'for_'
        assert _refusal(tree, 'fleets merge f1').field == 'into'
        assert _refusal(tree, 'fleet').field is None

    def test_as_data(self, tree):
        assert _refusal(tree, 'fleet f1 jump').to_json() == {
            'error': 'usage',
            'message': 'fleet f1 jump: which system? `fleet f1 jump <system>`',
            'line': 'fleet f1 jump',
            'column': 13,
            'hint': 'fleet f1 jump <system>',
        }


class TestSearedsRefusals:
    # A value seared refuses comes back as the word that gave it.
    def test_a_slot_s_value(self, tree):
        found = _refusal(tree, 'log 0', load=True)
        assert str(found) == 'log {n}: must be >= 1, got 0'
        assert (found.kind, found.column, found.word, found.field) == ('validation', 4, '0', 'n')
        assert isinstance(found.__cause__, parsed.ValidationError)

    def test_a_flag_s_value(self, tree):
        found = _refusal(tree, 'handheld connect dock r7 --host h --port 70000', load=True)
        assert str(found) == '--port: must be <= 65535, got 70000'
        assert (found.column, found.word, found.field) == (41, '70000', 'port')

    def test_one_of_a_list_s_words(self):
        tag = _one('tag {ns}', ns=parsed.Int(many=True, required=True, ge=1))
        found = _refusal(tag, 'tag 3 2 0 4', load=True)
        assert (found.column, found.word) == (8, '0')

    def test_one_of_a_list_s_flags(self):
        tag = _one('tag', ns=parsed.Int(many=True, default_factory=list, ge=1))
        found = _refusal(tag, 'tag --ns 2 --ns 0', load=True)
        assert (found.column, found.word) == (16, '0')

    def test_the_rest_of_the_line_from_its_first_word(self):
        note = _one('note {text**}', text=parsed.Str(required=True, max_length=5))
        found = _refusal(note, 'note far too long', load=True)
        assert (found.column, found.word, found.field) == (5, 'far too long', 'text')
        assert found.message.startswith('note {text**}: ')

    def test_a_pattern(self):
        code = _one('code {c}', c=parsed.Str(required=True, pattern='[a-z]+'))
        found = _refusal(code, 'code AB1', load=True)
        assert (found.kind, found.word) == ('validation', 'AB1')


class TestFarlandiasCases:
    """farlandia's own reading cases (``tests/client/test_tree.py``), on this fixture's commands.

    Lifted: words, slots and flags anywhere after the first word; a slot of several words; a span of time and true or
    false; the refusals that are the walk's, with did-you-mean and a usage for a hint. Changed on purpose: ``--quiet
    yes`` reads ``yes`` as a word, since the tree knows ``--quiet`` is a switch; a flag the command doesn't take says
    so with the command's usage (``takes no --into `fleet <fleet> mine [--for <for>]```), and a required flag left out
    with the line it's missing from. Later: a share's ``off`` or percent (a kind of its own), names alone (names),
    chains and subjects, ``--help``, completion, schemas and ``render``.
    """

    def test_words_slots_and_flags_anywhere_after_the_first_word(self, tree):
        assert tree.read('fleets start true') == farlandia.FleetsStart(on=True)
        assert tree.read('fleets merge --into f2 f1') == farlandia.FleetsMerge(fleet='f1', into='f2')
        assert tree.read('fleets merge f1 --into f2 --quiet') == farlandia.FleetsMerge(
            fleet='f1', into='f2', quiet=True
        )
        assert tree.read('fleet f1 sell s1 s2 s3').goods == ['s1', 's2', 's3']

    @pytest.mark.parametrize(
        ('line', 'says'),
        [
            ('', 'no command'),
            ('fleet', 'which fleet'),
            ('fleet f1 progrms', "no command 'fleet f1 progrms'"),
            ('fleet f1 jump', 'which system'),
            ('fleet f1 mine --into f2', 'takes no --into `fleet <fleet> mine \\[--for <for>\\]`'),
            ('fleets merge f1', '--into'),
            ('fleet f1 mine --for 1h --for 2h', 'given twice'),
            ('fleet f1 mine --for', 'needs a value'),
            ('fleet f1 mine --for soon', 'not a span of time'),
            ('fleet f1', 'then what'),
            ('fleets start maybe', 'true or false'),
            ('fleet f1 dock nearest now', 'left over'),
        ],
    )
    def test_mistakes_say_how_to_say_it(self, tree, line, says):
        with pytest.raises(ReadError, match=says):
            tree.walk(line)

    def test_did_you_mean(self, tree):
        with pytest.raises(ReadError, match=r"no command 'fleet f1 mien'; did you mean mine\?"):
            tree.walk('fleet f1 mien')

    def test_a_switch_takes_no_word_so_the_word_is_left_over(self, tree):
        with pytest.raises(ReadError, match=r"fleets merge f1: 'yes' is left over"):
            tree.walk('fleets merge f1 --into f2 --quiet yes')
