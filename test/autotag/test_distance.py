import re
import unittest

from beets import config
from beets.autotag import AlbumInfo, TrackInfo, match
from beets.autotag.distance import Distance, string_dist
from beets.library import Item
from beets.test.helper import BeetsTestCase


def _make_item(title, track, artist="some artist"):
    return Item(
        title=title,
        track=track,
        artist=artist,
        album="some album",
        length=1,
        mb_trackid="",
        mb_albumid="",
        mb_artistid="",
    )


def _make_trackinfo():
    return [
        TrackInfo(
            title="one", track_id=None, artist="some artist", length=1, index=1
        ),
        TrackInfo(
            title="two", track_id=None, artist="some artist", length=1, index=2
        ),
        TrackInfo(
            title="three",
            track_id=None,
            artist="some artist",
            length=1,
            index=3,
        ),
    ]


def _clear_weights():
    """Hack around the lazy descriptor used to cache weights for
    Distance calculations.
    """
    Distance.__dict__["_weights"].cache = {}


class DistanceTest(BeetsTestCase):
    def tearDown(self):
        super().tearDown()
        _clear_weights()

    def test_add(self):
        dist = Distance()
        dist.add("add", 1.0)
        assert dist._penalties == {"add": [1.0]}

    def test_add_equality(self):
        dist = Distance()
        dist.add_equality("equality", "ghi", ["abc", "def", "ghi"])
        assert dist._penalties["equality"] == [0.0]

        dist.add_equality("equality", "xyz", ["abc", "def", "ghi"])
        assert dist._penalties["equality"] == [0.0, 1.0]

        dist.add_equality("equality", "abc", re.compile(r"ABC", re.I))
        assert dist._penalties["equality"] == [0.0, 1.0, 0.0]

    def test_add_expr(self):
        dist = Distance()
        dist.add_expr("expr", True)
        assert dist._penalties["expr"] == [1.0]

        dist.add_expr("expr", False)
        assert dist._penalties["expr"] == [1.0, 0.0]

    def test_add_number(self):
        dist = Distance()
        # Add a full penalty for each number of difference between two numbers.

        dist.add_number("number", 1, 1)
        assert dist._penalties["number"] == [0.0]

        dist.add_number("number", 1, 2)
        assert dist._penalties["number"] == [0.0, 1.0]

        dist.add_number("number", 2, 1)
        assert dist._penalties["number"] == [0.0, 1.0, 1.0]

        dist.add_number("number", -1, 2)
        assert dist._penalties["number"] == [0.0, 1.0, 1.0, 1.0, 1.0, 1.0]

    def test_add_priority(self):
        dist = Distance()
        dist.add_priority("priority", "abc", "abc")
        assert dist._penalties["priority"] == [0.0]

        dist.add_priority("priority", "def", ["abc", "def"])
        assert dist._penalties["priority"] == [0.0, 0.5]

        dist.add_priority(
            "priority", "gh", ["ab", "cd", "ef", re.compile("GH", re.I)]
        )
        assert dist._penalties["priority"] == [0.0, 0.5, 0.75]

        dist.add_priority("priority", "xyz", ["abc", "def"])
        assert dist._penalties["priority"] == [0.0, 0.5, 0.75, 1.0]

    def test_add_ratio(self):
        dist = Distance()
        dist.add_ratio("ratio", 25, 100)
        assert dist._penalties["ratio"] == [0.25]

        dist.add_ratio("ratio", 10, 5)
        assert dist._penalties["ratio"] == [0.25, 1.0]

        dist.add_ratio("ratio", -5, 5)
        assert dist._penalties["ratio"] == [0.25, 1.0, 0.0]

        dist.add_ratio("ratio", 5, 0)
        assert dist._penalties["ratio"] == [0.25, 1.0, 0.0, 0.0]

    def test_add_string(self):
        dist = Distance()
        sdist = string_dist("abc", "bcd")
        dist.add_string("string", "abc", "bcd")
        assert dist._penalties["string"] == [sdist]
        assert dist._penalties["string"] != [0]

    def test_add_string_none(self):
        dist = Distance()
        dist.add_string("string", None, "string")
        assert dist._penalties["string"] == [1]

    def test_add_string_both_none(self):
        dist = Distance()
        dist.add_string("string", None, None)
        assert dist._penalties["string"] == [0]

    def test_distance(self):
        config["match"]["distance_weights"]["album"] = 2.0
        config["match"]["distance_weights"]["medium"] = 1.0
        _clear_weights()

        dist = Distance()
        dist.add("album", 0.5)
        dist.add("media", 0.25)
        dist.add("media", 0.75)
        assert dist.distance == 0.5

        # __getitem__()
        assert dist["album"] == 0.25
        assert dist["media"] == 0.25

    def test_max_distance(self):
        config["match"]["distance_weights"]["album"] = 3.0
        config["match"]["distance_weights"]["medium"] = 1.0
        _clear_weights()

        dist = Distance()
        dist.add("album", 0.5)
        dist.add("medium", 0.0)
        dist.add("medium", 0.0)
        assert dist.max_distance == 5.0

    def test_operators(self):
        config["match"]["distance_weights"]["source"] = 1.0
        config["match"]["distance_weights"]["album"] = 2.0
        config["match"]["distance_weights"]["medium"] = 1.0
        _clear_weights()

        dist = Distance()
        dist.add("source", 0.0)
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

    def test_raw_distance(self):
        config["match"]["distance_weights"]["album"] = 3.0
        config["match"]["distance_weights"]["medium"] = 1.0
        _clear_weights()

        dist = Distance()
        dist.add("album", 0.5)
        dist.add("medium", 0.25)
        dist.add("medium", 0.5)
        assert dist.raw_distance == 2.25

    def test_items(self):
        config["match"]["distance_weights"]["album"] = 4.0
        config["match"]["distance_weights"]["medium"] = 2.0
        _clear_weights()

        dist = Distance()
        dist.add("album", 0.1875)
        dist.add("medium", 0.75)
        assert dist.items() == [("medium", 0.25), ("album", 0.125)]

        # Sort by key if distance is equal.
        dist = Distance()
        dist.add("album", 0.375)
        dist.add("medium", 0.75)
        assert dist.items() == [("album", 0.25), ("medium", 0.25)]

    def test_update(self):
        dist1 = Distance()
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


