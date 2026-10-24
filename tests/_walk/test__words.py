"""Tests for ``parsed/_walk/_words.py``: a line split into words, double quotes holding spaces, and written back."""

import pytest

from parsed._walk import Token, split
from parsed._walk._words import word
from parsed.errors import ReadError


def _texts(line):
    return [token.text for token in split(line)]


class TestSplitting:
    def test_on_whitespace_with_where_each_starts(self):
        assert split('  fleet  f1\tmine ') == [
            Token(text='fleet', start=2, raw='fleet'),
            Token(text='f1', start=9, raw='f1'),
            Token(text='mine', start=12, raw='mine'),
        ]

    def test_an_empty_line_has_no_words(self):
        assert split('') == []
        assert split(' \t ') == []

    def test_double_quotes_hold_spaces(self):
        found = split('fleet "Vruba\'a Belt 1" mine')
        assert [token.text for token in found] == ['fleet', "Vruba'a Belt 1", 'mine']
        assert found[1] == Token(text="Vruba'a Belt 1", start=6, raw='"Vruba\'a Belt 1"')

    def test_a_quote_anywhere_in_a_word(self):
        assert _texts('belt-"1 a" x') == ['belt-1 a', 'x']
        assert _texts('--label="north dock"') == ['--label=north dock']

    def test_an_empty_word(self):
        assert split('say ""') == [Token(text='say', start=0, raw='say'), Token(text='', start=4, raw='""')]

    def test_a_single_quote_is_a_plain_character(self):
        assert _texts("Vruba'a belt") == ["Vruba'a", 'belt']

    def test_each_raw_word_is_the_line_s_own(self):
        line = 'fleet  "Vruba\'a Belt 1"  --label="a b" ""'
        for token in split(line):
            assert line[token.start : token.start + len(token.raw)] == token.raw

    def test_an_open_quote_is_refused(self):
        with pytest.raises(ReadError, match=r'the quote at column 7 is never closed: "Vruba'):
            split('fleet "Vruba mine')


class TestTheEscape:
    # A backslash right before a double quote makes it a plain character, quoted or not; any other backslash is itself.
    def test_a_double_quote_in_a_word(self):
        assert _texts(r'call t --args "{\"station\": \"s1\"}"') == ['call', 't', '--args', '{"station": "s1"}']
        assert _texts(r'--until name=\"40\"') == ['--until', 'name="40"']
        assert _texts(r'\"40\" x') == ['"40"', 'x']

    def test_its_raw_word_is_the_line_s_own(self):
        line = r'say "a \"b\" c" d\"e'
        found = split(line)
        assert [token.raw for token in found] == ['say', r'"a \"b\" c"', r'd\"e']
        assert all(line[token.start : token.start + len(token.raw)] == token.raw for token in found)

    def test_any_other_backslash_is_itself(self):
        assert _texts(r'C:\temp a\d "C:\My Dir" \ x\\y') == ['C:\\temp', 'a\\d', 'C:\\My Dir', '\\', 'x\\\\y']

    def test_a_backslash_before_an_escape_is_itself(self):
        assert _texts(r'a\\"b') == ['a\\"b']

    def test_an_escaped_quote_opens_nothing(self):
        assert _texts(r'say \"hi') == ['say', '"hi']
        with pytest.raises(ReadError, match=r'the quote at column 1 is never closed'):  # the one reading it changes
            split(r'"C:\dir\"')

    def test_a_word_holding_one_is_a_value(self):
        assert split(r'\"nearest\"')[0].quoted


class TestWritingAWord:
    # Any string, written as a word, reads back to itself.
    @pytest.mark.parametrize(
        ('text', 'said'),
        [
            ('mine', 'mine'),
            ('Vesta Ring', '"Vesta Ring"'),
            ('', '""'),
            ('{"station": "s1"}', r'"{\"station\": \"s1\"}"'),
            ('name="40"', r'name=\"40\"'),
            ('"', r'\"'),
            ('C:\\temp', r'C:\temp'),
            ('C:\\My Dir\\', '"C:\\My Dir"\\'),  # the backslash after the closing quote, so it escapes none
            ('a\\"b', r'a\\"b'),
            ('{"path": "C:\\\\x y\\\\"}', r'"{\"path\": \"C:\\x y\\\"}"'),
        ],
    )
    def test_as_a_line_says_it(self, text, said):
        assert word(text) == said
        assert [token.text for token in split(said)] == [text]

    def test_quoted_where_asked(self):
        assert word('nearest', quoted=True) == '"nearest"'
        assert word('--loud', quoted=True) == '"--loud"'
        assert word('a"b', quoted=True) == r'"a\"b"'


class TestPartial:
    # A line being typed: a quote left open holds the last word as far as it goes.
    def test_an_open_quote_holds_the_last_word(self):
        assert split('dock "Vruba\'a ', partial=True) == [
            Token(text='dock', start=0, raw='dock'),
            Token(text="Vruba'a ", start=5, raw='"Vruba\'a '),
        ]

    def test_a_closed_line_splits_as_ever(self):
        assert split('dock vesta', partial=True) == split('dock vesta')


class TestQuoted:
    @pytest.mark.parametrize(('line', 'quoted'), [('nearest', False), ('"nearest"', True), ('a"b"', True)])
    def test_any_quote_makes_a_word_a_value(self, line, quoted):
        assert split(line)[0].quoted is quoted

    def test_an_empty_word_is_quoted(self):
        assert split('""')[0].quoted
