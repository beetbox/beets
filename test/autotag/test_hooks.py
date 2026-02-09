import pytest

from beets.autotag.hooks import Info


def test_genre_deprecation():
    with pytest.warns(
        DeprecationWarning, match="The 'genre' parameter is deprecated"
    ):
        Info(genre="Rock")
