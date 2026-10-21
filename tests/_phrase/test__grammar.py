"""Tests for ``parsed/_phrase/_grammar.py``: a phrase's words and slots."""

from __future__ import annotations

import pytest

from parsed._phrase._grammar import Phrase, Slot, Word, parse


class TestReading:
    def test_words_and_slots_in_order(self):
        found = parse('fleet {fleet} mine')
        assert found == Phrase(text='fleet {fleet} mine', parts=(Word('fleet'), Slot('fleet'), Word('mine')))
        assert found.slots == (Slot('fleet'),)
        assert found.words == ('fleet', 'mine')

    def test_the_rest_of_the_line(self):
        assert parse('say {message**}').slots == (Slot('message', rest=True),)

    def test_spaces_are_one_separator(self):
        assert parse('  fleet   {fleet}\tmine ').text == 'fleet {fleet} mine'

    @pytest.mark.parametrize('word', ['jump', 'set-up', 'take_off', 'b2', '2fa'])
    def test_a_word_is_lowercase_letters_digits_dashes_and_underscores(self, word):
        assert parse(word).words == (word,)

    def test_a_slot_takes_a_python_name(self):
        assert parse('mine {for_} {_x} {Ship2}').slots == (Slot('for_'), Slot('_x'), Slot('Ship2'))


class TestRefusals:
    @pytest.mark.parametrize(
        ('text', 'message'),
        [
            ('', 'a phrase has words'),
            ('   ', 'a phrase has words'),
            ('{fleet} mine', r'a phrase begins with a word, not the slot \{fleet\}'),
            ('fleet {fleet} {fleet}', r'\{fleet\} appears twice'),
            ('say {message**} now', r'\{message\*\*\} takes the rest of the line, so it comes last'),
            ('fleet {fleet mine', r"'\{fleet' is neither a word nor a slot"),
            ('fleet x{fleet}', r"'x\{fleet\}' is neither a word nor a slot"),
            ('fleet {1x}', r"'\{1x\}' is neither a word nor a slot"),
            ('fleet {fleet*}', r"'\{fleet\*\}' is neither a word nor a slot"),
            ('Fleet mine', r"'Fleet' is not a word: a word is lowercase letters, digits, '-' and '_'"),
            ('fleet/mine', r"'fleet/mine' is not a word"),
            ('fleet --for', r"'--for' is not a word"),
            ('fleet *', r"'\*' is not a word"),
        ],
    )
    def test_each_says_why(self, text, message):
        with pytest.raises(ValueError, match=message):
            parse(text)
