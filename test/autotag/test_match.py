import pytest

from beets.autotag.match import _parse_search_terms_with_fallbacks


class TestSearchTermHandling:
    @pytest.mark.parametrize(
        "input_pairs, expected",
        [
            (
                (("A", "F1"), ("B", "F2")),
                ("A", "B"),
            ),
            (
                (("", "F1"), ("B", "F2")),
                ("", "B"),
            ),
            (
                (("", "F1"), ("", "F2")),
                ("F1", "F2"),
            ),
            (
                (("A", "F1"), (None, "F2")),
                ("A", ""),
            ),
            (
                ((None, "F1"), (None, "F2")),
                ("F1", "F2"),
            ),
        ],
    )
    def test_search_parsing(self, input_pairs, expected):
        result = _parse_search_terms_with_fallbacks(*input_pairs)
        assert result == expected

        # Should also apply for the reversed order of inputs
        reversed_pairs = tuple(reversed(input_pairs))
        reversed_expected = tuple(reversed(expected))
        reversed_result = _parse_search_terms_with_fallbacks(*reversed_pairs)
        assert reversed_result == reversed_expected
