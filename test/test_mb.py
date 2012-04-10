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
from _common import unittest
from beets.autotag import mb

class MBAlbumInfoTest(unittest.TestCase):
    def _make_release(self, date_str='2009', tracks=None):
        release = {
            'title': 'ALBUM TITLE',
            'id': 'ALBUM ID',
            'asin': 'ALBUM ASIN',
            'release-group': {
                'type': 'Album',
                'first-release-date': date_str,
                'id': 'RELEASE GROUP ID',
                'disambiguation': 'DISAMBIGUATION',
            },
            'artist-credit': [
                {'artist': {
                    'name': 'ARTIST NAME',
                    'id': 'ARTIST ID',
                    'sort-name': 'ARTIST SORT NAME',
                }}
            ],
            'date': '3001',
            'medium-list': [],
            'label-info-list': [{
                'catalog-number': 'CATALOG NUMBER',
                'label': {'name': 'LABEL NAME'},
            }],
            'text-representation': {
                'script': 'SCRIPT',
                'language': 'LANGUAGE',
            },
            'country': 'COUNTRY',
            'status': 'STATUS',
        }
        if tracks:
            track_list = []
            for i, track in enumerate(tracks):
                track_list.append({
                    'recording': track,
                    'position': str(i+1),
                })
            release['medium-list'].append({
                'position': '1',
                'track-list': track_list,
                'format': 'FORMAT',
                'title': 'MEDIUM TITLE',
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

    def test_parse_track_indices(self):
        tracks = [self._make_track('TITLE ONE', 'ID ONE', 100.0 * 1000.0),
                  self._make_track('TITLE TWO', 'ID TWO', 200.0 * 1000.0)]
        release = self._make_release(tracks=tracks)

        d = mb.album_info(release)
        t = d.tracks
        self.assertEqual(t[0].medium_index, 1)
        self.assertEqual(t[1].medium_index, 2)

    def test_parse_medium_numbers_single_medium(self):
        tracks = [self._make_track('TITLE ONE', 'ID ONE', 100.0 * 1000.0),
                  self._make_track('TITLE TWO', 'ID TWO', 200.0 * 1000.0)]
        release = self._make_release(tracks=tracks)

        d = mb.album_info(release)
        self.assertEqual(d.mediums, 1)
        t = d.tracks
        self.assertEqual(t[0].medium, 1)
        self.assertEqual(t[1].medium, 1)

    def test_parse_medium_numbers_two_mediums(self):
        tracks = [self._make_track('TITLE ONE', 'ID ONE', 100.0 * 1000.0),
                  self._make_track('TITLE TWO', 'ID TWO', 200.0 * 1000.0)]
        release = self._make_release(tracks=[tracks[0]])
        second_track_list = [{
            'recording': tracks[1],
            'position': '1',
        }]
        release['medium-list'].append({
            'position': '2',
            'track-list': second_track_list,
        })

        d = mb.album_info(release)
        self.assertEqual(d.mediums, 2)
        t = d.tracks
        self.assertEqual(t[0].medium, 1)
        self.assertEqual(t[0].medium_index, 1)
        self.assertEqual(t[1].medium, 2)
        self.assertEqual(t[1].medium_index, 1)

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

    def test_parse_artist_sort_name(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertEqual(d.artist_sort, 'ARTIST SORT NAME')

    def test_parse_releasegroupid(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertEqual(d.releasegroup_id, 'RELEASE GROUP ID')

    def test_parse_asin(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertEqual(d.asin, 'ALBUM ASIN')

    def test_parse_catalognum(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertEqual(d.catalognum, 'CATALOG NUMBER')

    def test_parse_textrepr(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertEqual(d.script, 'SCRIPT')
        self.assertEqual(d.language, 'LANGUAGE')

    def test_parse_country(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertEqual(d.country, 'COUNTRY')

    def test_parse_status(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertEqual(d.albumstatus, 'STATUS')

    def test_parse_media(self):
        tracks = [self._make_track('TITLE ONE', 'ID ONE', 100.0 * 1000.0),
                  self._make_track('TITLE TWO', 'ID TWO', 200.0 * 1000.0)]
        release = self._make_release(None, tracks=tracks)
        d = mb.album_info(release)
        self.assertEqual(d.media, 'FORMAT')

    def test_parse_disambig(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertEqual(d.albumdisambig, 'DISAMBIGUATION')

    def test_parse_disctitle(self):
        tracks = [self._make_track('TITLE ONE', 'ID ONE', 100.0 * 1000.0),
                  self._make_track('TITLE TWO', 'ID TWO', 200.0 * 1000.0)]
        release = self._make_release(None, tracks=tracks)
        d = mb.album_info(release)
        t = d.tracks
        self.assertEqual(t[0].disctitle, 'MEDIUM TITLE')
        self.assertEqual(t[1].disctitle, 'MEDIUM TITLE')

    def test_missing_language(self):
        release = self._make_release(None)
        del release['text-representation']['language']
        d = mb.album_info(release)
        self.assertEqual(d.language, None)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
