# This file is part of beets.
# Copyright 2016, Adrian Sampson.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Tests for autotagging functionality."""

import pytest

from beets import autotag, config
from beets.autotag import AlbumInfo, TrackInfo, correct_list_fields, match
from beets.library import Item
from beets.test.helper import BeetsTestCase


class TestAssignment:
    A = "one"
    B = "two"
    C = "three"

    @pytest.fixture(autouse=True)
    def config(self, config):
        config["match"]["track_length_grace"] = 10
        config["match"]["track_length_max"] = 30

    @pytest.mark.parametrize(
        # 'expected' is a tuple of expected (mapping, extra_items, extra_tracks)
        "item_titles, track_titles, expected",
        [
            # items ordering gets corrected
            ([A, C, B], [A, B, C], ({A: A, B: B, C: C}, [], [])),
            # unmatched tracks are returned as 'extra_tracks'
            # the first track is unmatched
            ([B, C], [A, B, C], ({B: B, C: C}, [], [A])),
            # the middle track is unmatched
            ([A, C], [A, B, C], ({A: A, C: C}, [], [B])),
            # the last track is unmatched
            ([A, B], [A, B, C], ({A: A, B: B}, [], [C])),
            # unmatched items are returned as 'extra_items'
            ([A, C, B], [A, C], ({A: A, C: C}, [B], [])),
        ],
    )
    def test_assign_tracks(self, item_titles, track_titles, expected):
        expected_mapping, expected_extra_items, expected_extra_tracks = expected

        items = [Item(title=title) for title in item_titles]
        tracks = [TrackInfo(title=title) for title in track_titles]

        item_info_pairs, extra_items, extra_tracks = match.assign_items(
            items, tracks
        )

        assert (
            {i.title: t.title for i, t in item_info_pairs},
            [i.title for i in extra_items],
            [t.title for t in extra_tracks],
        ) == (expected_mapping, expected_extra_items, expected_extra_tracks)

    def test_order_works_when_track_names_are_entirely_wrong(self):
        # A real-world test case contributed by a user.
        def item(i, length):
            return Item(
                artist="ben harper",
                album="burn to shine",
                title=f"ben harper - Burn to Shine {i}",
                track=i,
                length=length,
            )

        items = []
        items.append(item(1, 241.37243007106997))
        items.append(item(2, 342.27781704375036))
        items.append(item(3, 245.95070222338137))
        items.append(item(4, 472.87662515485437))
        items.append(item(5, 279.1759535763187))
        items.append(item(6, 270.33333768012))
        items.append(item(7, 247.83435613222923))
        items.append(item(8, 216.54504531525072))
        items.append(item(9, 225.72775379800484))
        items.append(item(10, 317.7643606963552))
        items.append(item(11, 243.57001238834192))
        items.append(item(12, 186.45916150485752))

        def info(index, title, length):
            return TrackInfo(title=title, length=length, index=index)

        trackinfo = []
        trackinfo.append(info(1, "Alone", 238.893))
        trackinfo.append(info(2, "The Woman in You", 341.44))
        trackinfo.append(info(3, "Less", 245.59999999999999))
        trackinfo.append(info(4, "Two Hands of a Prayer", 470.49299999999999))
        trackinfo.append(info(5, "Please Bleed", 277.86599999999999))
        trackinfo.append(info(6, "Suzie Blue", 269.30599999999998))
        trackinfo.append(info(7, "Steal My Kisses", 245.36000000000001))
        trackinfo.append(info(8, "Burn to Shine", 214.90600000000001))
        trackinfo.append(info(9, "Show Me a Little Shame", 224.0929999999999))
        trackinfo.append(info(10, "Forgiven", 317.19999999999999))
        trackinfo.append(info(11, "Beloved One", 243.733))
        trackinfo.append(info(12, "In the Lord's Arms", 186.13300000000001))

        expected = list(zip(items, trackinfo)), [], []

        assert match.assign_items(items, trackinfo) == expected


