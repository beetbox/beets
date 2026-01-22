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


class MusicBrainzTestCase(BeetsTestCase):
    def setUp(self):
        super().setUp()
        self.mb = musicbrainz.MusicBrainzPlugin()
        self.config["match"]["preferred"]["countries"] = ["US"]

    @staticmethod
    def _make_release(
        date_str="2009",
        recordings=None,
        track_length=None,
        track_artist=False,
        multi_artist_credit=False,
        data_tracks=None,
        medium_format="FORMAT",
    ):
        release = {
            "title": "ALBUM TITLE",
            "id": "ALBUM ID",
            "asin": "ALBUM ASIN",
            "disambiguation": "R_DISAMBIGUATION",
            "release_group": {
                "primary_type": "Album",
                "first_release_date": date_str,
                "id": "RELEASE GROUP ID",
                "disambiguation": "RG_DISAMBIGUATION",
            },
            "artist_credit": [artist_credit_factory(artist__id_base=10)],
            "date": "3001",
            "media": [],
            "genres": [{"count": 1, "name": "GENRE"}],
            "tags": [{"count": 1, "name": "TAG"}],
            "label_info": [
                {
                    "catalog_number": "CATALOG NUMBER",
                    "label": {"name": "LABEL NAME"},
                }
            ],
            "text_representation": {
                "script": "SCRIPT",
                "language": "LANGUAGE",
            },
            "country": "COUNTRY",
            "status": "STATUS",
            "barcode": "BARCODE",
            "release_events": [{"area": None, "date": "2021-03-26"}],
        }

        if multi_artist_credit:
            release["artist_credit"][0]["joinphrase"] = " & "
            release["artist_credit"].append(
                artist_credit_factory(artist__name="Other Artist")
            )

        i = 0
        track_list = []
        if recordings:
            for recording in recordings:
                i += 1
                track = {
                    "id": f"RELEASE TRACK ID {i}",
                    "recording": recording,
                    "position": i,
                    "number": "A1",
                }
                if track_length:
                    # Track lengths are distinct from recording lengths.
                    track["length"] = track_length
                if track_artist:
                    # Similarly, track artists can differ from recording
                    # artists.
                    track["artist_credit"] = [
                        artist_credit_factory(artist__name="Track Artist")
                    ]

                    if multi_artist_credit:
                        track["artist_credit"][0]["joinphrase"] = " & "
                        track["artist_credit"].append(
                            artist_credit_factory(
                                artist__name="Other Track Artist",
                                artist__index=2,
                            )
                        )

                track_list.append(track)
        data_track_list = []
        if data_tracks:
            for recording in data_tracks:
                i += 1
                data_track = {
                    "id": f"RELEASE TRACK ID {i}",
                    "recording": recording,
                    "position": i,
                    "number": "A1",
                }
                data_track_list.append(data_track)
        release["media"].append(
            {
                "position": "1",
                "tracks": track_list,
                "data_tracks": data_track_list,
                "format": medium_format,
                "title": "MEDIUM TITLE",
            }
        )
        return release

    @staticmethod
    def _make_recording(
        title,
        tr_id,
        duration,
        video=False,
        disambiguation="",
        remixer=False,
        multi_artist_credit=False,
    ) -> mb.Recording:
        recording: mb.Recording = {
            "title": title,
            "id": tr_id,
            "length": duration,
            "video": video,
            "disambiguation": disambiguation,
            "isrcs": [],
            "aliases": [],
            "artist_credit": [
                artist_credit_factory(artist__name="Recording Artist")
            ],
        }
        if multi_artist_credit:
            recording["artist_credit"][0]["joinphrase"] = " & "
            recording["artist_credit"].append(
                artist_credit_factory(
                    artist__name="Other Recording Artist",
                    artist__index=2,
                )
            )
        if remixer:
            recording["artist_relations"] = [
                {
                    "type": "remixer",
                    "type_id": "RELATION TYPE ID",
                    "direction": "backward",
                    "artist": {
                        "id": "RECORDING REMIXER ARTIST ID",
                        "type": "Person",
                        "name": "RECORDING REMIXER ARTIST NAME",
                        "sort_name": "RECORDING REMIXER ARTIST SORT NAME",
                        "country": "GB",
                        "disambiguation": "",
                        "type_id": "b6e035f4-3ce9-331c-97df-83397230b0df",
                    },
                    "attribute_ids": {},
                    "attribute_values": {},
                    "attributes": [],
                    "begin": None,
                    "end": None,
                    "ended": False,
                    "source_credit": "",
                    "target_credit": "",
                }
            ]
        return recording


