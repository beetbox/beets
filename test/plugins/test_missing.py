import uuid

import pytest

from beets.library import Album
from beets.test.helper import IOMixin, PluginMixin, TestHelper


@pytest.fixture
def helper(request):
    helper = TestHelper()
    helper.setup_beets()

    request.instance.lib = helper.lib

    yield

    helper.teardown_beets()


@pytest.mark.usefixtures("helper")
class TestMissingAlbums(IOMixin, PluginMixin):
    plugin = "missing"
    album_in_lib = Album(
        album="Album",
        albumartist="Artist",
        mb_albumartistid=str(uuid.uuid4()),
        mb_albumid="album",
    )

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
                    reason=(
                        "Album in lib must not be reported as missing."
                        " Needs fixing."
                    )
                ),
                id="not missing",
            ),
        ],
    )
    def test_missing_artist_albums(
        self, requests_mock, release_from_mb, expected_output
    ):
        self.lib.add(self.album_in_lib)
        requests_mock.get(
            f"/ws/2/release-group?artist={self.album_in_lib.mb_albumartistid}",
            json={"release-groups": [release_from_mb]},
        )

        with self.configure_plugin({}):
            assert self.run_with_output("missing", "--album") == expected_output