class ApplyTestUtil:
    def _apply(self, info=None, per_disc_numbering=False, artist_credit=False):
        info = info or self.info
        item_info_pairs = list(zip(self.items, info.tracks))
        config["per_disc_numbering"] = per_disc_numbering
        config["artist_credit"] = artist_credit
        autotag.apply_metadata(info, item_info_pairs)


class ApplyTest(BeetsTestCase, ApplyTestUtil):
    def setUp(self):
        super().setUp()

        self.items = []
        self.items.append(Item({}))
        self.items.append(Item({}))
        trackinfo = []
        trackinfo.append(
            TrackInfo(
                title="oneNew",
                track_id="dfa939ec-118c-4d0f-84a0-60f3d1e6522c",
                medium=1,
                medium_index=1,
                medium_total=1,
                index=1,
                artist_credit="trackArtistCredit",
                artists_credit=["trackArtistCredit"],
                artist_sort="trackArtistSort",
                artists_sort=["trackArtistSort"],
            )
        )
        trackinfo.append(
            TrackInfo(
                title="twoNew",
                track_id="40130ed1-a27c-42fd-a328-1ebefb6caef4",
                medium=2,
                medium_index=1,
                index=2,
                medium_total=1,
            )
        )
        self.info = AlbumInfo(
            tracks=trackinfo,
            artist="artistNew",
            artists=["artistNew", "artistNew2"],
            album="albumNew",
            album_id="7edb51cb-77d6-4416-a23c-3a8c2994a2c7",
            artist_id="a6623d39-2d8e-4f70-8242-0a9553b91e50",
            artists_ids=[
                "a6623d39-2d8e-4f70-8242-0a9553b91e50",
                "a6623d39-2d8e-4f70-8242-0a9553b91e51",
            ],
            artist_credit="albumArtistCredit",
            artists_credit=["albumArtistCredit", "albumArtistCredit2"],
            artist_sort="albumArtistSort",
            artists_sort=["albumArtistSort", "albumArtistSort2"],
            albumtype="album",
            va=False,
            mediums=2,
        )

    def test_titles_applied(self):
        self._apply()
        assert self.items[0].title == "oneNew"
        assert self.items[1].title == "twoNew"

    def test_album_and_artist_applied_to_all(self):
        self._apply()
        assert self.items[0].album == "albumNew"
        assert self.items[1].album == "albumNew"
        assert self.items[0].artist == "artistNew"
        assert self.items[1].artist == "artistNew"
        assert self.items[0].artists == ["artistNew", "artistNew2"]
        assert self.items[1].artists == ["artistNew", "artistNew2"]
        assert self.items[0].albumartists == ["artistNew", "artistNew2"]
        assert self.items[1].albumartists == ["artistNew", "artistNew2"]

    def test_track_index_applied(self):
        self._apply()
        assert self.items[0].track == 1
        assert self.items[1].track == 2

    def test_track_total_applied(self):
        self._apply()
        assert self.items[0].tracktotal == 2
        assert self.items[1].tracktotal == 2

    def test_disc_index_applied(self):
        self._apply()
        assert self.items[0].disc == 1
        assert self.items[1].disc == 2

    def test_disc_total_applied(self):
        self._apply()
        assert self.items[0].disctotal == 2
        assert self.items[1].disctotal == 2

    def test_per_disc_numbering(self):
        self._apply(per_disc_numbering=True)
        assert self.items[0].track == 1
        assert self.items[1].track == 1

    def test_per_disc_numbering_track_total(self):
        self._apply(per_disc_numbering=True)
        assert self.items[0].tracktotal == 1
        assert self.items[1].tracktotal == 1

    def test_artist_credit(self):
        self._apply(artist_credit=True)
        assert self.items[0].artist == "trackArtistCredit"
        assert self.items[1].artist == "albumArtistCredit"
        assert self.items[0].albumartist == "albumArtistCredit"
        assert self.items[1].albumartist == "albumArtistCredit"
        assert self.items[0].albumartists == [
            "albumArtistCredit",
            "albumArtistCredit2",
        ]
        assert self.items[1].albumartists == [
            "albumArtistCredit",
            "albumArtistCredit2",
        ]

    def test_artist_credit_prefers_artist_over_albumartist_credit(self):
        self.info.tracks[0].artist = "oldArtist"
        self.info.tracks[0].artist_credit = None
        self._apply(artist_credit=True)
        assert self.items[0].artist == "oldArtist"

    def test_artist_credit_falls_back_to_albumartist(self):
        self.info.artist_credit = None
        self._apply(artist_credit=True)
        assert self.items[1].artist == "artistNew"

    def test_mb_trackid_applied(self):
        self._apply()
        assert (
            self.items[0].mb_trackid == "dfa939ec-118c-4d0f-84a0-60f3d1e6522c"
        )
        assert (
            self.items[1].mb_trackid == "40130ed1-a27c-42fd-a328-1ebefb6caef4"
        )

    def test_mb_albumid_and_artistid_applied(self):
        self._apply()
        for item in self.items:
            assert item.mb_albumid == "7edb51cb-77d6-4416-a23c-3a8c2994a2c7"
            assert item.mb_artistid == "a6623d39-2d8e-4f70-8242-0a9553b91e50"
            assert item.mb_artistids == [
                "a6623d39-2d8e-4f70-8242-0a9553b91e50",
                "a6623d39-2d8e-4f70-8242-0a9553b91e51",
            ]

    def test_albumtype_applied(self):
        self._apply()
        assert self.items[0].albumtype == "album"
        assert self.items[1].albumtype == "album"

    def test_album_artist_overrides_empty_track_artist(self):
        my_info = self.info.copy()
        self._apply(info=my_info)
        assert self.items[0].artist == "artistNew"
        assert self.items[1].artist == "artistNew"
        assert self.items[0].artists == ["artistNew", "artistNew2"]
        assert self.items[1].artists == ["artistNew", "artistNew2"]

    def test_album_artist_overridden_by_nonempty_track_artist(self):
        my_info = self.info.copy()
        my_info.tracks[0].artist = "artist1!"
        my_info.tracks[1].artist = "artist2!"
        my_info.tracks[0].artists = ["artist1!", "artist1!!"]
        my_info.tracks[1].artists = ["artist2!", "artist2!!"]
        self._apply(info=my_info)
        assert self.items[0].artist == "artist1!"
        assert self.items[1].artist == "artist2!"
        assert self.items[0].artists == ["artist1!", "artist1!!"]
        assert self.items[1].artists == ["artist2!", "artist2!!"]

    def test_artist_credit_applied(self):
        self._apply()
        assert self.items[0].albumartist_credit == "albumArtistCredit"
        assert self.items[0].albumartists_credit == [
            "albumArtistCredit",
            "albumArtistCredit2",
        ]
        assert self.items[0].artist_credit == "trackArtistCredit"
        assert self.items[0].artists_credit == ["trackArtistCredit"]
        assert self.items[1].albumartist_credit == "albumArtistCredit"
        assert self.items[1].albumartists_credit == [
            "albumArtistCredit",
            "albumArtistCredit2",
        ]
        assert self.items[1].artist_credit == "albumArtistCredit"
        assert self.items[1].artists_credit == [
            "albumArtistCredit",
            "albumArtistCredit2",
        ]

    def test_artist_sort_applied(self):
        self._apply()
        assert self.items[0].albumartist_sort == "albumArtistSort"
        assert self.items[0].albumartists_sort == [
            "albumArtistSort",
            "albumArtistSort2",
        ]
        assert self.items[0].artist_sort == "trackArtistSort"
        assert self.items[0].artists_sort == ["trackArtistSort"]
        assert self.items[1].albumartist_sort == "albumArtistSort"
        assert self.items[1].albumartists_sort == [
            "albumArtistSort",
            "albumArtistSort2",
        ]
        assert self.items[1].artist_sort == "albumArtistSort"
        assert self.items[1].artists_sort == [
            "albumArtistSort",
            "albumArtistSort2",
        ]

    def test_full_date_applied(self):
        my_info = self.info.copy()
        my_info.year = 2013
        my_info.month = 12
        my_info.day = 18
        self._apply(info=my_info)

        assert self.items[0].year == 2013
        assert self.items[0].month == 12
        assert self.items[0].day == 18

    def test_date_only_zeros_month_and_day(self):
        self.items = []
        self.items.append(Item(year=1, month=2, day=3))
        self.items.append(Item(year=4, month=5, day=6))

        my_info = self.info.copy()
        my_info.year = 2013
        self._apply(info=my_info)

        assert self.items[0].year == 2013
        assert self.items[0].month == 0
        assert self.items[0].day == 0

    def test_missing_date_applies_nothing(self):
        self.items = []
        self.items.append(Item(year=1, month=2, day=3))
        self.items.append(Item(year=4, month=5, day=6))

        self._apply()

        assert self.items[0].year == 1
        assert self.items[0].month == 2
        assert self.items[0].day == 3

    def test_data_source_applied(self):
        my_info = self.info.copy()
        my_info.data_source = "MusicBrainz"
        self._apply(info=my_info)

        assert self.items[0].data_source == "MusicBrainz"