class MBAlbumInfoTest(MusicBrainzTestCase):
    def test_parse_release_with_year(self):
        release = self._make_release("1984")
        d = self.mb.album_info(release)
        assert d.album == "ALBUM TITLE"
        assert d.album_id == "ALBUM ID"
        assert d.artist == "Artist"
        assert d.artist_id == "00000000-0000-0000-0000-000000000011"
        assert d.original_year == 1984
        assert d.year == 3001
        assert d.artist_credit == "Artist Credit"

    def test_parse_release_type(self):
        release = self._make_release("1984")
        d = self.mb.album_info(release)
        assert d.albumtype == "album"

    def test_parse_release_full_date(self):
        release = self._make_release("1987-03-31")
        d = self.mb.album_info(release)
        assert d.original_year == 1987
        assert d.original_month == 3
        assert d.original_day == 31

    def test_parse_tracks(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(recordings=recordings)

        d = self.mb.album_info(release)
        t = d.tracks
        assert len(t) == 2
        assert t[0].title == "TITLE ONE"
        assert t[0].track_id == "ID ONE"
        assert t[0].length == 100.0
        assert t[1].title == "TITLE TWO"
        assert t[1].track_id == "ID TWO"
        assert t[1].length == 200.0

    def test_parse_track_indices(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(recordings=recordings)

        d = self.mb.album_info(release)
        t = d.tracks
        assert t[0].medium_index == 1
        assert t[0].index == 1
        assert t[1].medium_index == 2
        assert t[1].index == 2

    def test_parse_medium_numbers_single_medium(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(recordings=recordings)

        d = self.mb.album_info(release)
        assert d.mediums == 1
        t = d.tracks
        assert t[0].medium == 1
        assert t[1].medium == 1

    def test_parse_medium_numbers_two_mediums(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(recordings=[recordings[0]])
        second_track_list = [
            {
                "id": "RELEASE TRACK ID 2",
                "recording": recordings[1],
                "position": "1",
                "number": "A1",
            }
        ]
        release["media"].append(
            {
                "position": "2",
                "tracks": second_track_list,
            }
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
        release = self._make_release("1987-03")
        d = self.mb.album_info(release)
        assert d.original_year == 1987
        assert d.original_month == 3

    def test_no_durations(self):
        recordings = [self._make_recording("TITLE", "ID", None)]
        release = self._make_release(recordings=recordings)
        d = self.mb.album_info(release)
        assert d.tracks[0].length is None

    def test_track_length_overrides_recording_length(self):
        recordings = [self._make_recording("TITLE", "ID", 1.0 * 1000.0)]
        release = self._make_release(
            recordings=recordings, track_length=2.0 * 1000.0
        )
        d = self.mb.album_info(release)
        assert d.tracks[0].length == 2.0

    def test_no_release_date(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert not d.original_year
        assert not d.original_month
        assert not d.original_day

    def test_various_artists_defaults_false(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert not d.va

    def test_detect_various_artists(self):
        release = self._make_release(None)
        release["artist_credit"][0]["artist"]["id"] = (
            musicbrainz.VARIOUS_ARTISTS_ID
        )
        d = self.mb.album_info(release)
        assert d.va

    def test_parse_artist_sort_name(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert d.artist_sort == "Artist, The"

    def test_parse_releasegroupid(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert d.releasegroup_id == "RELEASE GROUP ID"

    def test_parse_asin(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert d.asin == "ALBUM ASIN"

    def test_parse_catalognum(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert d.catalognum == "CATALOG NUMBER"

    def test_parse_textrepr(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert d.script == "SCRIPT"
        assert d.language == "LANGUAGE"

    def test_parse_country(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert d.country == "COUNTRY"

    def test_parse_status(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert d.albumstatus == "STATUS"

    def test_parse_barcode(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert d.barcode == "BARCODE"

    def test_parse_media(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(None, recordings=recordings)
        d = self.mb.album_info(release)
        assert d.media == "FORMAT"

    def test_parse_disambig(self):
        release = self._make_release(None)
        d = self.mb.album_info(release)
        assert d.albumdisambig == "R_DISAMBIGUATION"
        assert d.releasegroupdisambig == "RG_DISAMBIGUATION"

    def test_parse_disctitle(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(None, recordings=recordings)
        d = self.mb.album_info(release)
        t = d.tracks
        assert t[0].disctitle == "MEDIUM TITLE"
        assert t[1].disctitle == "MEDIUM TITLE"

    def test_missing_language(self):
        release = self._make_release(None)
        del release["text_representation"]["language"]
        d = self.mb.album_info(release)
        assert d.language is None

    def test_parse_recording_artist(self):
        recordings = [self._make_recording("a", "b", 1)]
        release = self._make_release(None, recordings=recordings)
        track = self.mb.album_info(release).tracks[0]
        assert track.artist == "Recording Artist"
        assert track.artist_id == "00000000-0000-0000-0000-000000000001"
        assert track.artist_sort == "Recording Artist, The"
        assert track.artist_credit == "Recording Artist Credit"

    def test_parse_recording_artist_multi(self):
        recordings = [
            self._make_recording("a", "b", 1, multi_artist_credit=True)
        ]
        release = self._make_release(None, recordings=recordings)
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
        recordings = [self._make_recording("a", "b", 1)]
        release = self._make_release(
            None, recordings=recordings, track_artist=True
        )
        track = self.mb.album_info(release).tracks[0]
        assert track.artist == "Track Artist"
        assert track.artist_id == "00000000-0000-0000-0000-000000000001"
        assert track.artist_sort == "Track Artist, The"
        assert track.artist_credit == "Track Artist Credit"

    def test_track_artist_overrides_recording_artist_multi(self):
        recordings = [
            self._make_recording("a", "b", 1, multi_artist_credit=True)
        ]
        release = self._make_release(
            None,
            recordings=recordings,
            track_artist=True,
            multi_artist_credit=True,
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
        recordings = [self._make_recording("a", "b", 1, remixer=True)]
        release = self._make_release(None, recordings=recordings)
        track = self.mb.album_info(release).tracks[0]
        assert track.remixer == "RECORDING REMIXER ARTIST NAME"

    def test_data_source(self):
        release = self._make_release()
        d = self.mb.album_info(release)
        assert d.data_source == "MusicBrainz"

    def test_genres(self):
        config["musicbrainz"]["genres"] = True
        config["musicbrainz"]["genres_tag"] = "genre"
        release = self._make_release()
        d = self.mb.album_info(release)
        assert d.genre == "GENRE"

    def test_tags(self):
        config["musicbrainz"]["genres"] = True
        config["musicbrainz"]["genres_tag"] = "tag"
        release = self._make_release()
        d = self.mb.album_info(release)
        assert d.genre == "TAG"

    def test_no_genres(self):
        config["musicbrainz"]["genres"] = False
        release = self._make_release()
        d = self.mb.album_info(release)
        assert d.genre is None

    def test_ignored_media(self):
        config["match"]["ignored_media"] = ["IGNORED1", "IGNORED2"]
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(
            recordings=recordings, medium_format="IGNORED1"
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 0

    def test_no_ignored_media(self):
        config["match"]["ignored_media"] = ["IGNORED1", "IGNORED2"]
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(
            recordings=recordings, medium_format="NON-IGNORED"
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 2

    def test_skip_data_track(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording(
                "[data track]", "ID DATA TRACK", 100.0 * 1000.0
            ),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(recordings=recordings)
        d = self.mb.album_info(release)
        assert len(d.tracks) == 2
        assert d.tracks[0].title == "TITLE ONE"
        assert d.tracks[1].title == "TITLE TWO"

    def test_skip_audio_data_tracks_by_default(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        data_tracks = [
            self._make_recording(
                "TITLE AUDIO DATA", "ID DATA TRACK", 100.0 * 1000.0
            )
        ]
        release = self._make_release(
            recordings=recordings, data_tracks=data_tracks
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 2
        assert d.tracks[0].title == "TITLE ONE"
        assert d.tracks[1].title == "TITLE TWO"

    def test_no_skip_audio_data_tracks_if_configured(self):
        config["match"]["ignore_data_tracks"] = False
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        data_tracks = [
            self._make_recording(
                "TITLE AUDIO DATA", "ID DATA TRACK", 100.0 * 1000.0
            )
        ]
        release = self._make_release(
            recordings=recordings, data_tracks=data_tracks
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 3
        assert d.tracks[0].title == "TITLE ONE"
        assert d.tracks[1].title == "TITLE TWO"
        assert d.tracks[2].title == "TITLE AUDIO DATA"

    def test_skip_video_tracks_by_default(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording(
                "TITLE VIDEO", "ID VIDEO", 100.0 * 1000.0, video=True
            ),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(recordings=recordings)
        d = self.mb.album_info(release)
        assert len(d.tracks) == 2
        assert d.tracks[0].title == "TITLE ONE"
        assert d.tracks[1].title == "TITLE TWO"

    def test_skip_video_data_tracks_by_default(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        data_tracks = [
            self._make_recording(
                "TITLE VIDEO", "ID VIDEO", 100.0 * 1000.0, True
            )
        ]
        release = self._make_release(
            recordings=recordings, data_tracks=data_tracks
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 2
        assert d.tracks[0].title == "TITLE ONE"
        assert d.tracks[1].title == "TITLE TWO"

    def test_no_skip_video_tracks_if_configured(self):
        config["match"]["ignore_data_tracks"] = False
        config["match"]["ignore_video_tracks"] = False
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording(
                "TITLE VIDEO", "ID VIDEO", 100.0 * 1000.0, True
            ),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        release = self._make_release(recordings=recordings)
        d = self.mb.album_info(release)
        assert len(d.tracks) == 3
        assert d.tracks[0].title == "TITLE ONE"
        assert d.tracks[1].title == "TITLE VIDEO"
        assert d.tracks[2].title == "TITLE TWO"

    def test_no_skip_video_data_tracks_if_configured(self):
        config["match"]["ignore_data_tracks"] = False
        config["match"]["ignore_video_tracks"] = False
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording("TITLE TWO", "ID TWO", 200.0 * 1000.0),
        ]
        data_tracks = [
            self._make_recording(
                "TITLE VIDEO", "ID VIDEO", 100.0 * 1000.0, True
            )
        ]
        release = self._make_release(
            recordings=recordings, data_tracks=data_tracks
        )
        d = self.mb.album_info(release)
        assert len(d.tracks) == 3
        assert d.tracks[0].title == "TITLE ONE"
        assert d.tracks[1].title == "TITLE TWO"
        assert d.tracks[2].title == "TITLE VIDEO"

    def test_track_disambiguation(self):
        recordings = [
            self._make_recording("TITLE ONE", "ID ONE", 100.0 * 1000.0),
            self._make_recording(
                "TITLE TWO",
                "ID TWO",
                200.0 * 1000.0,
                disambiguation="SECOND TRACK",
            ),
        ]
        release = self._make_release(recordings=recordings)

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
            artist_credit_factory(
                artist__name="Other Artist", artist__id_suffix="1"
            ),
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
        side_effect = [
            {
                "title": "pseudo",
                "id": "d2a6f856-b553-40a0-ac54-a321e8e2da02",
                "status": "Pseudo-Release",
                "media": [
                    {
                        "tracks": [
                            {
                                "id": "baz",
                                "recording": self._make_recording(
                                    "translated title", "bar", 42
                                ),
                                "position": 9,
                                "number": "A1",
                            }
                        ],
                        "position": 5,
                    }
                ],
                "artist_credit": [artist_credit_factory()],
                "release_group": {
                    "id": "another-id",
                },
                "release_relations": [
                    {
                        "type": "transl-tracklisting",
                        "direction": "backward",
                        "release": {
                            "id": "d2a6f856-b553-40a0-ac54-a321e8e2da01"
                        },
                    }
                ],
            },
            {
                "title": "actual",
                "id": "d2a6f856-b553-40a0-ac54-a321e8e2da01",
                "status": "Official",
                "media": [
                    {
                        "tracks": [
                            {
                                "id": "baz",
                                "recording": self._make_recording(
                                    "original title", "bar", 42
                                ),
                                "position": 9,
                                "number": "A1",
                            }
                        ],
                        "position": 5,
                    }
                ],
                "artist_credit": [artist_credit_factory()],
                "release_group": {
                    "id": "another-id",
                },
                "country": "COUNTRY",
            },
        ]

        with mock.patch(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_release"
        ) as gp:
            gp.side_effect = side_effect
            album = self.mb.album_for_id("d2a6f856-b553-40a0-ac54-a321e8e2da02")
            assert album.country == "COUNTRY"

    def test_pseudo_releases_with_empty_links(self):
        side_effect = [
            {
                "title": "pseudo",
                "id": "d2a6f856-b553-40a0-ac54-a321e8e2da02",
                "status": "Pseudo-Release",
                "media": [
                    {
                        "tracks": [
                            {
                                "id": "baz",
                                "recording": self._make_recording(
                                    "translated title", "bar", 42
                                ),
                                "position": 9,
                                "number": "A1",
                            }
                        ],
                        "position": 5,
                    }
                ],
                "artist_credit": [artist_credit_factory()],
                "release_group": {
                    "id": "another-id",
                },
            }
        ]

        with mock.patch(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_release"
        ) as gp:
            gp.side_effect = side_effect
            album = self.mb.album_for_id("d2a6f856-b553-40a0-ac54-a321e8e2da02")
            assert album.country is None

    def test_pseudo_releases_without_links(self):
        side_effect = [
            {
                "title": "pseudo",
                "id": "d2a6f856-b553-40a0-ac54-a321e8e2da02",
                "status": "Pseudo-Release",
                "media": [
                    {
                        "tracks": [
                            {
                                "id": "baz",
                                "recording": self._make_recording(
                                    "translated title", "bar", 42
                                ),
                                "position": 9,
                                "number": "A1",
                            }
                        ],
                        "position": 5,
                    }
                ],
                "artist_credit": [artist_credit_factory()],
                "release_group": {
                    "id": "another-id",
                },
            }
        ]

        with mock.patch(
            "beetsplug._utils.musicbrainz.MusicBrainzAPI.get_release"
        ) as gp:
            gp.side_effect = side_effect
            album = self.mb.album_for_id("d2a6f856-b553-40a0-ac54-a321e8e2da02")
            assert album.country is None

    def test_pseudo_releases_with_unsupported_links(self):
        side_effect = [
            {
                "title": "pseudo",
                "id": "d2a6f856-b553-40a0-ac54-a321e8e2da02",
                "status": "Pseudo-Release",
                "media": [
                    {
                        "tracks": [
                            {
                                "id": "baz",
                                "recording": self._make_recording(
                                    "translated title", "bar", 42
                                ),
                                "position": 9,
                                "number": "A1",
                            }
                        ],
                        "position": 5,
                    }
                ],
                "artist_credit": [artist_credit_factory()],
                "release_group": {
                    "id": "another-id",
                },
                "release_relations": [
                    {
                        "type": "remaster",
                        "direction": "backward",
                        "release": {
                            "id": "d2a6f856-b553-40a0-ac54-a321e8e2da01"
                        },
                    }
                ],
            }
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
    RECORDING: ClassVar[mb.Recording] = MusicBrainzTestCase._make_recording(
        "foo", "00000000-0000-0000-0000-000000000000", 42
    )

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
            lambda *_, **__: {
                "title": "hi",
                "id": self.mbid,
                "status": "status",
                "media": [
                    {
                        "tracks": [
                            {
                                "id": "baz",
                                "recording": self.RECORDING,
                                "position": 9,
                                "number": "A1",
                            }
                        ],
                        "position": 5,
                    }
                ],
                "artist_credit": [artist_credit_factory()],
                "release_group": {"id": "another-id"},
            },
        )
        candidates = list(mb.candidates([], "hello", "there", False))

        assert len(candidates) == 1
        assert candidates[0].tracks[0].track_id == self.RECORDING["id"]
        assert candidates[0].album == "hi"

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
