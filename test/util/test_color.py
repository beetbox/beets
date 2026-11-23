import pytest

from beets.util.color import color_split, uncolorize


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param("test", "test", id="plain_text"),
        pytest.param("\x1b[31mtest\x1b[39;49;00m", "test", id="colored_text"),
        pytest.param(
            "\x1b[31mtest\x1b[39;49;00m test",
            "test test",
            id="colored_text_with_spaced_suffix",
        ),
        pytest.param(
            "\x1b[31mtest\x1b[39;49;00mtest",
            "testtest",
            id="colored_text_with_adjacent_suffix",
        ),
        pytest.param(
            "test \x1b[31mtest\x1b[39;49;00m test",
            "test test test",
            id="colored_text_between_plain_text",
        ),
    ],
)
def test_uncolorize(text, expected):
    assert uncolorize(text) == expected


@pytest.mark.parametrize(
    "text, index, expected",
    [
        pytest.param("test", 5, ("test", ""), id="index_beyond_plain_text"),
        pytest.param(
            "\x1b[31mtest\x1b[39;49;00m",
            3,
            ("\x1b[31mtes\x1b[39;49;00m", "\x1b[31mt\x1b[39;49;00m"),
            id="split_preserves_color",
        ),
    ],
)
def test_color_split(text, index, expected):
    assert color_split(text, index) == expected
