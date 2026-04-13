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

"""Tests for MusicBrainz API wrapper."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, ClassVar
from unittest import mock

import pytest
import requests

from beets import config
from beets.library import Item
from beets.test.helper import BeetsTestCase, PluginMixin
from beetsplug import musicbrainz
from beetsplug.musicbrainz import MusicBrainzPlugin

from .factories import musicbrainz as factories

if TYPE_CHECKING:
    from beetsplug._utils import musicbrainz as mb

_p = pytest.param


def alias_factory(**kwargs) -> mb.Alias:
    return factories.AliasFactory.build(**kwargs)


def artist_credit_factory(**kwargs) -> mb.ArtistCredit:
    return factories.ArtistCreditFactory.build(**kwargs)


def artist_relation_factory(**kwargs) -> mb.ArtistRelation:
    return factories.ArtistRelationFactory.build(**kwargs)


def release_group_factory(**kwargs) -> mb.ReleaseGroup:
    return factories.ReleaseGroupFactory.build(**kwargs)


def recording_factory(**kwargs) -> mb.Recording:
    return factories.RecordingFactory.build(**kwargs)


def track_factory(**kwargs) -> mb.Track:
    return factories.TrackFactory.build(**kwargs)


def medium_factory(**kwargs) -> mb.Medium:
    return factories.MediumFactory(**kwargs)  # type: ignore[return-value]


def release_factory(**kwargs) -> mb.Release:
    return factories.ReleaseFactory(**kwargs)  # type: ignore[return-value]


class MusicBrainzTestCase(BeetsTestCase):
    def setUp(self):
        super().setUp()
        self.mb = musicbrainz.MusicBrainzPlugin()
        self.config["match"]["preferred"]["countries"] = ["US"]


class MBAlbumInfoTest(MusicBrainzTestCase):
    def test_parse_release(self):
        release = release_factory()
        d = self.mb.album_info(release)

        assert d == {
            "album": "Album",
            "album_id": "00000000-0000-0000-0000-000001000001",
            "albumdisambig": "Album Disambiguation",
            "albumstatus": "Official",
            "albumtype": "album",
            "albumtypes": [
                "album",
            ],
            "artist": "Artist",
            "artist_credit": "Artist Credit",
            "artist_id": "00000000-0000-0000-0000-000000000011",
            "artist_sort": "Artist, The",
            "artists": [
                "Artist",
            ],
            "artists_credit": [
                "Artist Credit",
            ],
            "artists_ids": [
                "00000000-0000-0000-0000-000000000011",
            ],
            "artists_sort": [
                "Artist, The",
            ],
            "asin": "Album Asin",
            "barcode": "0000000000000",
            "catalognum": "LAB123",
            "country": "US",
            "data_source": "MusicBrainz",
            "data_url": "https://musicbrainz.org/release/00000000-0000-0000-0000-000001000001",
            "day": 1,
            "discogs_albumid": None,
            "discogs_artistid": None,
            "discogs_labelid": None,
            "genres": None,
            "label": "Label",
            "language": "eng",
            "media": "Digital Media",
            "mediums": 1,
            "month": 1,
            "original_day": 3,
            "original_month": 2,
            "original_year": 2001,
            "release_group_title": "Release Group",
            "releasegroup_id": "00000000-0000-0000-0000-000000000101",
            "releasegroupdisambig": "Release Group Disambiguation",
            "script": "Latn",
            "style": None,
            "tracks": [
                {
                    "album": None,
                    "arrangers": None,
                    "arrangers_ids": [],
                    "artist": "Recording Artist",
                    "artist_credit": "Recording Artist Credit",
                    "artist_id": "00000000-0000-0000-0000-000000000001",
                    "artist_sort": "Recording Artist, The",
                    "artists": [
                        "Recording Artist",
                    ],
                    "artists_credit": [
                        "Recording Artist Credit",
                    ],
                    "artists_ids": [
                        "00000000-0000-0000-0000-000000000001",
                    ],
                    "artists_sort": [
                        "Recording Artist, The",
                    ],
                    "bpm": None,
                    "composer_sort": None,
                    "composers": None,
                    "composers_ids": [],
                    "data_source": "MusicBrainz",
                    "data_url": "https://musicbrainz.org/recording/00000000-0000-0000-0000-000000001001",
                    "disctitle": "Medium",
                    "genres": None,
                    "index": 1,
                    "initial_key": None,
                    "isrc": None,
                    "length": 0.36,
                    "lyricists": None,
                    "lyricists_ids": [],
                    "mb_workid": None,
                    "media": "Digital Media",
                    "medium": 1,
                    "medium_index": 1,
                    "medium_total": 1,
                    "release_track_id": "00000000-0000-0000-0000-000000010001",
                    "remixers": None,
                    "remixers_ids": [],
                    "title": "Recording",
                    "track_alt": "A1",
                    "track_id": "00000000-0000-0000-0000-000000001001",
                    "trackdisambig": None,
                    "work": None,
                    "work_disambig": None,
                },
            ],
            "va": False,
            "year": 2020,
        }

    def test_parse_release_title(self):
        release = release_factory(
            aliases=[
                alias_factory(suffix="en", locale="en", primary=True),
            ]
        )

        # test no alias
        config["import"]["languages"] = []
        d = self.mb.album_info(release)
        assert d.album == "Album"

        # test en primary
        config["import"]["languages"] = ["en"]
        d = self.mb.album_info(release)
        assert d.album == "Alias en"

    def test_parse_tracks(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(
                    recording__length=100000,
                    recording__aliases=[
                        alias_factory(suffix="ONEen", locale="en", primary=True)
                    ],
                ),
                track_factory(
                    recording__index=2,
                    recording__length=200000,
                    recording__title="Other Recording",
                    recording__aliases=[
                        alias_factory(suffix="TWOen", locale="en", primary=True)
                    ],
                ),
            ]
        )

        # test no alias
        config["import"]["languages"] = []

        d = self.mb.album_info(release)
        t = d.tracks
        assert len(t) == 2
        assert t[0].title == "Recording"
        assert t[0].track_id == "00000000-0000-0000-0000-000000001001"
        assert t[0].length == 100.0
        assert t[1].title == "Other Recording"
        assert t[1].track_id == "00000000-0000-0000-0000-000000001002"
        assert t[1].length == 200.0

        # test en primary
        config["import"]["languages"] = ["en"]
        d = self.mb.album_info(release)
        t = d.tracks
        assert t[0].title == "Alias ONEen"
        assert t[1].title == "Alias TWOen"

    def test_parse_track_indices(self):
        release = release_factory(media__0__tracks__count=2)

        d = self.mb.album_info(release)
        t = d.tracks
        assert t[0].medium_index == 1
        assert t[0].index == 1
        assert t[1].medium_index == 2
        assert t[1].index == 2

    def test_parse_medium_numbers_single_medium(self):
        release = release_factory(media__0__tracks__count=2)

        d = self.mb.album_info(release)
        assert d.mediums == 1
        t = d.tracks
        assert t[0].medium == 1
        assert t[1].medium == 1

    def test_parse_medium_numbers_two_mediums(self):
        release = release_factory(
            media=[medium_factory(), medium_factory(position=2)]
        )

        d = self.mb.album_info(release)
        assert d.mediums == 2
        t = d.tracks
        assert t[0].medium == 1
        assert t[0].medium_index == 1
        assert t[0].index == 1
        assert t[1].medium == 2
        assert t[1].medium_index == 1
        assert t[1].index == 2

    def test_parse_release_year_month_only(self):
        release = release_factory(release_group__first_release_date="1987-03")
        d = self.mb.album_info(release)
        assert d.original_year == 1987
        assert d.original_month == 3

    def test_no_durations(self):
        release = release_factory(
            media__0__tracks=[track_factory(recording__length=None)]
        )
        d = self.mb.album_info(release)
        assert d.tracks[0].length is None

    def test_track_length_overrides_recording_length(self):
        release = release_factory(
            media__0__tracks=[track_factory(recording__length=2000.0)]
        )
        d = self.mb.album_info(release)
        assert d.tracks[0].length == 2.0

    def test_no_release_date(self):
        release = release_factory(release_group__first_release_date="")
        d = self.mb.album_info(release)
        assert not d.original_year
        assert not d.original_month
        assert not d.original_day

    def test_detect_various_artists(self):
        release = release_factory(
            artist_credit=[
                artist_credit_factory(artist__id=musicbrainz.VARIOUS_ARTISTS_ID)
            ]
        )
        d = self.mb.album_info(release)
        assert d.va

    def test_parse_release_group_title(self):
        release = release_factory(
            release_group__aliases=[
                alias_factory(suffix="en", locale="en", primary=True),
            ]
        )

        # test no alias
        config["import"]["languages"] = []
        d = self.mb.album_info(release)
        assert d.release_group_title == "Release Group"

        # test en primary
        config["import"]["languages"] = ["en"]
        d = self.mb.album_info(release)
        assert d.release_group_title == "Alias en"

    def test_parse_disctitle(self):
        release = release_factory(media__0__tracks__count=2)
        d = self.mb.album_info(release)
        t = d.tracks
        assert t[0].disctitle == "Medium"
        assert t[1].disctitle == "Medium"

    def test_missing_language(self):
        release = release_factory(text_representation__language=None)
        d = self.mb.album_info(release)
        assert d.language is None

    def test_parse_recording_artist_multi(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(
                    recording__artist_credit=[
                        artist_credit_factory(
                            artist__name="Recording Artist",
                            joinphrase=" & ",
                        ),
                        artist_credit_factory(
                            artist__name="Other Recording Artist",
                            artist__index=2,
                        ),
                    ]
                )
            ]
        )
        track = self.mb.album_info(release).tracks[0]
        assert track.artist == "Recording Artist & Other Recording Artist"
        assert track.artist_id == "00000000-0000-0000-0000-000000000001"
        assert (
            track.artist_sort
            == "Recording Artist, The & Other Recording Artist, The"
        )
        assert (
            track.artist_credit
            == "Recording Artist Credit & Other Recording Artist Credit"
        )

        assert track.artists == [
            "Recording Artist",
            "Other Recording Artist",
        ]
        assert track.artists_ids == [
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        ]
        assert track.artists_sort == [
            "Recording Artist, The",
            "Other Recording Artist, The",
        ]
        assert track.artists_credit == [
            "Recording Artist Credit",
            "Other Recording Artist Credit",
        ]

    def test_track_artist_overrides_recording_artist(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(
                    artist_credit=[
                        artist_credit_factory(artist__name="Track Artist")
                    ]
                )
            ]
        )
        track = self.mb.album_info(release).tracks[0]
        assert track.artist == "Track Artist"
        assert track.artist_id == "00000000-0000-0000-0000-000000000001"
        assert track.artist_sort == "Track Artist, The"
        assert track.artist_credit == "Track Artist Credit"

    def test_track_artist_overrides_recording_artist_multi(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(
                    artist_credit=[
                        artist_credit_factory(
                            artist__name="Track Artist",
                            joinphrase=" & ",
                        ),
                        artist_credit_factory(
                            artist__name="Other Track Artist",
                            artist__index=2,
                        ),
                    ],
                    recording__artist_credit=[
                        artist_credit_factory(
                            artist__name="Recording Artist",
                            joinphrase=" & ",
                        ),
                        artist_credit_factory(
                            artist__name="Other Recording Artist",
                            artist__index=2,
                        ),
                    ],
                ),
            ]
        )
        track = self.mb.album_info(release).tracks[0]
        assert track.artist == "Track Artist & Other Track Artist"
        assert track.artist_id == "00000000-0000-0000-0000-000000000001"
        assert (
            track.artist_sort == "Track Artist, The & Other Track Artist, The"
        )
        assert (
            track.artist_credit
            == "Track Artist Credit & Other Track Artist Credit"
        )

        assert track.artists == ["Track Artist", "Other Track Artist"]
        assert track.artists_ids == [
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        ]
        assert track.artists_sort == [
            "Track Artist, The",
            "Other Track Artist, The",
        ]
        assert track.artists_credit == [
            "Track Artist Credit",
            "Other Track Artist Credit",
        ]

    def test_parse_recording_artist_credits(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(
                    recording__artist_relations=[
                        artist_relation_factory(
                            type="remixer",
                            artist__index=1,
                            artist__name="Recording Remixer",
                        ),
                        artist_relation_factory(
                            type="arranger",
                            artist__index=2,
                            artist__name="Recording Arranger",
                        ),
                        artist_relation_factory(
                            type="arranger",
                            artist__index=3,
                            artist__name="Another Recording Arranger",
                        ),
                    ],
                    recording__work_relations=[
                        {
                            "type": "performance",
                            "work": {
                                "id": "WORK ID",
                                "title": "WORK TITLE",
                                "artist_relations": [
                                    artist_relation_factory(
                                        type="lyricist",
                                        artist__index=4,
                                        artist__name="Recording Lyricist",
                                    ),
                                    artist_relation_factory(
                                        type="lyricist",
                                        artist__index=5,
                                        artist__name="Another Recording Lyricist",
                                    ),
                                    artist_relation_factory(
                                        type="composer",
                                        artist__index=6,
                                        artist__name="Recording Composer",
                                    ),
                                    artist_relation_factory(
                                        type="composer",
                                        artist__index=7,
                                        artist__name="Another Recording Composer",
                                    ),
                                ],
                            },
                        }
                    ],
                )
            ]
        )

        track = self.mb.album_info(release).tracks[0]
        assert track.remixers == ["Recording Remixer"]
        assert track.arrangers == [
            "Recording Arranger",
            "Another Recording Arranger",
        ]
        assert track.lyricists_ids == [
            "00000000-0000-0000-0000-000000000004",
            "00000000-0000-0000-0000-000000000005",
        ]
        assert track.lyricists == [
            "Recording Lyricist",
            "Another Recording Lyricist",
        ]
        assert track.composers == [
            "Recording Composer",
            "Another Recording Composer",
        ]
        assert track.composers_ids == [
            "00000000-0000-0000-0000-000000000006",
            "00000000-0000-0000-0000-000000000007",
        ]
        assert track.composer_sort == (
            "Recording Composer, The, Another Recording Composer, The"
        )

    def test_track_disambiguation(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(),
                track_factory(
                    recording__title="Other Recording",
                    recording__disambiguation="SECOND TRACK",
                ),
            ]
        )

        d = self.mb.album_info(release)
        t = d.tracks
        assert len(t) == 2
        assert t[0].trackdisambig is None
        assert t[1].trackdisambig == "SECOND TRACK"

    def test_missing_tracks(self):
        release = release_factory(
            media=[
                medium_factory(),
                medium_factory(
                    tracks=[
                        track_factory(),
                        track_factory(
                            recording__title="Other Recording",
                            recording__disambiguation="SECOND TRACK",
                        ),
                    ]
                ),
            ]
        )
        d = self.mb.album_info(release)
        assert d.mediums == 2


class MusicBrainzPluginTestMixin(PluginMixin):
    plugin = "musicbrainz"

    @pytest.fixture
    def plugin_config(self):
        return {}

    @pytest.fixture
    def mb(self, plugin_config):
        self.config[self.plugin].set(plugin_config)

        return musicbrainz.MusicBrainzPlugin()


class TestParse(MusicBrainzPluginTestMixin):
    @pytest.mark.parametrize(
        "beets_match_config, expected_titles",
        [
            _p({}, ("Audio",), id="only audio tracks by default"),
            _p(
                {"ignore_data_tracks": False},
                ("Audio", "Data"),
                id="include data tracks",
            ),
            _p(
                {
                    "ignore_data_tracks": False,
                    "ignore_video_tracks": False,
                },
                ("Audio", "Video: Video", "Data"),
                id="include data and video tracks",
            ),
            _p({"ignored_media": "Vinyl"}, (), id="ignore all tracks"),
        ],
    )
    def test_data_tracks(self, config, beets_match_config, mb, expected_titles):
        medium = medium_factory(
            format="Vinyl",
            tracks=[
                track_factory(recording__title="Audio"),
                track_factory(recording__title="[data track]"),
                track_factory(recording__title="Video", recording__video=True),
            ],
            data_tracks=[
                track_factory(recording__title="Data"),
            ],
        )
        release = release_factory(media=[medium])

        config.set({"match": beets_match_config})

        actual_titles = tuple(t.title for t in mb.album_info(release).tracks)

        assert actual_titles == expected_titles

    @pytest.mark.parametrize(
        "plugin_config, expected_genres",
        [
            _p({"genres": False}, None, id="genres disabled"),
            _p({"genres": True, "genres_tag": "genre"}, ["Genre"], id="use genres"),
            _p({"genres": True, "genres_tag": "tag"}, ["Tag"], id="use tags"),
        ],
    )  # fmt: skip
    def test_genres(self, mb, expected_genres):
        assert mb.album_info(release_factory()).genres == expected_genres


class TestArtist:
    def test_single_artist(self):
        credit = [artist_credit_factory(artist__name="Artist")]

        assert MusicBrainzPlugin._parse_artist_credits(credit) == {
            "artist": "Artist",
            "artist_id": "00000000-0000-0000-0000-000000000001",
            "artist_sort": "Artist, The",
            "artist_credit": "Artist Credit",
            "artists": ["Artist"],
            "artists_ids": ["00000000-0000-0000-0000-000000000001"],
            "artists_sort": ["Artist, The"],
            "artists_credit": ["Artist Credit"],
        }

    def test_two_artists(self):
        credit = [
            artist_credit_factory(artist__name="Artist", joinphrase=" AND "),
            artist_credit_factory(artist__name="Other Artist", artist__index=2),
        ]

        assert MusicBrainzPlugin._parse_artist_credits(credit) == {
            "artist": "Artist AND Other Artist",
            "artist_id": "00000000-0000-0000-0000-000000000001",
            "artist_sort": "Artist, The AND Other Artist, The",
            "artist_credit": "Artist Credit AND Other Artist Credit",
            "artists": ["Artist", "Other Artist"],
            "artists_ids": [
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
            ],
            "artists_sort": ["Artist, The", "Other Artist, The"],
            "artists_credit": ["Artist Credit", "Other Artist Credit"],
        }

    @pytest.mark.parametrize(
        "languages_config, expected_alias_name",
        [
            _p([], None, id="no alias without languages"),
            _p(["en"], "Alias en", id="en primary"),
            _p(["en_GB", "en"], "Alias en_GB", id="en_GB primary"),
            _p(["en", "en_GB"], "Alias en", id="en primary over en_GB"),
            _p(["fr"], "Alias fr_P", id="fr primary"),
            _p(["pt_BR", "fr"], "Alias fr_P", id="non-primary ignored"),
        ],
    )
    def test_preferred_alias(
        self, config, languages_config, expected_alias_name
    ):
        aliases = [
            alias_factory(suffix="en", locale="en", primary=True),
            alias_factory(suffix="en_GB", locale="en_GB", primary=True),
            alias_factory(suffix="fr", locale="fr"),
            alias_factory(suffix="fr_P", locale="fr", primary=True),
            alias_factory(suffix="pt_BR", locale="pt_BR"),
        ]

        config["import"]["languages"] = languages_config

        alias = musicbrainz._preferred_alias(aliases)

        if expected_alias_name is None:
            assert not alias
        else:
            assert alias["name"] == expected_alias_name


class MBLibraryTest(MusicBrainzTestCase):
    def test_follow_pseudo_releases(self):
        side_effect = [
            release_factory(
                id="d2a6f856-b553-40a0-ac54-a321e8e2da02",
                title="pseudo",
                status="Pseudo-Release",
                country=None,
                release_events=[],
                release_relations=[
                    {
                        "type": "transl-tracklisting",
                        "direction": "backward",
                        "release": {
                            "id": "d2a6f856-b553-40a0-ac54-a321e8e2da01"
                        },
                    }
                ],
            ),
            release_factory(
                title="actual",
                id="d2a6f856-b553-40a0-ac54-a321e8e2da01",
            ),
        ]

        with mock.patch(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_release"
        ) as gp:
            gp.side_effect = side_effect
            album = self.mb.album_for_id("d2a6f856-b553-40a0-ac54-a321e8e2da02")
            assert album
            assert album.country == "US"

    def test_pseudo_releases_with_empty_links(self):
        side_effect = [
            release_factory(
                id="d2a6f856-b553-40a0-ac54-a321e8e2da02",
                title="pseudo",
                status="Pseudo-Release",
                release_events=[],
            )
        ]

        with mock.patch(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_release"
        ) as gp:
            gp.side_effect = side_effect
            album = self.mb.album_for_id("d2a6f856-b553-40a0-ac54-a321e8e2da02")
            assert album
            assert album.country is None

    def test_pseudo_releases_without_links(self):
        side_effect = [
            release_factory(
                id="d2a6f856-b553-40a0-ac54-a321e8e2da02",
                title="pseudo",
                status="Pseudo-Release",
                release_events=[],
            )
        ]

        with mock.patch(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_release"
        ) as gp:
            gp.side_effect = side_effect
            album = self.mb.album_for_id("d2a6f856-b553-40a0-ac54-a321e8e2da02")
            assert album
            assert album.country is None

    def test_pseudo_releases_with_unsupported_links(self):
        side_effect = [
            release_factory(
                id="d2a6f856-b553-40a0-ac54-a321e8e2da02",
                title="pseudo",
                status="Pseudo-Release",
                release_events=[],
                release_relations=[
                    {
                        "type": "remaster",
                        "direction": "backward",
                        "release": {
                            "id": "d2a6f856-b553-40a0-ac54-a321e8e2da01"
                        },
                    }
                ],
            )
        ]

        with mock.patch(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_release"
        ) as gp:
            gp.side_effect = side_effect
            album = self.mb.album_for_id("d2a6f856-b553-40a0-ac54-a321e8e2da02")
            assert album
            assert album.country is None


class TestMusicBrainzPlugin(MusicBrainzPluginTestMixin):
    mbid = "d2a6f856-b553-40a0-ac54-a321e8e2da99"
    RECORDING: ClassVar[mb.Recording] = recording_factory()

    @pytest.mark.parametrize(
        "plugin_config,va_likely,expected_additional_criteria",
        [
            ({}, False, {"artist": "Artist "}),
            ({}, True, {"arid": "89ad4ac3-39f7-470e-963a-56509c546377"}),
            (
                {"extra_tags": ["label", "catalognum"]},
                False,
                {"artist": "Artist ", "label": "abc", "catno": "ABC123"},
            ),
        ],
    )
    def test_get_album_criteria(
        self, mb, va_likely, expected_additional_criteria
    ):
        items = [
            Item(catalognum="ABC 123", label="abc"),
            Item(catalognum="ABC 123", label="abc"),
            Item(catalognum="ABC 123", label="def"),
        ]

        assert mb.get_album_criteria(items, "Artist ", " Album", va_likely) == {
            "release": " Album",
            **expected_additional_criteria,
        }

    def test_item_candidates(self, monkeypatch, mb):
        monkeypatch.setattr(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_json",
            lambda *_, **__: {"recordings": [self.RECORDING]},
        )
        monkeypatch.setattr(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_recording",
            lambda *_, **__: self.RECORDING,
        )

        candidates = list(mb.item_candidates(Item(), "hello", "there"))

        assert len(candidates) == 1
        assert candidates[0].track_id == self.RECORDING["id"]

    def test_candidates(self, monkeypatch, mb):
        monkeypatch.setattr(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_json",
            lambda *_, **__: {"releases": [{"id": self.mbid}]},
        )
        monkeypatch.setattr(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_release",
            lambda *_, **__: release_factory(
                id=self.mbid, media=[medium_factory()]
            ),
        )
        candidates = list(mb.candidates([], "hello", "there", False))

        assert len(candidates) == 1
        assert (
            candidates[0].tracks[0].track_id
            == "00000000-0000-0000-0000-000000001001"
        )
        assert candidates[0].album == "Album"

    def test_import_handles_404_gracefully(self, mb, requests_mock):
        id_ = uuid.uuid4()
        response = requests.Response()
        response.status_code = 404
        requests_mock.get(
            f"/ws/2/release/{id_}",
            exc=requests.exceptions.HTTPError(response=response),
        )
        res = mb.album_for_id(str(id_))
        assert res is None

    def test_import_propagates_non_404_errors(self, mb):
        class DummyResponse:
            status_code = 500

        error = requests.exceptions.HTTPError(response=DummyResponse())

        def raise_error(*args, **kwargs):
            raise error

        # Simulate mb.mb_api.get_release raising a non-404 HTTP error
        mb.mb_api.get_release = raise_error

        with pytest.raises(requests.exceptions.HTTPError) as excinfo:
            mb.album_for_id(str(uuid.uuid4()))

        # Ensure the exact error is propagated, not swallowed
        assert excinfo.value is error
