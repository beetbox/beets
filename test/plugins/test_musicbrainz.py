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

import pytest
import requests

from beets.library import Item
from beets.test.helper import PluginMixin
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


def label_info_factory(**kwargs) -> mb.LabelInfo:
    return factories.LabelInfoFactory.build(**kwargs)


def release_group_factory(**kwargs) -> mb.ReleaseGroup:
    return factories.ReleaseGroupFactory.build(**kwargs)


def recording_factory(**kwargs) -> mb.Recording:
    return factories.RecordingFactory.build(**kwargs)


def track_factory(**kwargs) -> mb.Track:
    return factories.TrackFactory.build(**kwargs)


def url_relation_factory(**kwargs) -> mb.UrlRelation:
    return factories.UrlRelationFactory.build(**kwargs)


def medium_factory(**kwargs) -> mb.Medium:
    return factories.MediumFactory.build(**kwargs)


def release_factory(**kwargs) -> mb.Release:
    return factories.ReleaseFactory.build(**kwargs)


class TestUtils:
    @pytest.mark.parametrize(
        "date, expected_parts",
        [
            ("1987-03-01", (1987, 3, 1)),
            ("1987-03", (1987, 3, None)),
            ("1987", (1987, None, None)),
        ],
    )
    def test_get_date(self, date, expected_parts):
        assert musicbrainz._get_date(date) == expected_parts

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
            alias_factory(locale="en"),
            alias_factory(locale="en_GB"),
            alias_factory(locale="fr", primary=False),
            alias_factory(suffix="fr_P", locale="fr"),
            alias_factory(locale="pt_BR", primary=False),
        ]

        config["import"]["languages"] = languages_config

        alias = musicbrainz._preferred_alias(aliases)

        if expected_alias_name is None:
            assert not alias
        else:
            assert alias["name"] == expected_alias_name

    @pytest.mark.parametrize(
        "label_infos, expected",
        [
            _p([], {"catalognum": None, "label": None}, id="no label"),
            _p(
                [label_info_factory(label=None)],
                {"catalognum": "LAB123", "label": None},
                id="no label",
            ),
            _p(
                [label_info_factory(label__name="[no label]")],
                {"catalognum": "LAB123", "label": None},
                id="label with ignored [no label] name",
            ),
            _p(
                [label_info_factory()],
                {"catalognum": "LAB123", "label": "Label"},
                id="normal case",
            ),
        ],
    )
    def test_parse_label_info(self, label_infos, expected):
        assert MusicBrainzPlugin._parse_label_infos(label_infos) == expected


class MusicBrainzPluginTestMixin(PluginMixin):
    plugin = "musicbrainz"

    @pytest.fixture
    def plugin_config(self):
        return {}

    @pytest.fixture
    def mb(self, plugin_config):
        self.config[self.plugin].set(plugin_config)

        return musicbrainz.MusicBrainzPlugin()


class TestParseRecording(MusicBrainzPluginTestMixin):
    def test_parse_recording(self, mb):
        recording = recording_factory(
            length=None,
            disambiguation="Recording Disambiguation",
            artist_relations=[
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
                artist_relation_factory(type="engineer"),
            ],
            work_relations=[
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
                            artist_relation_factory(type="mastering"),
                        ],
                    },
                }
            ],
        )

        assert mb.track_info(recording) == {
            "album": None,
            "arrangers": [
                "Recording Arranger",
                "Another Recording Arranger",
            ],
            "arrangers_ids": [
                "00000000-0000-0000-0000-000000000002",
                "00000000-0000-0000-0000-000000000003",
            ],
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
            "composer_sort": "Recording Composer, The, Another Recording Composer, The",
            "composers": [
                "Recording Composer",
                "Another Recording Composer",
            ],
            "composers_ids": [
                "00000000-0000-0000-0000-000000000006",
                "00000000-0000-0000-0000-000000000007",
            ],
            "data_source": "MusicBrainz",
            "data_url": "https://musicbrainz.org/recording/00000000-0000-0000-0000-000000001001",
            "disctitle": None,
            "genres": None,
            "index": None,
            "initial_key": None,
            "isrc": None,
            "length": None,
            "lyricists": [
                "Recording Lyricist",
                "Another Recording Lyricist",
            ],
            "lyricists_ids": [
                "00000000-0000-0000-0000-000000000004",
                "00000000-0000-0000-0000-000000000005",
            ],
            "mb_workid": "WORK ID",
            "media": None,
            "medium": None,
            "medium_index": None,
            "medium_total": None,
            "release_track_id": None,
            "remixers": [
                "Recording Remixer",
            ],
            "remixers_ids": [
                "00000000-0000-0000-0000-000000000001",
            ],
            "title": "Recording",
            "track_alt": None,
            "track_id": "00000000-0000-0000-0000-000000001001",
            "trackdisambig": "Recording Disambiguation",
            "work": "WORK TITLE",
            "work_disambig": None,
        }


