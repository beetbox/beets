# This file is part of beets.
# Copyright 2016, Adrian Sampson.
# Copyright 2022, Szymon "Samik" Tarasiński.
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

"""Tests for the 'beatport' plugin.
"""

import unittest
from test import _common
from test.helper import TestHelper
from datetime import timedelta

from beetsplug import beatport
from beets import library


class BeatportTest(_common.TestCase, TestHelper):
    def _make_release_response(self):
        """Returns a dict that mimics a response from the beatport API.

        The results were retrieved from:
        https://api.beatport.com/v4/docs/catalog/releases/1742984/
        The list of elements on the returned dict is incomplete, including just
        those required for the tests on this class.
        """
        result = {
            "artists": [
                {
                    "id": 326158,
                    "name": "Supersillyus",
                    "slug": "supersillyus",
                }
            ],
            "catalog_number": "GR089",
            "id": 1742984,
            "label": {
                "id": 24539,
                "name": "Gravitas Recordings",
                "slug": "gravitas-recordings"
            },
            "name": "Charade",
            "new_release_date": "2016-04-11",
            "publish_date": "2016-04-11",
            "remixers": [],
            "slug": "charade",
            "track_count": 6,
            "type": {
                "id": 1,
                "name": "Release"
            },
        }
        return result

    def _make_tracks_response(self):
        """Return a list that mimics a response from the beatport API.

        The results were retrieved from:
        https://api.beatport.com/v4/docs/catalog/releases/1742984/tracks/
        The list of elements on the returned list is incomplete, including just
        those required for the tests on this class.
        """
        results = {
            "next": None,
            "previous": None,
            "count": 6,
            "page": "1/1",
            "per_page": 10,
            "results": [
                {
                    "artists": [
                        {
                            "id": 326158,
                            "name": "Supersillyus",
                            "slug": "supersillyus",
                        }
                    ],
                    "bpm": 90,
                    "catalog_number": "GR089",
                    "genre": {
                        "id": 9,
                        "name": "Breaks / Breakbeat / UK Bass",
                        "slug": "breaks-breakbeat-uk-bass",
                    },
                    "id": 7817567,
                    "key": {
                        "camelot_number": 6,
                        "camelot_letter": "A",
                        "chord_type": {
                            "id": 1,
                            "name": "Minor",
                        },
                        "id": 6,
                        "is_sharp": False,
                        "is_flat": False,
                        "letter": "G",
                        "name": "G Minor",
                    },
                    "length": "7:05",
                    "length_ms": 425421,
                    "mix_name": "Original Mix",
                    "name": "Mirage a Trois",
                    "new_release_date": "2016-04-11",
                    "publish_date": "2016-04-11",
                    "release": {
                        "id": 1742984,
                        "name": "Charade",
                        "label": {
                            "id": 24539,
                            "name": "Gravitas Recordings",
                            "slug": "gravitas-recordings"
                        },
                        "slug": "charade"
                    },
                    "remixers": [],
                    "slug": "mirage-a-trois",
                    "sub_genre": {
                        "id": 209,
                        "name": "Glitch Hop",
                        "slug": "glitch-hop",
                    },
                },
                {
                    "artists": [
                        {
                            "id": 326158,
                            "name": "Supersillyus",
                            "slug": "supersillyus",
                        }
                    ],
                    "bpm": 100,
                    "catalog_number": "GR089",
                    "genre": {
                        "id": 9,
                        "name": "Breaks / Breakbeat / UK Bass",
                        "slug": "breaks-breakbeat-uk-bass",
                    },
                    "id": 7817568,
                    "key": {
                        "camelot_number": 9,
                        "camelot_letter": "B",
                        "chord_type": {
                            "id": 2,
                            "name": "Major",
                        },
                        "id": 21,
                        "is_sharp": False,
                        "is_flat": False,
                        "letter": "G",
                        "name": "G Major",
                    },
                    "length": "7:38",
                    "length_ms": 458000,
                    "mix_name": "Original Mix",
                    "name": "Aeon Bahamut",
                    "new_release_date": "2016-04-11",
                    "publish_date": "2016-04-11",
                    "release": {
                        "id": 1742984,
                        "name": "Charade",
                        "label": {
                            "id": 24539,
                            "name": "Gravitas Recordings",
                            "slug": "gravitas-recordings"
                        },
                        "slug": "charade"
                    },
                    "remixers": [],
                    "slug": "aeon-bahamut",
                    "sub_genre": {
                        "id": 209,
                        "name": "Glitch Hop",
                        "slug": "glitch-hop",
                    },
                },
                {
                    "artists": [
                        {
                            "id": 326158,
                            "name": "Supersillyus",
                            "slug": "supersillyus",
                        }
                    ],
                    "bpm": 141,
                    "catalog_number": "GR089",
                    "genre": {
                        "id": 9,
                        "name": "Breaks / Breakbeat / UK Bass",
                        "slug": "breaks-breakbeat-uk-bass",
                    },
                    "id": 7817569,
                    "key": {
                        "camelot_number": 7,
                        "camelot_letter": "B",
                        "chord_type": {
                            "id": 2,
                            "name": "Major",
                        },
                        "id": 19,
                        "is_sharp": False,
                        "is_flat": False,
                        "letter": "F",
                        "name": "F Major",
                    },
                    "length": "1:08",
                    "length_ms": 68571,
                    "mix_name": "Original Mix",
                    "name": "Trancendental Medication",
                    "new_release_date": "2016-04-11",
                    "publish_date": "2016-04-11",
                    "release": {
                        "id": 1742984,
                        "name": "Charade",
                        "label": {
                            "id": 24539,
                            "name": "Gravitas Recordings",
                            "slug": "gravitas-recordings"
                        },
                        "slug": "charade"
                    },
                    "remixers": [],
                    "slug": "trancendental-medication",
                    "sub_genre": {
                        "id": 209,
                        "name": "Glitch Hop",
                        "slug": "glitch-hop",
                    },
                },
                {
                    "artists": [
                        {
                            "id": 326158,
                            "name": "Supersillyus",
                            "slug": "supersillyus",
                        }
                    ],
                    "bpm": 88,
                    "catalog_number": "GR089",
                    "genre": {
                        "id": 9,
                        "name": "Breaks / Breakbeat / UK Bass",
                        "slug": "breaks-breakbeat-uk-bass",
                    },
                    "id": 7817570,
                    "key": {
                        "camelot_number": 8,
                        "camelot_letter": "A",
                        "chord_type": {
                            "id": 1,
                            "name": "Minor",
                        },
                        "id": 8,
                        "is_sharp": False,
                        "is_flat": False,
                        "letter": "A",
                        "name": "A Minor",
                    },
                    "length": "6:57",
                    "length_ms": 417913,
                    "mix_name": "Original Mix",
                    "name": "A List of Instructions for When I'm Human",
                    "new_release_date": "2016-04-11",
                    "publish_date": "2016-04-11",
                    "release": {
                        "id": 1742984,
                        "name": "Charade",
                        "label": {
                            "id": 24539,
                            "name": "Gravitas Recordings",
                            "slug": "gravitas-recordings"
                        },
                        "slug": "charade"
                    },
                    "remixers": [],
                    "slug": "a-list-of-instructions-for-when-im-human",
                    "sub_genre": {
                        "id": 209,
                        "name": "Glitch Hop",
                        "slug": "glitch-hop",
                    },
                },
                {
                    "artists": [
                        {
                            "id": 326158,
                            "name": "Supersillyus",
                            "slug": "supersillyus",
                        }
                    ],
                    "bpm": 123,
                    "catalog_number": "GR089",
                    "genre": {
                        "id": 9,
                        "name": "Breaks / Breakbeat / UK Bass",
                        "slug": "breaks-breakbeat-uk-bass",
                    },
                    "id": 7817571,
                    "key": {
                        "camelot_number": 5,
                        "camelot_letter": "B",
                        "chord_type": {
                            "id": 2,
                            "name": "Major",
                        },
                        "id": 17,
                        "is_sharp": False,
                        "is_flat": True,
                        "letter": "E",
                        "name": "Eb Major",
                    },
                    "length": "9:49",
                    "length_ms": 589875,
                    "mix_name": "Original Mix",
                    "name": "The Great Shenanigan",
                    "new_release_date": "2016-04-11",
                    "publish_date": "2016-04-11",
                    "release": {
                        "id": 1742984,
                        "name": "Charade",
                        "label": {
                            "id": 24539,
                            "name": "Gravitas Recordings",
                            "slug": "gravitas-recordings"
                        },
                        "slug": "charade"
                    },
                    "remixers": [],
                    "slug": "the-great-shenanigan",
                    "sub_genre": {
                        "id": 209,
                        "name": "Glitch Hop",
                        "slug": "glitch-hop",
                    },
                },
                {
                    "artists": [
                        {
                            "id": 326158,
                            "name": "Supersillyus",
                            "slug": "supersillyus",
                        }
                    ],
                    "bpm": 123,
                    "catalog_number": "GR089",
                    "genre": {
                        "id": 9,
                        "name": "Breaks / Breakbeat / UK Bass",
                        "slug": "breaks-breakbeat-uk-bass",
                    },
                    "id": 7817572,
                    "key": {
                        "camelot_number": 11,
                        "camelot_letter": "B",
                        "chord_type": {
                            "id": 2,
                            "name": "Major",
                        },
                        "id": 23,
                        "is_sharp": False,
                        "is_flat": False,
                        "letter": "A",
                        "name": "A Major",
                    },
                    "length": "7:05",
                    "length_ms": 425423,
                    "mix_name": "Original Mix",
                    "name": "Charade",
                    "new_release_date": "2016-04-11",
                    "publish_date": "2016-04-11",
                    "release": {
                        "id": 1742984,
                        "name": "Charade",
                        "label": {
                            "id": 24539,
                            "name": "Gravitas Recordings",
                            "slug": "gravitas-recordings"
                        },
                        "slug": "charade"
                    },
                    "remixers": [],
                    "slug": "charade",
                    "sub_genre": {
                        "id": 209,
                        "name": "Glitch Hop",
                        "slug": "glitch-hop",
                    },
                }
            ]
        }
        return results

    def setUp(self):
        self.setup_beets()
        self.load_plugins('beatport')
        self.lib = library.Library(':memory:')

        # Set up 'album'.
        response_release = self._make_release_response()
        self.album = beatport.BeatportRelease(response_release)

        # Set up 'tracks'.
        response_tracks = self._make_tracks_response()
        self.tracks = [beatport.BeatportTrack(t)
                       for t in response_tracks['results']]

        # Set up 'test_album'.
        self.test_album = self.mk_test_album()

        # Set up 'test_tracks'
        self.test_tracks = self.test_album.items()

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def mk_test_album(self):
        items = [_common.item() for _ in range(6)]
        for item in items:
            item.album = 'Charade'
            item.catalognum = 'GR089'
            item.label = 'Gravitas Recordings'
            item.artist = 'Supersillyus'
            item.year = 2016
            item.comp = False
            item.label_name = 'Gravitas Recordings'
            item.genre = 'Glitch Hop'
            item.year = 2016
            item.month = 4
            item.day = 11
            item.mix_name = 'Original Mix'

        items[0].title = 'Mirage a Trois'
        items[1].title = 'Aeon Bahamut'
        items[2].title = 'Trancendental Medication'
        items[3].title = 'A List of Instructions for When I\'m Human'
        items[4].title = 'The Great Shenanigan'
        items[5].title = 'Charade'

        items[0].length = timedelta(minutes=7, seconds=5).total_seconds()
        items[1].length = timedelta(minutes=7, seconds=38).total_seconds()
        items[2].length = timedelta(minutes=1, seconds=8).total_seconds()
        items[3].length = timedelta(minutes=6, seconds=57).total_seconds()
        items[4].length = timedelta(minutes=9, seconds=49).total_seconds()
        items[5].length = timedelta(minutes=7, seconds=5).total_seconds()

        items[0].url = 'mirage-a-trois'
        items[1].url = 'aeon-bahamut'
        items[2].url = 'trancendental-medication'
        items[3].url = 'a-list-of-instructions-for-when-im-human'
        items[4].url = 'the-great-shenanigan'
        items[5].url = 'charade'

        counter = 0
        for item in items:
            counter += 1
            item.track_number = counter

        items[0].bpm = 90
        items[1].bpm = 100
        items[2].bpm = 141
        items[3].bpm = 88
        items[4].bpm = 123
        items[5].bpm = 123

        items[0].initial_key = 'Gmin'
        items[1].initial_key = 'Gmaj'
        items[2].initial_key = 'Fmaj'
        items[3].initial_key = 'Amin'
        items[4].initial_key = 'Ebmaj'
        items[5].initial_key = 'Amaj'

        for item in items:
            self.lib.add(item)

        album = self.lib.add_album(items)
        album.store()

        return album

    # Test BeatportRelease.
    def test_album_name_applied(self):
        self.assertEqual(self.album.name, self.test_album['album'])

    def test_catalog_number_applied(self):
        self.assertEqual(self.album.catalog_number,
                         self.test_album['catalognum'])

    def test_label_applied(self):
        self.assertEqual(self.album.label.name, self.test_album['label'])

    def test_category_applied(self):
        self.assertEqual(self.album.type, 'Release')

    def test_album_url_applied(self):
        self.assertEqual(self.album.url,
                         'https://beatport.com/release/charade/1742984')

    # Test BeatportTrack.
    def test_title_applied(self):
        for track, test_track in zip(self.tracks, self.test_tracks):
            self.assertEqual(track.name, test_track.title)

    def test_mix_name_applied(self):
        for track, test_track in zip(self.tracks, self.test_tracks):
            self.assertEqual(track.mix_name, test_track.mix_name)

    def test_length_applied(self):
        for track, test_track in zip(self.tracks, self.test_tracks):
            self.assertEqual(int(track.length.total_seconds()),
                             int(test_track.length))

    def test_track_url_applied(self):
        # Specify beatport ids here because an 'item.id' is beets-internal.
        ids = [
            7817567,
            7817568,
            7817569,
            7817570,
            7817571,
            7817572,
        ]
        # Concatenate with 'id' to pass strict equality test.
        for track, test_track, id in zip(self.tracks, self.test_tracks, ids):
            self.assertEqual(
                track.url, 'https://beatport.com/track/' +
                           test_track.url + '/' + str(id))

    def test_bpm_applied(self):
        for track, test_track in zip(self.tracks, self.test_tracks):
            self.assertEqual(track.bpm, test_track.bpm)

    def test_initial_key_applied(self):
        for track, test_track in zip(self.tracks, self.test_tracks):
            self.assertEqual(track.initial_key, test_track.initial_key)

    def test_genre_applied(self):
        for track, test_track in zip(self.tracks, self.test_tracks):
            self.assertEqual(track.genre, test_track.genre)


