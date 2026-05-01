import pytest

from beets import logging
from beets.library import Item
from beets.test.helper import TestHelper
from beetsplug._utils.playcount import (
    get_items,
    process_track,
    update_play_counts,
)

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
    def track(self, **overrides):
        return {
            "mbid": "",
            "artist": "Artist",
            "name": "Song",
            "playcount": 1,
            **overrides,
        }

    def get_playcount(self, item_id, source="lastfm"):
        field = f"{source}_play_count"
        return int(self.lib.get_item(item_id).get(field, 0))

    def add_item(
        self,
        *,
        title="Song",
        artist="Artist",
        album="Album",
        mb_trackid="",
        play_count=None,
        source="lastfm",
    ):
        item = Item(
            title=title,
            artist=artist,
            album=album,
            mb_trackid=mb_trackid,
        )
        self.lib.add(item)

        if play_count is not None:
            item[f"{source}_play_count"] = play_count
            item.store()

        return item

    @pytest.mark.parametrize(
        "item_kwargs, track_kwargs",
        [
            pytest.param(
                {"title": "Song", "artist": "Artist"},
                {"playcount": 7},
                id="artist-and-title",
            ),
            pytest.param(
                {
                    "title": "Different Song",
                    "artist": "Different Artist",
                    "mb_trackid": "track-id",
                },
                {"mbid": "track-id", "playcount": 5},
                id="musicbrainz-track-id",
            ),
            pytest.param(
                {
                    "title": "Song",
                    "artist": "Different Artist",
                    "album": "Album",
                },
                {"album": "Album", "playcount": 3},
                id="album-and-title",
            ),
            pytest.param(
                {"title": "Don\u2019t Stop", "artist": "Artist"},
                {"name": "Don't Stop", "playcount": 11},
                id="apostrophe-normalized",
            ),
        ],
    )
    def test_get_items_matches_supported_query_paths(
        self, item_kwargs, track_kwargs
    ):
        item = self.add_item(**item_kwargs)
        matched_ids = [
            matched.id
            for matched in get_items(
                self.lib, self.track(**track_kwargs), self.log
            )
        ]

        assert matched_ids == [item.id]

    def test_process_track_updates_every_matching_song(self):
        first = self.add_item(
            title="Song",
            artist="Artist",
            album="First Album",
            play_count=1,
        )
        second = self.add_item(
            title="Song",
            artist="Artist",
            album="Second Album",
            play_count=9,
        )

        assert (
            process_track(
                self.lib,
                self.track(playcount=0),
                self.log,
                "lastfm",
            )
            is True
        )

        assert self.get_playcount(first.id) == 0
        assert self.get_playcount(second.id) == 0

    def test_process_track_returns_false_when_nothing_matches(self):
        assert (
            process_track(
                self.lib,
                self.track(
                    artist="Missing Artist",
                    name="Missing Song",
                    album="Missing Album",
                    playcount=4,
                ),
                self.log,
                "lastfm",
            )
            is False
        )

    def test_process_track_updates_requested_source_field(self):
        new_count = 6
        item = self.add_item(play_count=1, source="lastfm")

        assert (
            process_track(
                self.lib,
                self.track(playcount=new_count),
                self.log,
                "listenbrainz",
            )
            is True
        )

        assert self.get_playcount(item.id, "lastfm") == 1
        assert self.get_playcount(item.id, "listenbrainz") == new_count

    @pytest.mark.parametrize(
        "tracks, expected_counts, expected_summary, expected_playcount",
        [
            pytest.param([], (0, 0), None, None, id="empty-page"),
            pytest.param(
                [
                    {
                        "artist": "Artist",
                        "name": "Known Song",
                        "playcount": 8,
                    },
                    {
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
    def test_update_play_counts_counts_and_logs_summary(
        self,
        tracks,
        expected_counts,
        expected_summary,
        expected_playcount,
        caplog,
    ):
        item = self.add_item(
            title="Known Song",
            artist="Artist",
            play_count=1,
        )

        with caplog.at_level("DEBUG", logger=LOGGER_NAME):
            assert (
                update_play_counts(
                    self.lib,
                    [self.track(**track) for track in tracks],
                    self.log,
                    "lastfm",
                )
                == expected_counts
            )

        assert any(
            f"Received {len(tracks)} tracks in this page, processing..." in msg
            for msg in caplog.messages
        )
        if expected_summary is None:
            assert not any("Acquired" in msg for msg in caplog.messages)
        else:
            assert expected_summary in caplog.text
            assert self.get_playcount(item.id) == expected_playcount
