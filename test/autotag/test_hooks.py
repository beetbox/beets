import pytest

from beets.autotag.hooks import Info


@pytest.mark.parametrize(
    "genre, expected_genres",
    [
        ("Rock", ("Rock",)),
        ("Rock; Alternative", ("Rock", "Alternative")),
    ],
)
def test_genre_deprecation(genre, expected_genres):
    with pytest.warns(
        DeprecationWarning, match="The 'genre' parameter is deprecated"
    ):
        assert tuple(Info(genre=genre).genres) == expected_genres