class TestParseMedia(MusicBrainzPluginTestMixin):
    def test_multiple_mediums(self, mb):
        first_medium = medium_factory(
            title="First Medium",
            position=1,
            tracks=[
                track_factory(recording__length=100000),
                track_factory(
                    position=2,
                    recording__index=2,
                    recording__length=200000,
                    recording__title="Other Recording",
                ),
            ],
        )
        second_medium = medium_factory(
            title="Second Medium",
            position=2,
            pregap=track_factory(recording__title="Pregap", position=0),
            tracks=[track_factory()],
        )
        release = release_factory(media=[first_medium, second_medium])

        d = mb.album_info(release)

        assert d.mediums == 2
        t = d.tracks
        assert len(t) == 4

        assert t[0].title == "Recording"
        assert t[0].track_id == "00000000-0000-0000-0000-000000001001"
        assert t[0].length == 100.0
        assert t[0].medium == 1
        assert t[0].medium_index == 1
        assert t[0].index == 1
        assert t[0].disctitle == "First Medium"

        assert t[1].title == "Other Recording"
        assert t[1].track_id == "00000000-0000-0000-0000-000000001002"
        assert t[1].length == 200.0
        assert t[1].medium == 1
        assert t[1].medium_index == 2
        assert t[1].index == 2
        assert t[1].disctitle == "First Medium"

        assert t[2].title == "Pregap"
        assert t[2].medium == 2
        assert t[2].medium_index == 0
        assert t[2].index == 3
        assert t[2].disctitle == "Second Medium"

        assert t[3].medium == 2
        assert t[3].medium_index == 1
        assert t[3].index == 4
        assert t[3].disctitle == "Second Medium"

    def test_track_overrides_recording(self, mb):
        release = release_factory(
            media__0__tracks=[
                track_factory(
                    length=1000.0,
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
                    recording__length=2000.0,
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

        track = mb.album_info(release).tracks[0]

        assert track.length == 1.0
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

    def test_missing_tracks(self, mb):
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

        assert mb.album_info(release).mediums == 2

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


class TestParseRelease(MusicBrainzPluginTestMixin):
    def test_parse_release(self, config, mb):
        config["match"]["preferred"]["countries"] = ["US"]
        mb.config.set(
            {
                "external_ids": {
                    "discogs": True,
                    "bandcamp": True,
                    "spotify": False,
                }
            }
        )

        release = release_factory(
            url_relations=[
                url_relation_factory(
                    url__resource="https://discogs.com/release/123456"
                ),
                url_relation_factory(
                    url__resource="https://open.spotify.com/album/ABCDab2ImQyHZ9sXCXFyZ8",
                ),
                url_relation_factory(
                    url__resource="https://somemusic.bandcamp.com/album/somealbum",
                ),
            ]
        )
        d = mb.album_info(release)

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
            "bandcamp_album_id": "https://somemusic.bandcamp.com/album/somealbum",
            "barcode": "0000000000000",
            "catalognum": "LAB123",
            "country": "US",
            "data_source": "MusicBrainz",
            "data_url": "https://musicbrainz.org/release/00000000-0000-0000-0000-000001000001",
            "day": 1,
            "discogs_album_id": "123456",
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

    def test_detect_various_artists(self, mb):
        release = release_factory(
            artist_credit=[
                artist_credit_factory(artist__id=musicbrainz.VARIOUS_ARTISTS_ID)
            ]
        )

        assert mb.album_info(release).va

    def test_missing_language(self, mb):
        release = release_factory(text_representation__language=None)

        assert mb.album_info(release).language is None

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

    def test_parse_aliased_titles(self, config, mb: MusicBrainzPlugin):
        release = release_factory()

        config["import"]["languages"] = ["en"]

        d = mb.album_info(release)

        assert d.album == "Album Alias en"
        assert d.release_group_title == "Release Group Alias en"
        assert d.tracks[0].title == "Recording Alias en"

        album_artist = "Artist Alias en"
        assert d.artist == album_artist
        assert d.artists == [album_artist]
        # There is no artist credit specific alias
        assert d.artist_credit == album_artist
        assert d.artists_credit == [album_artist]

        album_artist_sort = "Artist Alias en, The"
        assert d.artist_sort == album_artist_sort
        assert d.artists_sort == [album_artist_sort]

        first_track = d.tracks[0]

        track_artist = "Recording Artist Alias en"
        assert first_track.artist == track_artist
        assert first_track.artists == [track_artist]
        # There is no artist credit specific alias
        assert first_track.artist_credit == track_artist
        assert first_track.artists_credit == [track_artist]

        track_artist_sort = "Recording Artist Alias en, The"
        assert first_track.artist_sort == track_artist_sort
        assert first_track.artists_sort == [track_artist_sort]

    def test_ensure_complete_recordings(self, monkeypatch, mb):
        titles = ["Recording", "Other Recording"]
        initial_recordings = [
            recording_factory(index=idx, title=t)
            for idx, t in enumerate(titles)
        ]
        complete_recordings = [
            {**r, "url_relations": [url_relation_factory()]}
            for r in initial_recordings
        ]

        monkeypatch.setattr("beetsplug.musicbrainz.BROWSE_CHUNKSIZE", 1)
        monkeypatch.setattr("beetsplug.musicbrainz.BROWSE_MAXTRACKS", 1)
        monkeypatch.setattr(
            mb.mb_api,
            "browse_recordings",
            lambda offset=0, **__: [complete_recordings[offset]],
        )

        release = release_factory(
            media__0__tracks=[
                track_factory(recording=r) for r in initial_recordings
            ]
        )

        mb._ensure_complete_recordings(release)

        new_recordings = [
            t["recording"] for m in release["media"] for t in m["tracks"]
        ]
        assert new_recordings == complete_recordings


class TestPseudoRelease(MusicBrainzPluginTestMixin):
    ACTUAL_RELEASE = release_factory(index=1, country="US")
    PSEUDO_WITHOUT_LINKS = release_factory(
        index=2, status="Pseudo-Release", country=None
    )
    PSEUDO_INVALID_LINK = release_factory(
        index=3,
        status="Pseudo-Release",
        country=None,
        release_relations=[
            {
                "type": "remaster",
                "direction": "backward",
                "release": {"id": "d2a6f856-b553-40a0-ac54-a321e8e2da01"},
            }
        ],
    )
    PSEUDO_VALID_LINK = release_factory(
        index=4,
        status="Pseudo-Release",
        country=None,
        release_relations=[
            {
                "type": "transl-tracklisting",
                "direction": "backward",
                "release": {"id": ACTUAL_RELEASE["id"]},
            }
        ],
    )

    @pytest.fixture(autouse=True)
    def setup_album_lookup(self, monkeypatch, mb):
        releases = [
            self.ACTUAL_RELEASE,
            self.PSEUDO_WITHOUT_LINKS,
            self.PSEUDO_INVALID_LINK,
            self.PSEUDO_VALID_LINK,
        ]
        release_by_id = {r["id"]: r for r in releases}

        monkeypatch.setattr(
            mb.mb_api, "get_release", lambda id_: release_by_id[id_]
        )

    @pytest.mark.parametrize(
        "release_id, expected_country",
        [
            _p(ACTUAL_RELEASE["id"], "US", id="actual release"),
            _p(PSEUDO_WITHOUT_LINKS["id"], None, id="pseudo without links"),
            _p(PSEUDO_INVALID_LINK["id"], None, id="pseudo with invalid link"),
            _p(PSEUDO_VALID_LINK["id"], "US", id="pseudo with valid link"),
        ],
    )
    def test_follow_pseudo_release(self, mb, release_id, expected_country):
        album = mb.album_for_id(release_id)

        assert album
        assert album.country == expected_country


class TestMusicBrainzPlugin(MusicBrainzPluginTestMixin):
    mbid = "d2a6f856-b553-40a0-ac54-a321e8e2da99"
    RECORDING: ClassVar[mb.Recording] = recording_factory()

    @pytest.mark.parametrize(
        "plugin_config,va_likely,expected_additional_criteria",
        [
            _p({}, False, {"artist": "Artist "}, id="default"),
            _p(
                {},
                True,
                {"arid": "89ad4ac3-39f7-470e-963a-56509c546377"},
                id="va likely",
            ),
            _p(
                {"extra_tags": ["label", "catalognum"]},
                False,
                {"artist": "Artist ", "label": "abc", "catno": "ABC123"},
                id="value-based extra_tags",
            ),
            _p(
                {"extra_tags": ["alias", "tracks"]},
                False,
                {"artist": "Artist ", "alias": " Album", "tracks": "3"},
                id="non-value-based extra_tags",
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

    @pytest.mark.parametrize(
        "input,expected",
        [
            ("??-??-??", (None, None, None)),
            ("??-01-??", (None, 1, None)),
            ("??-??-02", (None, None, 2)),
            ("??-01-02", (None, 1, 2)),
            ("2010-??-01", (2010, None, 1)),
            ("2010-01-not_an_int", (2010, 1, None)),
            ("2010", (2010, None, None)),
            ("2010-01", (2010, 1, None)),
            ("2010-01-02", (2010, 1, 2)),
        ],
    )
    def test_get_date(self, input, expected):
        assert musicbrainz._get_date(input) == expected
