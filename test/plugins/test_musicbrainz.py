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

import unittest
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
    def test_parse_release_with_year(self):
        release = release_factory(release_group__first_release_date="1984")
        d = self.mb.album_info(release)
        assert d.album == "Album"
        assert d.album_id == "00000000-0000-0000-0000-000001000001"
        assert d.artist == "Artist"
        assert d.artist_id == "00000000-0000-0000-0000-000000000011"
        assert d.original_year == 1984
        assert d.year == 2020
        assert d.artist_credit == "Artist Credit"

    def test_parse_release_type(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.albumtype == "album"

    def test_parse_release_full_date(self):
        release = release_factory(
            release_group__first_release_date="1987-03-31"
        )
        d = self.mb.album_info(release)
        assert d.original_year == 1987
        assert d.original_month == 3
        assert d.original_day == 31

    def test_parse_tracks(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(recording__length=100000),
                track_factory(
                    recording__index=2,
                    recording__length=200000,
                    recording__title="Other Recording",
                ),
            ]
        )

        d = self.mb.album_info(release)
        t = d.tracks
        assert len(t) == 2
        assert t[0].title == "Recording"
        assert t[0].track_id == "00000000-0000-0000-0000-000000001001"
        assert t[0].length == 100.0
        assert t[1].title == "Other Recording"
        assert t[1].track_id == "00000000-0000-0000-0000-000000001002"
        assert t[1].length == 200.0

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

    def test_various_artists_defaults_false(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert not d.va

    def test_detect_various_artists(self):
        release = release_factory()
        release["artist_credit"][0]["artist"]["id"] = (
            musicbrainz.VARIOUS_ARTISTS_ID
        )
        d = self.mb.album_info(release)
        assert d.va

    def test_parse_artist_sort_name(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.artist_sort == "Artist, The"

    def test_parse_releasegroupid(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.releasegroup_id == "00000000-0000-0000-0000-000000000101"

    def test_parse_asin(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.asin == "Album Asin"

    def test_parse_catalognum(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.catalognum == "LAB123"

    def test_parse_textrepr(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.script == "Latn"
        assert d.language == "eng"

    def test_parse_country(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.country == "US"

    def test_parse_status(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.albumstatus == "Official"

    def test_parse_barcode(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.barcode == "0000000000000"

    def test_parse_media(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.media == "Digital Media"

    def test_parse_disambig(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.albumdisambig == "Album Disambiguation"
        assert d.releasegroupdisambig == "Release Group Disambiguation"

    def test_parse_disctitle(self):
        release = release_factory(media__0__tracks__count=2)
        d = self.mb.album_info(release)
        t = d.tracks
        assert t[0].disctitle == "Medium"
        assert t[1].disctitle == "Medium"

    def test_missing_language(self):
        release = release_factory()
        release["text_representation"]["language"] = None
        d = self.mb.album_info(release)
        assert d.language is None

    def test_parse_recording_artist(self):
        release = release_factory()
        track = self.mb.album_info(release).tracks[0]
        assert track.artist == "Recording Artist"
        assert track.artist_id == "00000000-0000-0000-0000-000000000001"
        assert track.artist_sort == "Recording Artist, The"
        assert track.artist_credit == "Recording Artist Credit"

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

    def test_parse_recording_remixer(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(
                    recording__artist_relations=[
                        artist_relation_factory(
                            type="remixer", artist__name="Recording Remixer"
                        )
                    ]
                )
            ]
        )
        track = self.mb.album_info(release).tracks[0]
        assert track.remixer == "Recording Remixer"

    def test_data_source(self):
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.data_source == "MusicBrainz"

    def test_genres(self):
        config["musicbrainz"]["genres"] = True
        config["musicbrainz"]["genres_tag"] = "genre"
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.genre == "Genre"

    def test_tags(self):
        config["musicbrainz"]["genres"] = True
        config["musicbrainz"]["genres_tag"] = "tag"
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.genre == "Tag"

    def test_no_genres(self):
        config["musicbrainz"]["genres"] = False
        release = release_factory()
        d = self.mb.album_info(release)
        assert d.genre is None

    def test_ignored_media(self):
        config["match"]["ignored_media"] = ["IGNORED1", "IGNORED2"]
        release = release_factory(
            media__0__format="IGNORED1", media__0__tracks__count=2
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 0

    def test_no_ignored_media(self):
        config["match"]["ignored_media"] = ["IGNORED1", "IGNORED2"]
        release = release_factory(
            media__0__format="NON-IGNORED", media__0__tracks__count=2
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 2

    def test_skip_data_track(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(),
                track_factory(recording__title="[data track]"),
                track_factory(recording__title="Other Recording"),
            ]
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 2
        assert d.tracks[0].title == "Recording"
        assert d.tracks[1].title == "Other Recording"

    def test_skip_audio_data_tracks_by_default(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(),
                track_factory(recording__title="Other Recording"),
            ],
            media__0__data_tracks=[
                track_factory(recording__title="Audio Data Recording"),
            ],
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 2
        assert d.tracks[0].title == "Recording"
        assert d.tracks[1].title == "Other Recording"

    def test_no_skip_audio_data_tracks_if_configured(self):
        config["match"]["ignore_data_tracks"] = False
        release = release_factory(
            media__0__tracks=[
                track_factory(),
                track_factory(recording__title="Other Recording"),
            ],
            media__0__data_tracks=[
                track_factory(recording__title="Audio Data Recording"),
            ],
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 3
        assert d.tracks[0].title == "Recording"
        assert d.tracks[1].title == "Other Recording"
        assert d.tracks[2].title == "Audio Data Recording"

    def test_skip_video_tracks_by_default(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(),
                track_factory(recording__video=True),
                track_factory(recording__title="Other Recording"),
            ]
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 2
        assert d.tracks[0].title == "Recording"
        assert d.tracks[1].title == "Other Recording"

    def test_skip_video_data_tracks_by_default(self):
        release = release_factory(
            media__0__tracks=[
                track_factory(),
                track_factory(recording__title="Other Recording"),
            ],
            media__0__data_tracks=[
                track_factory(recording__video=True),
            ],
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 2
        assert d.tracks[0].title == "Recording"
        assert d.tracks[1].title == "Other Recording"

    def test_no_skip_video_tracks_if_configured(self):
        config["match"]["ignore_data_tracks"] = False
        config["match"]["ignore_video_tracks"] = False
        release = release_factory(
            media__0__tracks=[
                track_factory(),
                track_factory(recording__video=True),
                track_factory(recording__title="Other Recording"),
            ]
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 3
        assert d.tracks[0].title == "Recording"
        assert d.tracks[1].title == "Video: Recording"
        assert d.tracks[2].title == "Other Recording"

    def test_no_skip_video_data_tracks_if_configured(self):
        config["match"]["ignore_data_tracks"] = False
        config["match"]["ignore_video_tracks"] = False
        release = release_factory(
            media__0__tracks=[
                track_factory(),
                track_factory(recording__title="Other Recording"),
            ],
            media__0__data_tracks=[
                track_factory(recording__video=True),
            ],
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 3
        assert d.tracks[0].title == "Recording"
        assert d.tracks[1].title == "Other Recording"
        assert d.tracks[2].title == "Video: Recording"

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
        tracks = [
            self._make_track("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_track(
                "TITLE TWO",
                "ID TWO",
                200.0 * 1000.0,
                disambiguation="SECOND TRACK",
            ),
        ]
        release = self._make_release(tracks=tracks)
        release["media"].append(release["media"][0])
        del release["media"][0]["tracks"]
        del release["media"][0]["data-tracks"]
        d = self.mb.album_info(release)
        assert d.mediums == 2


class ArtistTest(unittest.TestCase):
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

    def test_preferred_alias(self):
        aliases = [
            alias_factory(suffix="en", locale="en", primary=True),
            alias_factory(suffix="en_GB", locale="en_GB", primary=True),
            alias_factory(suffix="fr", locale="fr"),
            alias_factory(suffix="fr_P", locale="fr", primary=True),
            alias_factory(suffix="pt_BR", locale="pt_BR"),
        ]

        # test no alias
        config["import"]["languages"] = [""]
        assert not musicbrainz._preferred_alias(aliases)

        # test en primary
        config["import"]["languages"] = ["en"]
        preferred_alias = musicbrainz._preferred_alias(aliases)
        assert preferred_alias
        assert preferred_alias["name"] == "Alias en"

        # test en_GB en primary
        config["import"]["languages"] = ["en_GB", "en"]
        preferred_alias = musicbrainz._preferred_alias(aliases)
        assert preferred_alias
        assert preferred_alias["name"] == "Alias en_GB"

        # test en en_GB primary
        config["import"]["languages"] = ["en", "en_GB"]
        preferred_alias = musicbrainz._preferred_alias(aliases)
        assert preferred_alias
        assert preferred_alias["name"] == "Alias en"

        # test fr primary
        config["import"]["languages"] = ["fr"]
        preferred_alias = musicbrainz._preferred_alias(aliases)
        assert preferred_alias
        assert preferred_alias["name"] == "Alias fr_P"

        # test for not matching non-primary
        config["import"]["languages"] = ["pt_BR", "fr"]
        preferred_alias = musicbrainz._preferred_alias(aliases)
        assert preferred_alias
        assert preferred_alias["name"] == "Alias fr_P"


class MBLibraryTest(MusicBrainzTestCase):
    def test_follow_pseudo_releases(self):
        side_effect: list[mb.Release] = [
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
            assert album.country == "US"

    def test_pseudo_releases_with_empty_links(self):
        side_effect: list[mb.Release] = [
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
            assert album.country is None

    def test_pseudo_releases_without_links(self):
        side_effect: list[mb.Release] = [
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
            assert album.country is None

    def test_pseudo_releases_with_unsupported_links(self):
        side_effect: list[mb.Release] = [
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
            assert album.country is None


class TestMusicBrainzPlugin(PluginMixin):
    plugin = "musicbrainz"

    mbid = "d2a6f856-b553-40a0-ac54-a321e8e2da99"
    RECORDING: ClassVar[mb.Recording] = recording_factory()

    @pytest.fixture
    def plugin_config(self):
        return {}

    @pytest.fixture
    def mb(self, plugin_config):
        self.config[self.plugin].set(plugin_config)

        return musicbrainz.MusicBrainzPlugin()

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
            lambda *_, **__: {"recordings": [{"id": self.RECORDING["id"]}]},
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
        assert candidates[0].tracks[0].track_id == self.RECORDING["id"]
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
