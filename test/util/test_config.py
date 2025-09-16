import pytest

from beets.util.config import sanitize_choices, sanitize_pairs


@pytest.mark.parametrize(
    "input_choices, valid_choices, expected",
    [
        (["A", "Z"], ("A", "B"), ["A"]),
        (["A", "A"], ("A"), ["A"]),
        (["D", "*", "A"], ("A", "B", "C", "D"), ["D", "B", "C", "A"]),
    ],
)
def test_sanitize_choices(input_choices, valid_choices, expected):
    assert sanitize_choices(input_choices, valid_choices) == expected


def test_sanitize_pairs():
    assert sanitize_pairs(
        [
            ("foo", "baz bar"),
            ("foo", "baz bar"),
            ("key", "*"),
            ("*", "*"),
            ("discard", "bye"),
        ],
        [
            ("foo", "bar"),
            ("foo", "baz"),
            ("foo", "foobar"),
            ("key", "value"),
        ],
    ) == [
        ("foo", "baz"),
        ("foo", "bar"),
        ("key", "value"),
        ("foo", "foobar"),
    ]
