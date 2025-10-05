import re

import pytest

from beets.autotag import AlbumInfo, TrackInfo
from beets.autotag.distance import (
    Distance,
    distance,
    string_dist,
    track_distance,
)
from beets.library import Item
from beets.test.helper import ConfigMixin

_p = pytest.param


class TestDistance:
    @pytest.fixture(scope="class")
    def config(self):
        return ConfigMixin().config

    @pytest.fixture
    def dist(self, config):
        config["match"]["distance_weights"]["data_source"] = 2.0
        config["match"]["distance_weights"]["album"] = 4.0
        config["match"]["distance_weights"]["medium"] = 2.0

        Distance.__dict__["_weights"].cache = {}

        return Distance()

    def test_add(self, dist):
        dist.add("add", 1.0)

        assert dist._penalties == {"add": [1.0]}

    @pytest.mark.parametrize(
        "key, args_with_expected",
        [
            (
                "equality",
                [
                    (("ghi", ["abc", "def", "ghi"]), [0.0]),
                    (("xyz", ["abc", "def", "ghi"]), [0.0, 1.0]),
                    (("abc", re.compile(r"ABC", re.I)), [0.0, 1.0, 0.0]),
                ],
            ),
            ("expr", [((True,), [1.0]), ((False,), [1.0, 0.0])]),
            (
                "number",
                [
                    ((1, 1), [0.0]),
                    ((1, 2), [0.0, 1.0]),
                    ((2, 1), [0.0, 1.0, 1.0]),
                    ((-1, 2), [0.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
                ],
            ),
            (
                "priority",
                [
                    (("abc", "abc"), [0.0]),
                    (("def", ["abc", "def"]), [0.0, 0.5]),
                    (("gh", ["ab", "cd", "ef", re.compile("GH", re.I)]), [0.0, 0.5, 0.75]),  # noqa: E501
                    (("xyz", ["abc", "def"]), [0.0, 0.5, 0.75, 1.0]),
                ],
            ),
            (
                "ratio",
                [
                    ((25, 100), [0.25]),
                    ((10, 5), [0.25, 1.0]),
                    ((-5, 5), [0.25, 1.0, 0.0]),
                    ((5, 0), [0.25, 1.0, 0.0, 0.0]),
                ],
            ),
            (
                "string",
                [
                    (("abc", "bcd"), [2 / 3]),
                    (("abc", None), [2 / 3, 1]),
                    ((None, None), [2 / 3, 1, 0]),
                ],
            ),
        ],
    )  # fmt: skip
    def test_add_methods(self, dist, key, args_with_expected):
        method = getattr(dist, f"add_{key}")
        for arg_set, expected in args_with_expected:
            method(key, *arg_set)
            assert dist._penalties[key] == expected

    def test_distance(self, dist):
        dist.add("album", 0.5)
        dist.add("media", 0.25)
        dist.add("media", 0.75)

        assert dist.distance == 0.5
        assert dist.max_distance == 6.0
        assert dist.raw_distance == 3.0

        assert dist["album"] == 1 / 3
        assert dist["media"] == 1 / 6

    def test_operators(self, dist):
        dist.add("data_source", 0.0)
        dist.add("album", 0.5)
        dist.add("medium", 0.25)
        dist.add("medium", 0.75)
        assert len(dist) == 2
        assert list(dist) == [("album", 0.2), ("medium", 0.2)]
        assert dist == 0.4
        assert dist < 1.0
        assert dist > 0.0
        assert dist - 0.4 == 0.0
        assert 0.4 - dist == 0.0
        assert float(dist) == 0.4

    def test_penalties_sort(self, dist):
        dist.add("album", 0.1875)
        dist.add("medium", 0.75)
        assert dist.items() == [("medium", 0.25), ("album", 0.125)]

        # Sort by key if distance is equal.
        dist = Distance()
        dist.add("album", 0.375)
        dist.add("medium", 0.75)
        assert dist.items() == [("album", 0.25), ("medium", 0.25)]

    def test_update(self, dist):
        dist1 = dist
        dist1.add("album", 0.5)
        dist1.add("media", 1.0)

        dist2 = Distance()
        dist2.add("album", 0.75)
        dist2.add("album", 0.25)
        dist2.add("media", 0.05)

        dist1.update(dist2)

        assert dist1._penalties == {
            "album": [0.5, 0.75, 0.25],
            "media": [1.0, 0.05],
        }


class TestTrackDistance:
    @pytest.fixture(scope="class")
    def info(self):
        return TrackInfo(title="title", artist="artist")

    @pytest.mark.parametrize(
        "title, artist, expected_penalty",
        [
            _p("title", "artist", False, id="identical"),
            _p("title", "Various Artists", False, id="tolerate-va"),
            _p("title", "different artist", True, id="different-artist"),
            _p("different title", "artist", True, id="different-title"),
        ],
    )
    def test_track_distance(self, info, title, artist, expected_penalty):
        item = Item(artist=artist, title=title)

        assert (
            bool(track_distance(item, info, incl_artist=True))
            == expected_penalty
        )


class TestAlbumDistance:
    @pytest.fixture(scope="class")
    def items(self):
        return [
            Item(
                title=title,
                track=track,
                artist="artist",
                album="album",
                length=1,
            )
            for title, track in [("one", 1), ("two", 2), ("three", 3)]
        ]

    @pytest.fixture
    def get_dist(self, items):
        def inner(info: AlbumInfo):
            return distance(items, info, dict(zip(items, info.tracks)))

        return inner

    @pytest.fixture
    def info(self, items):
        return AlbumInfo(
            artist="artist",
            album="album",
            tracks=[
                TrackInfo(
                    title=i.title,
                    artist=i.artist,
                    index=i.track,
                    length=i.length,
                )
                for i in items
            ],
            va=False,
        )

    def test_identical_albums(self, get_dist, info):
        assert get_dist(info) == 0

    def test_incomplete_album(self, get_dist, info):
        info.tracks.pop(2)

        assert 0 < float(get_dist(info)) < 0.2

    def test_overly_complete_album(self, get_dist, info):
        info.tracks.append(
            Item(index=4, title="four", artist="artist", length=1)
        )

        assert 0 < float(get_dist(info)) < 0.2

    @pytest.mark.parametrize("va", [True, False])
    def test_albumartist(self, get_dist, info, va):
        info.artist = "another artist"
        info.va = va

        assert bool(get_dist(info)) is not va

    def test_comp_no_track_artists(self, get_dist, info):
        # Some VA releases don't have track artists (incomplete metadata).
        info.artist = "another artist"
        info.va = True
        for track in info.tracks:
            track.artist = None

        assert get_dist(info) == 0

    def test_comp_track_artists_do_not_match(self, get_dist, info):
        info.va = True
        info.tracks[0].artist = "another artist"

        assert get_dist(info) != 0

    def test_tracks_out_of_order(self, get_dist, info):
        tracks = info.tracks
        tracks[1].title, tracks[2].title = tracks[2].title, tracks[1].title

        assert 0 < float(get_dist(info)) < 0.2

    def test_two_medium_release(self, get_dist, info):
        info.tracks[0].medium_index = 1
        info.tracks[1].medium_index = 2
        info.tracks[2].medium_index = 1

        assert get_dist(info) == 0


class TestStringDistance:
    @pytest.mark.parametrize(
        "string1, string2",
        [
            ("Some String", "Some String"),
            ("Some String", "Some.String!"),
            ("Some String", "sOME sTring"),
            ("My Song (EP)", "My Song"),
            ("The Song Title", "Song Title, The"),
            ("A Song Title", "Song Title, A"),
            ("An Album Title", "Album Title, An"),
            ("", ""),
            ("Untitled", "[Untitled]"),
            ("And", "&"),
            ("\xe9\xe1\xf1", "ean"),
        ],
    )
    def test_matching_distance(self, string1, string2):
        assert string_dist(string1, string2) == 0.0

    def test_different_distance(self):
        assert string_dist("Some String", "Totally Different") != 0.0

    @pytest.mark.parametrize(
        "string1, string2, reference",
        [
            ("XXX Band Name", "The Band Name", "Band Name"),
            ("One .Two.", "One (Two)", "One"),
            ("One .Two.", "One [Two]", "One"),
            ("My Song blah Someone", "My Song feat Someone", "My Song"),
        ],
    )
    def test_relative_weights(self, string1, string2, reference):
        assert string_dist(string2, reference) < string_dist(string1, reference)

    def test_solo_pattern(self):
        # Just make sure these don't crash.
        string_dist("The ", "")
        string_dist("(EP)", "(EP)")
        string_dist(", An", "")
