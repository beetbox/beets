# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

"""Tests for MusicBrainz API wrapper.
"""
import unittest

import _common
from beets.autotag import mb

class MBAlbumInfoTest(unittest.TestCase):
    def _make_release(self, date_str='2009', tracks=None):
        release = {
            'title': 'ALBUM TITLE',
            'id': 'ALBUM ID',
            'release-group': {
                'type': 'Album',
                'first-release-date': date_str,
            },
            'artist-credit': [
                {'artist': {'name': 'ARTIST NAME', 'id': 'ARTIST ID'}}
            ],
            'date': '3001',
            'medium-list': [],
        }
        if tracks:
            release['medium-list'].append({
                'track-list': [{'recording': track} for track in tracks]
            })
        return release

    def _make_track(self, title, tr_id, duration):
        track = {
            'title': title,
            'id': tr_id,
        }
        if duration is not None:
            track['length'] = duration
        return track
    
    def test_parse_release_with_year(self):
        release = self._make_release('1984')
        d = mb.album_info(release)
        self.assertEqual(d.album, 'ALBUM TITLE')
        self.assertEqual(d.album_id, 'ALBUM ID')
        self.assertEqual(d.artist, 'ARTIST NAME')
        self.assertEqual(d.artist_id, 'ARTIST ID')
        self.assertEqual(d.year, 1984)

    def test_parse_release_type(self):
        release = self._make_release('1984')
        d = mb.album_info(release)
        self.assertEqual(d.albumtype, 'album')

    def test_parse_release_full_date(self):
        release = self._make_release('1987-03-31')
        d = mb.album_info(release)
        self.assertEqual(d.year, 1987)
        self.assertEqual(d.month, 3)
        self.assertEqual(d.day, 31)

    def test_parse_tracks(self):
        tracks = [self._make_track('TITLE ONE', 'ID ONE', 100.0 * 1000.0),
                  self._make_track('TITLE TWO', 'ID TWO', 200.0 * 1000.0)]
        release = self._make_release(tracks=tracks)

        d = mb.album_info(release)
        t = d.tracks
        self.assertEqual(len(t), 2)
        self.assertEqual(t[0].title, 'TITLE ONE')
        self.assertEqual(t[0].track_id, 'ID ONE')
        self.assertEqual(t[0].length, 100.0)
        self.assertEqual(t[1].title, 'TITLE TWO')
        self.assertEqual(t[1].track_id, 'ID TWO')
        self.assertEqual(t[1].length, 200.0)

    def test_parse_release_year_month_only(self):
        release = self._make_release('1987-03')
        d = mb.album_info(release)
        self.assertEqual(d.year, 1987)
        self.assertEqual(d.month, 3)
    
    def test_no_durations(self):
        tracks = [self._make_track('TITLE', 'ID', None)]
        release = self._make_release(tracks=tracks)
        d = mb.album_info(release)
        self.assertEqual(d.tracks[0].length, None)

    def test_no_release_date(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertFalse(d.year)
        self.assertFalse(d.month)
        self.assertFalse(d.day)

    def test_various_artists_defaults_false(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertFalse(d.va)

    def test_detect_various_artists(self):
        release = self._make_release(None)
        release['artist-credit'][0]['artist']['id'] = \
            mb.VARIOUS_ARTISTS_ID
        d = mb.album_info(release)
        self.assertTrue(d.va)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
