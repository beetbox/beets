import pytest

from beets.util.musictheory import (
    CIRCLE_OF_FIFTHS,
    harmonic_sort_key,
    key_spellings,
    normalize_key,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Gmin", "Gm"),
        ("Gmaj", "G"),
        ("G minor", "Gm"),
        ("G major", "G"),
        ("Abmin", "G#m"),
        ("Bbmaj", "A#"),
        ("F#min", "F#m"),
        ("Am", "Am"),
    ],
)
def test_normalize_key(raw, expected):
    assert normalize_key(raw) == expected


def test_key_spellings_normalize_to_their_position():
    spellings = key_spellings()

    assert set(spellings.values()) == set(range(len(CIRCLE_OF_FIFTHS)))
    for spelling, position in spellings.items():
        assert normalize_key(spelling) == CIRCLE_OF_FIFTHS[position]


def test_harmonic_sort_key_uses_the_spelling_table():
    # The SQL sort matches against key_spellings(), so the Python fallback
    # must rank exactly the same spellings and treat all others as unknown.
    for spelling, position in key_spellings().items():
        assert harmonic_sort_key(spelling.upper()) == position
    for unrecognized in ("G-minor", "G  minor", None, ""):
        assert harmonic_sort_key(unrecognized) == len(CIRCLE_OF_FIFTHS)
