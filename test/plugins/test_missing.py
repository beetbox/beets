import uuid

import pytest

from beets.library import Album
from beets.test.helper import PluginMixin, TestHelper


class TestMissingAlbums(PluginMixin, TestHelper):
    plugin = "missing"
    album_in_lib = Album(
        album="Album",
        albumartist="Artist",
        mb_albumartistid=str(uuid.uuid4()),
        mb_albumid="album",
    )

    @pytest.fixture(autouse=True)
    def helper(self):
        self.setup_beets()
        self.lib.add(self.album_in_lib)

        yield self

        self.teardown_beets()

    @pytest.mark.parametrize(
        "release_from_mb,expected_output",
        [
            pytest.param(
                {"id": "other", "title": "Other Album"},
                "Artist - Other Album\n",
                id="missing",
            ),
            pytest.param(
                {"id": album_in_lib.mb_albumid, "title": album_in_lib.album},
                "",
                marks=pytest.mark.xfail(
                    reason="album in lib should not be reported as missing. Needs fixing."
                ),
                id="not missing",
            ),
        ],
    )
    def test_missing_artist_albums(
        self, monkeypatch, helper, release_from_mb, expected_output
    ):
        monkeypatch.setattr(
            "musicbrainzngs.browse_release_groups",
            lambda **__: {"release-group-list": [release_from_mb]},
        )

        assert helper.run_with_output("missing", "--album") == expected_output