class ApplyCompilationTest(BeetsTestCase, ApplyTestUtil):
    def setUp(self):
        super().setUp()

        self.items = []
        self.items.append(Item({}))
        self.items.append(Item({}))
        trackinfo = []
        trackinfo.append(
            TrackInfo(
                title="oneNew",
                track_id="dfa939ec-118c-4d0f-84a0-60f3d1e6522c",
                artist="artistOneNew",
                artist_id="a05686fc-9db2-4c23-b99e-77f5db3e5282",
                index=1,
            )
        )
        trackinfo.append(
            TrackInfo(
                title="twoNew",
                track_id="40130ed1-a27c-42fd-a328-1ebefb6caef4",
                artist="artistTwoNew",
                artist_id="80b3cf5e-18fe-4c59-98c7-e5bb87210710",
                index=2,
            )
        )
        self.info = AlbumInfo(
            tracks=trackinfo,
            artist="variousNew",
            album="albumNew",
            album_id="3b69ea40-39b8-487f-8818-04b6eff8c21a",
            artist_id="89ad4ac3-39f7-470e-963a-56509c546377",
            albumtype="compilation",
        )

    def test_album_and_track_artists_separate(self):
        self._apply()
        assert self.items[0].artist == "artistOneNew"
        assert self.items[1].artist == "artistTwoNew"
        assert self.items[0].albumartist == "variousNew"
        assert self.items[1].albumartist == "variousNew"

    def test_mb_albumartistid_applied(self):
        self._apply()
        assert (
            self.items[0].mb_albumartistid
            == "89ad4ac3-39f7-470e-963a-56509c546377"
        )
        assert (
            self.items[1].mb_albumartistid
            == "89ad4ac3-39f7-470e-963a-56509c546377"
        )
        assert (
            self.items[0].mb_artistid == "a05686fc-9db2-4c23-b99e-77f5db3e5282"
        )
        assert (
            self.items[1].mb_artistid == "80b3cf5e-18fe-4c59-98c7-e5bb87210710"
        )

    def test_va_flag_cleared_does_not_set_comp(self):
        self._apply()
        assert not self.items[0].comp
        assert not self.items[1].comp

    def test_va_flag_sets_comp(self):
        va_info = self.info.copy()
        va_info.va = True
        self._apply(info=va_info)
        assert self.items[0].comp
        assert self.items[1].comp