class TrackDistanceTest(BeetsTestCase):
    def test_identical_tracks(self):
        item = _make_item("one", 1)
        info = _make_trackinfo()[0]
        dist = match.track_distance(item, info, incl_artist=True)
        assert dist == 0.0

    def test_different_title(self):
        item = _make_item("foo", 1)
        info = _make_trackinfo()[0]
        dist = match.track_distance(item, info, incl_artist=True)
        assert dist != 0.0

    def test_different_artist(self):
        item = _make_item("one", 1)
        item.artist = "foo"
        info = _make_trackinfo()[0]
        dist = match.track_distance(item, info, incl_artist=True)
        assert dist != 0.0

    def test_various_artists_tolerated(self):
        item = _make_item("one", 1)
        item.artist = "Various Artists"
        info = _make_trackinfo()[0]
        dist = match.track_distance(item, info, incl_artist=True)
        assert dist == 0.0


class AlbumDistanceTest(BeetsTestCase):
    def _mapping(self, items, info):
        out = {}
        for i, t in zip(items, info.tracks):
            out[i] = t
        return out

    def _dist(self, items, info):
        return match.distance(items, info, self._mapping(items, info))

    def test_identical_albums(self):
        items = []
        items.append(_make_item("one", 1))
        items.append(_make_item("two", 2))
        items.append(_make_item("three", 3))
        info = AlbumInfo(
            artist="some artist",
            album="some album",
            tracks=_make_trackinfo(),
            va=False,
        )
        assert self._dist(items, info) == 0

    def test_incomplete_album(self):
        items = []
        items.append(_make_item("one", 1))
        items.append(_make_item("three", 3))
        info = AlbumInfo(
            artist="some artist",
            album="some album",
            tracks=_make_trackinfo(),
            va=False,
        )
        dist = self._dist(items, info)
        assert dist != 0
        # Make sure the distance is not too great
        assert dist < 0.2

    def test_global_artists_differ(self):
        items = []
        items.append(_make_item("one", 1))
        items.append(_make_item("two", 2))
        items.append(_make_item("three", 3))
        info = AlbumInfo(
            artist="someone else",
            album="some album",
            tracks=_make_trackinfo(),
            va=False,
        )
        assert self._dist(items, info) != 0

    def test_comp_track_artists_match(self):
        items = []
        items.append(_make_item("one", 1))
        items.append(_make_item("two", 2))
        items.append(_make_item("three", 3))
        info = AlbumInfo(
            artist="should be ignored",
            album="some album",
            tracks=_make_trackinfo(),
            va=True,
        )
        assert self._dist(items, info) == 0

    def test_comp_no_track_artists(self):
        # Some VA releases don't have track artists (incomplete metadata).
        items = []
        items.append(_make_item("one", 1))
        items.append(_make_item("two", 2))
        items.append(_make_item("three", 3))
        info = AlbumInfo(
            artist="should be ignored",
            album="some album",
            tracks=_make_trackinfo(),
            va=True,
        )
        info.tracks[0].artist = None
        info.tracks[1].artist = None
        info.tracks[2].artist = None
        assert self._dist(items, info) == 0

    def test_comp_track_artists_do_not_match(self):
        items = []
        items.append(_make_item("one", 1))
        items.append(_make_item("two", 2, "someone else"))
        items.append(_make_item("three", 3))
        info = AlbumInfo(
            artist="some artist",
            album="some album",
            tracks=_make_trackinfo(),
            va=True,
        )
        assert self._dist(items, info) != 0

    def test_tracks_out_of_order(self):
        items = []
        items.append(_make_item("one", 1))
        items.append(_make_item("three", 2))
        items.append(_make_item("two", 3))
        info = AlbumInfo(
            artist="some artist",
            album="some album",
            tracks=_make_trackinfo(),
            va=False,
        )
        dist = self._dist(items, info)
        assert 0 < dist < 0.2

    def test_two_medium_release(self):
        items = []
        items.append(_make_item("one", 1))
        items.append(_make_item("two", 2))
        items.append(_make_item("three", 3))
        info = AlbumInfo(
            artist="some artist",
            album="some album",
            tracks=_make_trackinfo(),
            va=False,
        )
        info.tracks[0].medium_index = 1
        info.tracks[1].medium_index = 2
        info.tracks[2].medium_index = 1
        dist = self._dist(items, info)
        assert dist == 0

    def test_per_medium_track_numbers(self):
        items = []
        items.append(_make_item("one", 1))
        items.append(_make_item("two", 2))
        items.append(_make_item("three", 1))
        info = AlbumInfo(
            artist="some artist",
            album="some album",
            tracks=_make_trackinfo(),
            va=False,
        )
        info.tracks[0].medium_index = 1
        info.tracks[1].medium_index = 2
        info.tracks[2].medium_index = 1
        dist = self._dist(items, info)
        assert dist == 0


