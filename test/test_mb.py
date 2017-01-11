# -*- coding: utf-8 -*-
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

"""Tests for MusicBrainz API wrapper.
"""
from __future__ import division, absolute_import, print_function

from test import _common
from beets.autotag import mb
from beets import config

import unittest
import mock


class MBAlbumInfoTest(_common.TestCase):
    def _make_release(self, date_str='2009', tracks=None, track_length=None,
                      track_artist=False):
        release = {
            'title': 'ALBUM TITLE',
            'id': 'ALBUM ID',
            'asin': 'ALBUM ASIN',
            'disambiguation': 'R_DISAMBIGUATION',
            'release-group': {
                'type': 'Album',
                'first-release-date': date_str,
                'id': 'RELEASE GROUP ID',
                'disambiguation': 'RG_DISAMBIGUATION',
            },
            'artist-credit': [
                {
                    'artist': {
                        'name': 'ARTIST NAME',
                        'id': 'ARTIST ID',
                        'sort-name': 'ARTIST SORT NAME',
                    },
                    'name': 'ARTIST CREDIT',
                }
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
            for i, recording in enumerate(tracks):
                track = {
                    'recording': recording,
                    'position': i + 1,
                    'number': 'A1',
                }
                if track_length:
                    # Track lengths are distinct from recording lengths.
                    track['length'] = track_length
                if track_artist:
                    # Similarly, track artists can differ from recording
                    # artists.
                    track['artist-credit'] = [
                        {
                            'artist': {
                                'name': 'TRACK ARTIST NAME',
                                'id': 'TRACK ARTIST ID',
                                'sort-name': 'TRACK ARTIST SORT NAME',
                            },
                            'name': 'TRACK ARTIST CREDIT',
                        }
                    ]
                track_list.append(track)
            release['medium-list'].append({
                'position': '1',
                'track-list': track_list,
                'format': 'FORMAT',
                'title': 'MEDIUM TITLE',
            })
        return release

    def _make_track(self, title, tr_id, duration, artist=False):
        track = {
            'title': title,
            'id': tr_id,
        }
        if duration is not None:
            track['length'] = duration
        if artist:
            track['artist-credit'] = [
                {
                    'artist': {
                        'name': 'RECORDING ARTIST NAME',
                        'id': 'RECORDING ARTIST ID',
                        'sort-name': 'RECORDING ARTIST SORT NAME',
                    },
                    'name': 'RECORDING ARTIST CREDIT',
                }
            ]
        return track

    def test_parse_release_with_year(self):
        release = self._make_release('1984')
        d = mb.album_info(release)
        self.assertEqual(d.album, 'ALBUM TITLE')
        self.assertEqual(d.album_id, 'ALBUM ID')
        self.assertEqual(d.artist, 'ARTIST NAME')
        self.assertEqual(d.artist_id, 'ARTIST ID')
        self.assertEqual(d.original_year, 1984)
        self.assertEqual(d.year, 3001)
        self.assertEqual(d.artist_credit, 'ARTIST CREDIT')

    def test_parse_release_type(self):
        release = self._make_release('1984')
        d = mb.album_info(release)
        self.assertEqual(d.albumtype, 'album')

    def test_parse_release_full_date(self):
        release = self._make_release('1987-03-31')
        d = mb.album_info(release)
        self.assertEqual(d.original_year, 1987)
        self.assertEqual(d.original_month, 3)
        self.assertEqual(d.original_day, 31)

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
        self.assertEqual(t[0].index, 1)
        self.assertEqual(t[1].medium_index, 2)
        self.assertEqual(t[1].index, 2)

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
            'number': 'A1',
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
        self.assertEqual(t[0].index, 1)
        self.assertEqual(t[1].medium, 2)
        self.assertEqual(t[1].medium_index, 1)
        self.assertEqual(t[1].index, 2)

    def test_parse_release_year_month_only(self):
        release = self._make_release('1987-03')
        d = mb.album_info(release)
        self.assertEqual(d.original_year, 1987)
        self.assertEqual(d.original_month, 3)

    def test_no_durations(self):
        tracks = [self._make_track('TITLE', 'ID', None)]
        release = self._make_release(tracks=tracks)
        d = mb.album_info(release)
        self.assertEqual(d.tracks[0].length, None)

    def test_track_length_overrides_recording_length(self):
        tracks = [self._make_track('TITLE', 'ID', 1.0 * 1000.0)]
        release = self._make_release(tracks=tracks, track_length=2.0 * 1000.0)
        d = mb.album_info(release)
        self.assertEqual(d.tracks[0].length, 2.0)

    def test_no_release_date(self):
        release = self._make_release(None)
        d = mb.album_info(release)
        self.assertFalse(d.original_year)
        self.assertFalse(d.original_month)
        self.assertFalse(d.original_day)

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
        self.assertEqual(d.albumdisambig,
                         'RG_DISAMBIGUATION, R_DISAMBIGUATION')

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

    def test_parse_recording_artist(self):
        tracks = [self._make_track('a', 'b', 1, True)]
        release = self._make_release(None, tracks=tracks)
        track = mb.album_info(release).tracks[0]
        self.assertEqual(track.artist, 'RECORDING ARTIST NAME')
        self.assertEqual(track.artist_id, 'RECORDING ARTIST ID')
        self.assertEqual(track.artist_sort, 'RECORDING ARTIST SORT NAME')
        self.assertEqual(track.artist_credit, 'RECORDING ARTIST CREDIT')

    def test_track_artist_overrides_recording_artist(self):
        tracks = [self._make_track('a', 'b', 1, True)]
        release = self._make_release(None, tracks=tracks, track_artist=True)
        track = mb.album_info(release).tracks[0]
        self.assertEqual(track.artist, 'TRACK ARTIST NAME')
        self.assertEqual(track.artist_id, 'TRACK ARTIST ID')
        self.assertEqual(track.artist_sort, 'TRACK ARTIST SORT NAME')
        self.assertEqual(track.artist_credit, 'TRACK ARTIST CREDIT')

    def test_data_source(self):
        release = self._make_release()
        d = mb.album_info(release)
        self.assertEqual(d.data_source, 'MusicBrainz')


class ParseIDTest(_common.TestCase):
    def test_parse_id_correct(self):
        id_string = "28e32c71-1450-463e-92bf-e0a46446fc11"
        out = mb._parse_id(id_string)
        self.assertEqual(out, id_string)

    def test_parse_id_non_id_returns_none(self):
        id_string = "blah blah"
        out = mb._parse_id(id_string)
        self.assertEqual(out, None)

    def test_parse_id_url_finds_id(self):
        id_string = "28e32c71-1450-463e-92bf-e0a46446fc11"
        id_url = "http://musicbrainz.org/entity/%s" % id_string
        out = mb._parse_id(id_url)
        self.assertEqual(out, id_string)


class ArtistFlatteningTest(_common.TestCase):
    def _credit_dict(self, suffix=''):
        return {
            'artist': {
                'name': 'NAME' + suffix,
                'sort-name': 'SORT' + suffix,
            },
            'name': 'CREDIT' + suffix,
        }

    def _add_alias(self, credit_dict, suffix='', locale='', primary=False):
        alias = {
            'alias': 'ALIAS' + suffix,
            'locale': locale,
            'sort-name': 'ALIASSORT' + suffix
        }
        if primary:
            alias['primary'] = 'primary'
        if 'alias-list' not in credit_dict['artist']:
            credit_dict['artist']['alias-list'] = []
        credit_dict['artist']['alias-list'].append(alias)

    def test_single_artist(self):
        a, s, c = mb._flatten_artist_credit([self._credit_dict()])
        self.assertEqual(a, 'NAME')
        self.assertEqual(s, 'SORT')
        self.assertEqual(c, 'CREDIT')

    def test_two_artists(self):
        a, s, c = mb._flatten_artist_credit(
            [self._credit_dict('a'), ' AND ', self._credit_dict('b')]
        )
        self.assertEqual(a, 'NAMEa AND NAMEb')
        self.assertEqual(s, 'SORTa AND SORTb')
        self.assertEqual(c, 'CREDITa AND CREDITb')

    def test_alias(self):
        credit_dict = self._credit_dict()
        self._add_alias(credit_dict, suffix='en', locale='en', primary=True)
        self._add_alias(credit_dict, suffix='en_GB', locale='en_GB',
                        primary=True)
        self._add_alias(credit_dict, suffix='fr', locale='fr')
        self._add_alias(credit_dict, suffix='fr_P', locale='fr', primary=True)
        self._add_alias(credit_dict, suffix='pt_BR', locale='pt_BR')

        # test no alias
        config['import']['languages'] = ['']
        flat = mb._flatten_artist_credit([credit_dict])
        self.assertEqual(flat, ('NAME', 'SORT', 'CREDIT'))

        # test en primary
        config['import']['languages'] = ['en']
        flat = mb._flatten_artist_credit([credit_dict])
        self.assertEqual(flat, ('ALIASen', 'ALIASSORTen', 'CREDIT'))

        # test en_GB en primary
        config['import']['languages'] = ['en_GB', 'en']
        flat = mb._flatten_artist_credit([credit_dict])
        self.assertEqual(flat, ('ALIASen_GB', 'ALIASSORTen_GB', 'CREDIT'))

        # test en en_GB primary
        config['import']['languages'] = ['en', 'en_GB']
        flat = mb._flatten_artist_credit([credit_dict])
        self.assertEqual(flat, ('ALIASen', 'ALIASSORTen', 'CREDIT'))

        # test fr primary
        config['import']['languages'] = ['fr']
        flat = mb._flatten_artist_credit([credit_dict])
        self.assertEqual(flat, ('ALIASfr_P', 'ALIASSORTfr_P', 'CREDIT'))

        # test for not matching non-primary
        config['import']['languages'] = ['pt_BR', 'fr']
        flat = mb._flatten_artist_credit([credit_dict])
        self.assertEqual(flat, ('ALIASfr_P', 'ALIASSORTfr_P', 'CREDIT'))


class MBLibraryTest(unittest.TestCase):
    def test_match_track(self):
        with mock.patch('musicbrainzngs.search_recordings') as p:
            p.return_value = {
                'recording-list': [{
                    'title': 'foo',
                    'id': 'bar',
                    'length': 42,
                }],
            }
            ti = list(mb.match_track('hello', 'there'))[0]

            p.assert_called_with(artist='hello', recording='there', limit=5)
            self.assertEqual(ti.title, 'foo')
            self.assertEqual(ti.track_id, 'bar')

    def test_match_album(self):
        mbid = 'd2a6f856-b553-40a0-ac54-a321e8e2da99'
        with mock.patch('musicbrainzngs.search_releases') as sp:
            sp.return_value = {
                'release-list': [{
                    'id': mbid,
                }],
            }
            with mock.patch('musicbrainzngs.get_release_by_id') as gp:
                gp.return_value = {
                    'release': {
                        'title': 'hi',
                        'id': mbid,
                        'medium-list': [{
                            'track-list': [{
                                'recording': {
                                    'title': 'foo',
                                    'id': 'bar',
                                    'length': 42,
                                },
                                'position': 9,
                                'number': 'A1',
                            }],
                            'position': 5,
                        }],
                        'artist-credit': [{
                            'artist': {
                                'name': 'some-artist',
                                'id': 'some-id',
                            },
                        }],
                        'release-group': {
                            'id': 'another-id',
                        }
                    }
                }

                ai = list(mb.match_album('hello', 'there'))[0]

                sp.assert_called_with(artist='hello', release='there', limit=5)
                gp.assert_called_with(mbid, mock.ANY)
                self.assertEqual(ai.tracks[0].title, 'foo')
                self.assertEqual(ai.album, 'hi')

    def test_match_track_empty(self):
        with mock.patch('musicbrainzngs.search_recordings') as p:
            til = list(mb.match_track(' ', ' '))
            self.assertFalse(p.called)
            self.assertEqual(til, [])

    def test_match_album_empty(self):
        with mock.patch('musicbrainzngs.search_releases') as p:
            ail = list(mb.match_album(' ', ' '))
            self.assertFalse(p.called)
            self.assertEqual(ail, [])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