@pytest.mark.parametrize(
    "single_field,list_field",
    [
        ("mb_artistid", "mb_artistids"),
        ("mb_albumartistid", "mb_albumartistids"),
        ("albumtype", "albumtypes"),
    ],
)
@pytest.mark.parametrize(
    "single_value,list_value",
    [
        (None, []),
        (None, ["1"]),
        (None, ["1", "2"]),
        ("1", []),
        ("1", ["1"]),
        ("1", ["1", "2"]),
        ("1", ["2", "1"]),
    ],
)
def test_correct_list_fields(
    single_field, list_field, single_value, list_value
):
    """Ensure that the first value in a list field matches the single field."""
    data = {single_field: single_value, list_field: list_value}
    item = Item(**data)

    correct_list_fields(item)

    single_val, list_val = item[single_field], item[list_field]
    assert (not single_val and not list_val) or single_val == list_val[0]


# Tests for multi-value genres functionality
class TestGenreSync:
    """Test the genre/genres field synchronization."""

    def test_genres_list_to_genre_first(self):
        """Genres list sets genre to first item."""
        item = Item(genres=["Rock", "Alternative", "Indie"])
        correct_list_fields(item)

        assert item.genre == "Rock"
        assert item.genres == ["Rock", "Alternative", "Indie"]

    def test_genre_string_to_genres_list(self):
        """Genre string becomes first item in genres list."""
        item = Item(genre="Rock")
        correct_list_fields(item)

        assert item.genre == "Rock"
        assert item.genres == ["Rock"]

    def test_genre_and_genres_both_present(self):
        """When both genre and genres exist, genre becomes first in list."""
        item = Item(genre="Jazz", genres=["Rock", "Alternative"])
        correct_list_fields(item)

        # genre should be prepended to genres list (deduplicated)
        assert item.genre == "Jazz"
        assert item.genres == ["Jazz", "Rock", "Alternative"]

    def test_empty_genre(self):
        """Empty genre field."""
        item = Item(genre="")
        correct_list_fields(item)

        assert item.genre == ""
        assert item.genres == []

    def test_empty_genres(self):
        """Empty genres list."""
        item = Item(genres=[])
        correct_list_fields(item)

        assert item.genre == ""
        assert item.genres == []

    def test_none_values(self):
        """Handle None values in genre/genres fields without errors."""
        # Test with None genre
        item = Item(genre=None, genres=["Rock"])
        correct_list_fields(item)
        assert item.genres == ["Rock"]
        assert item.genre == "Rock"

        # Test with None genres
        item = Item(genre="Jazz", genres=None)
        correct_list_fields(item)
        assert item.genre == "Jazz"
        assert item.genres == ["Jazz"]

    def test_none_both(self):
        """Handle None in both genre and genres."""
        item = Item(genre=None, genres=None)
        correct_list_fields(item)

        assert item.genres == []
        assert item.genre == ""

    def test_migrate_comma_separated_genres(self):
        """Migrate legacy comma-separated genre strings."""
        item = Item(genre="Rock, Alternative, Indie", genres=[])
        correct_list_fields(item)

        # Should split into genres list
        assert item.genres == ["Rock", "Alternative", "Indie"]
        # Genre becomes first item after migration
        assert item.genre == "Rock"

    def test_migrate_semicolon_separated_genres(self):
        """Migrate legacy semicolon-separated genre strings."""
        item = Item(genre="Rock; Alternative; Indie", genres=[])
        correct_list_fields(item)

        assert item.genres == ["Rock", "Alternative", "Indie"]
        assert item.genre == "Rock"

    def test_migrate_slash_separated_genres(self):
        """Migrate legacy slash-separated genre strings."""
        item = Item(genre="Rock / Alternative / Indie", genres=[])
        correct_list_fields(item)

        assert item.genres == ["Rock", "Alternative", "Indie"]
        assert item.genre == "Rock"

    def test_no_migration_when_genres_exists(self):
        """Don't migrate if genres list already populated."""
        item = Item(genre="Jazz, Blues", genres=["Rock", "Pop"])
        correct_list_fields(item)

        # Existing genres list should be preserved
        # The full genre string is prepended (migration doesn't run when genres exists)
        assert item.genres == ["Jazz, Blues", "Rock", "Pop"]
        assert item.genre == "Jazz, Blues"

    def test_no_migration_single_genre(self):
        """Don't split single genres without separators."""
        item = Item(genre="Rock", genres=[])
        correct_list_fields(item)

        # Single genre (no separator) should not trigger migration
        assert item.genres == ["Rock"]
        assert item.genre == "Rock"