class StringDistanceTest(unittest.TestCase):
    def test_equal_strings(self):
        dist = string_dist("Some String", "Some String")
        assert dist == 0.0

    def test_different_strings(self):
        dist = string_dist("Some String", "Totally Different")
        assert dist != 0.0

    def test_punctuation_ignored(self):
        dist = string_dist("Some String", "Some.String!")
        assert dist == 0.0

    def test_case_ignored(self):
        dist = string_dist("Some String", "sOME sTring")
        assert dist == 0.0

    def test_leading_the_has_lower_weight(self):
        dist1 = string_dist("XXX Band Name", "Band Name")
        dist2 = string_dist("The Band Name", "Band Name")
        assert dist2 < dist1

    def test_parens_have_lower_weight(self):
        dist1 = string_dist("One .Two.", "One")
        dist2 = string_dist("One (Two)", "One")
        assert dist2 < dist1

    def test_brackets_have_lower_weight(self):
        dist1 = string_dist("One .Two.", "One")
        dist2 = string_dist("One [Two]", "One")
        assert dist2 < dist1

    def test_ep_label_has_zero_weight(self):
        dist = string_dist("My Song (EP)", "My Song")
        assert dist == 0.0

    def test_featured_has_lower_weight(self):
        dist1 = string_dist("My Song blah Someone", "My Song")
        dist2 = string_dist("My Song feat Someone", "My Song")
        assert dist2 < dist1

    def test_postfix_the(self):
        dist = string_dist("The Song Title", "Song Title, The")
        assert dist == 0.0

    def test_postfix_a(self):
        dist = string_dist("A Song Title", "Song Title, A")
        assert dist == 0.0

    def test_postfix_an(self):
        dist = string_dist("An Album Title", "Album Title, An")
        assert dist == 0.0

    def test_empty_strings(self):
        dist = string_dist("", "")
        assert dist == 0.0

    def test_solo_pattern(self):
        # Just make sure these don't crash.
        string_dist("The ", "")
        string_dist("(EP)", "(EP)")
        string_dist(", An", "")

    def test_heuristic_does_not_harm_distance(self):
        dist = string_dist("Untitled", "[Untitled]")
        assert dist == 0.0

    def test_ampersand_expansion(self):
        dist = string_dist("And", "&")
        assert dist == 0.0

    def test_accented_characters(self):
        dist = string_dist("\xe9\xe1\xf1", "ean")
        assert dist == 0.0
