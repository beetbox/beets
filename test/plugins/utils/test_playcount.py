import pytest

from beets import logging
from beets.library import Item
from beets.test.helper import TestHelper, capture_log
from beetsplug._utils.playcount import get_items, process_track, process_tracks

LOGGER_NAME = "beets.test_playcount"


@pytest.fixture
def helper(request):
    helper = TestHelper()
    helper.setup_beets()

    request.instance.lib = helper.lib
    request.instance.log = logging.getLogger(LOGGER_NAME)
    request.instance.log.set_global_level(logging.DEBUG)

    yield helper

    helper.teardown_beets()


@pytest.mark.usefixtures("helper")
class TestPlayCount:
    def get_playcount(self, item_id):
        return int(self.lib.get_item(item_id).get("lastfm_play_count", 0))

    def add_item(
        self,
        *,
        title="Song",
        artist="Artist",
        album="Album",
        mb_trackid="",
        lastfm_play_count=None,
    ):
        item = Item(
            title=title,
            artist=artist,
            album=album,
            mb_trackid=mb_trackid,
        )
        self.lib.add(item)

        if lastfm_play_count is not None:
            item.lastfm_play_count = lastfm_play_count
            item.store()

        return item

    @pytest.mark.parametrize(
        "item_kwargs, track",
        [
            pytest.param(
                {"title": "Song", "artist": "Artist"},
                {
                    "mbid": "",
                    "artist": "Artist",
                    "name": "Song",
                    "playcount": 7,
                },
                id="artist-and-title",
            ),
            pytest.param(
                {
                    "title": "Different Song",
                    "artist": "Different Artist",
                    "mb_trackid": "track-id",
                },
                {
                    "mbid": "track-id",
                    "artist": "Artist",
                    "name": "Song",
                    "playcount": 5,
                },
                id="musicbrainz-track-id",
            ),
            pytest.param(
                {
                    "title": "Song",
                    "artist": "Different Artist",
                    "album": "Album",
                },
                {
                    "mbid": "",
                    "artist": "Artist",
                    "name": "Song",
                    "album": {"name": "Album"},
                    "playcount": 3,
                },
                id="album-and-title",
            ),
            pytest.param(
                {"title": "Don\u2019t Stop", "artist": "Artist"},
                {
                    "mbid": "",
                    "artist": "Artist",
                    "name": "Don't Stop",
                    "playcount": 11,
                },
                id="apostrophe-normalized",
            ),
        ],
    )
    def test_get_items_matches_supported_query_paths(self, item_kwargs, track):
        item = self.add_item(**item_kwargs)
        matched_ids = [
            matched.id for matched in get_items(self.lib, track, self.log)
        ]

        assert matched_ids == [item.id]

    def test_process_track_updates_every_matching_song(self):
        first = self.add_item(
            title="Song",
            artist="Artist",
            album="First Album",
            lastfm_play_count=1,
        )
        second = self.add_item(
            title="Song",
            artist="Artist",
            album="Second Album",
            lastfm_play_count=9,
        )

        assert (
            process_track(
                self.lib,
                {
                    "mbid": "",
                    "artist": "Artist",
                    "name": "Song",
                    "playcount": 0,
                },
                self.log,
            )
            is True
        )

        assert self.get_playcount(first.id) == 0
        assert self.get_playcount(second.id) == 0

    def test_process_track_returns_false_when_nothing_matches(self):
        assert (
            process_track(
                self.lib,
                {
                    "mbid": "",
                    "artist": "Missing Artist",
                    "name": "Missing Song",
                    "album": {"name": "Missing Album"},
                    "playcount": 4,
                },
                self.log,
            )
            is False
        )

    @pytest.mark.parametrize(
        "tracks, expected_counts, expected_summary, expected_playcount",
        [
            pytest.param([], (0, 0), None, None, id="empty-page"),
            pytest.param(
                [
                    {
                        "mbid": "",
                        "artist": "Artist",
                        "name": "Known Song",
                        "playcount": 8,
                    },
                    {
                        "mbid": "",
                        "artist": "Missing Artist",
                        "name": "Missing Song",
                        "playcount": 2,
                    },
                ],
                (1, 1),
                "Acquired 1/2 play-counts (1 unknown)",
                8,
                id="mixed-results",
            ),
        ],
    )
    def test_process_tracks_counts_and_logs_summary(
        self, tracks, expected_counts, expected_summary, expected_playcount
    ):
        item = self.add_item(
            title="Known Song",
            artist="Artist",
            lastfm_play_count=1,
        )

        with capture_log(LOGGER_NAME) as logs:
            assert process_tracks(self.lib, tracks, self.log) == expected_counts

        assert any(
            f"Received {len(tracks)} tracks in this page, processing..." in log
            for log in logs
        )
        if expected_summary is None:
            assert not any("Acquired" in log for log in logs)
        else:
            assert expected_summary in logs
            assert self.get_playcount(item.id) == expected_playcount