class BeatportResponseEmptyTest(_common.TestCase, TestHelper):
    def _make_tracks_response(self):
        results = {
            "next": None,
            "previous": None,
            "count": 1,
            "page": "1/1",
            "per_page": 10,
            "results": [
                {
                    "artists": [
                        {
                            "id": 326158,
                            "name": "Supersillyus",
                            "slug": "supersillyus",
                        }
                    ],
                    "bpm": 90,
                    "catalog_number": "GR089",
                    "genre": {
                        "id": 9,
                        "name": "Breaks / Breakbeat / UK Bass",
                        "slug": "breaks-breakbeat-uk-bass",
                    },
                    "id": 7817567,
                    "key": {
                        "camelot_number": 6,
                        "camelot_letter": "A",
                        "chord_type": {
                            "id": 1,
                            "name": "Minor",
                        },
                        "id": 6,
                        "is_sharp": False,
                        "is_flat": False,
                        "letter": "G",
                        "name": "G Minor",
                    },
                    "length": "7:05",
                    "length_ms": 425421,
                    "mix_name": "Original Mix",
                    "name": "Mirage a Trois",
                    "new_release_date": "2016-04-11",
                    "publish_date": "2016-04-11",
                    "release": {
                        "id": 1742984,
                        "name": "Charade",
                        "label": {
                            "id": 24539,
                            "name": "Gravitas Recordings",
                            "slug": "gravitas-recordings"
                        },
                        "slug": "charade"
                    },
                    "remixers": [],
                    "slug": "mirage-a-trois",
                    "sub_genre": {
                        "id": 209,
                        "name": "Glitch Hop",
                        "slug": "glitch-hop",
                    },
                },
            ]
        }
        return results

    def setUp(self):
        self.setup_beets()
        self.load_plugins('beatport')
        self.lib = library.Library(':memory:')

        # Set up 'tracks'.
        self.response_tracks = self._make_tracks_response()
        self.tracks = [beatport.BeatportTrack(t)
                       for t in self.response_tracks['results']]

        # Make alias to be congruent with class `BeatportTest`.
        self.test_tracks = self.response_tracks

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_response_tracks_empty(self):
        response_tracks = []
        tracks = [beatport.BeatportTrack(t) for t in response_tracks]
        self.assertEqual(tracks, [])

    def test_sub_genre_empty_fallback(self):
        """No 'sub_genre' is provided. Test if fallback to 'genre' works.
        """
        del self.response_tracks['results'][0]['sub_genre']
        tracks = [beatport.BeatportTrack(t)
                  for t in self.response_tracks['results']]

        self.assertEqual(tracks[0].genre,
                         self.test_tracks['results'][0]['genre']['name'])

    def test_genre_empty(self):
        """No 'genre' is provided. Test if 'sub_genre' is applied.
        """
        del self.response_tracks['results'][0]['genre']
        tracks = [beatport.BeatportTrack(t)
                  for t in self.response_tracks['results']]

        self.assertEqual(tracks[0].genre,
                         self.test_tracks['results'][0]['sub_genre']['name'])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
