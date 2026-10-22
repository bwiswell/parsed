"""Tests for ``parsed/_walk/_words.py``: a line split into words, double quotes holding spaces."""

import pytest

from parsed._walk import Token, split
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


class TestQuoted:
    @pytest.mark.parametrize(('line', 'quoted'), [('nearest', False), ('"nearest"', True), ('a"b"', True)])
    def test_any_quote_makes_a_word_a_value(self, line, quoted):
        assert split(line)[0].quoted is quoted

    def test_an_empty_word_is_quoted(self):
        assert split('""')[0].quoted
