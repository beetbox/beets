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

"""Tests for discogs plugin.
"""
from __future__ import division, absolute_import, print_function

import unittest
from test import _common
from test._common import Bag
from test.helper import capture_log

from beetsplug.discogs import DiscogsPlugin


class DGAlbumInfoTest(_common.TestCase):
    def _make_release(self, tracks=None):
        """Returns a Bag that mimics a discogs_client.Release. The list
        of elements on the returned Bag is incomplete, including just
        those required for the tests on this class."""
        data = {
            'id': 'ALBUM ID',
            'uri': 'ALBUM URI',
            'title': 'ALBUM TITLE',
            'year': '3001',
            'artists': [{
                'name': 'ARTIST NAME',
                'id': 'ARTIST ID',
                'join': ','
            }],
            'formats': [{
                'descriptions': ['FORMAT DESC 1', 'FORMAT DESC 2'],
                'name': 'FORMAT',
                'qty': 1
            }],
            'labels': [{
                'name': 'LABEL NAME',
                'catno': 'CATALOG NUMBER',
            }],
            'tracklist': []
        }

        if tracks:
            for recording in tracks:
                data['tracklist'].append(recording)

        return Bag(data=data,
                   # Make some fields available as properties, as they are
                   # accessed by DiscogsPlugin methods.
                   title=data['title'],
                   artists=[Bag(data=d) for d in data['artists']])

    def _make_track(self, title, position='', duration='', type_=None):
        track = {
            'title': title,
            'position': position,
            'duration': duration
        }
        if type_ is not None:
            # Test samples on discogs_client do not have a 'type_' field, but
            # the API seems to return it. Values: 'track' for regular tracks,
            # 'heading' for descriptive texts (ie. not real tracks - 12.13.2).
            track['type_'] = type_

        return track

    def _make_release_from_positions(self, positions):
        """Return a Bag that mimics a discogs_client.Release with a
        tracklist where tracks have the specified `positions`."""
        tracks = [self._make_track('TITLE%s' % i, position) for
                  (i, position) in enumerate(positions, start=1)]
        return self._make_release(tracks)

    def test_parse_media_for_tracks(self):
        tracks = [self._make_track('TITLE ONE', '1', '01:01'),
                  self._make_track('TITLE TWO', '2', '02:02')]
        release = self._make_release(tracks=tracks)

        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks
        self.assertEqual(d.media, 'FORMAT')
        self.assertEqual(t[0].media, d.media)
        self.assertEqual(t[1].media, d.media)

    def test_parse_medium_numbers_single_medium(self):
        release = self._make_release_from_positions(['1', '2'])
        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks

        self.assertEqual(d.mediums, 1)
        self.assertEqual(t[0].medium, 1)
        self.assertEqual(t[0].medium_total, 1)
        self.assertEqual(t[1].medium, 1)
        self.assertEqual(t[0].medium_total, 1)

    def test_parse_medium_numbers_two_mediums(self):
        release = self._make_release_from_positions(['1-1', '2-1'])
        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks

        self.assertEqual(d.mediums, 2)
        self.assertEqual(t[0].medium, 1)
        self.assertEqual(t[0].medium_total, 2)
        self.assertEqual(t[1].medium, 2)
        self.assertEqual(t[1].medium_total, 2)

    def test_parse_medium_numbers_two_mediums_two_sided(self):
        release = self._make_release_from_positions(['A1', 'B1', 'C1'])
        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks

        self.assertEqual(d.mediums, 2)
        self.assertEqual(t[0].medium, 1)
        self.assertEqual(t[0].medium_total, 2)
        self.assertEqual(t[0].medium_index, 1)
        self.assertEqual(t[1].medium, 1)
        self.assertEqual(t[1].medium_total, 2)
        self.assertEqual(t[1].medium_index, 2)
        self.assertEqual(t[2].medium, 2)
        self.assertEqual(t[2].medium_total, 2)
        self.assertEqual(t[2].medium_index, 1)

    def test_parse_track_indices(self):
        release = self._make_release_from_positions(['1', '2'])
        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks

        self.assertEqual(t[0].medium_index, 1)
        self.assertEqual(t[0].index, 1)
        self.assertEqual(t[0].medium_total, 1)
        self.assertEqual(t[1].medium_index, 2)
        self.assertEqual(t[1].index, 2)
        self.assertEqual(t[1].medium_total, 1)

    def test_parse_track_indices_several_media(self):
        release = self._make_release_from_positions(['1-1', '1-2', '2-1',
                                                     '3-1'])
        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks

        self.assertEqual(d.mediums, 3)
        self.assertEqual(t[0].medium_index, 1)
        self.assertEqual(t[0].index, 1)
        self.assertEqual(t[0].medium_total, 3)
        self.assertEqual(t[1].medium_index, 2)
        self.assertEqual(t[1].index, 2)
        self.assertEqual(t[1].medium_total, 3)
        self.assertEqual(t[2].medium_index, 1)
        self.assertEqual(t[2].index, 3)
        self.assertEqual(t[2].medium_total, 3)
        self.assertEqual(t[3].medium_index, 1)
        self.assertEqual(t[3].index, 4)
        self.assertEqual(t[3].medium_total, 3)

    def test_parse_position(self):
        """Test the conversion of discogs `position` to medium, medium_index
        and subtrack_index."""
        # List of tuples (discogs_position, (medium, medium_index, subindex)
        positions = [('1',       (None,   '1',  None)),
                     ('A12',     ('A',    '12', None)),
                     ('12-34',   ('12-',  '34', None)),
                     ('CD1-1',   ('CD1-', '1',  None)),
                     ('1.12',    (None,   '1',  '12')),
                     ('12.a',    (None,   '12', 'A')),
                     ('12.34',   (None,   '12', '34')),
                     ('1ab',     (None,   '1',  'AB')),
                     # Non-standard
                     ('IV',      ('IV',   None, None)),
                     ]

        d = DiscogsPlugin()
        for position, expected in positions:
            self.assertEqual(d.get_track_index(position), expected)

    def test_parse_tracklist_without_sides(self):
        """Test standard Discogs position 12.2.9#1: "without sides"."""
        release = self._make_release_from_positions(['1', '2', '3'])
        d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d.mediums, 1)
        self.assertEqual(len(d.tracks), 3)

    def test_parse_tracklist_with_sides(self):
        """Test standard Discogs position 12.2.9#2: "with sides"."""
        release = self._make_release_from_positions(['A1', 'A2', 'B1', 'B2'])
        d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d.mediums, 1)  # 2 sides = 1 LP
        self.assertEqual(len(d.tracks), 4)

    def test_parse_tracklist_multiple_lp(self):
        """Test standard Discogs position 12.2.9#3: "multiple LP"."""
        release = self._make_release_from_positions(['A1', 'A2', 'B1', 'C1'])
        d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d.mediums, 2)  # 3 sides = 1 LP + 1 LP
        self.assertEqual(len(d.tracks), 4)

    def test_parse_tracklist_multiple_cd(self):
        """Test standard Discogs position 12.2.9#4: "multiple CDs"."""
        release = self._make_release_from_positions(['1-1', '1-2', '2-1',
                                                     '3-1'])
        d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d.mediums, 3)
        self.assertEqual(len(d.tracks), 4)

    def test_parse_tracklist_non_standard(self):
        """Test non standard Discogs position."""
        release = self._make_release_from_positions(['I', 'II', 'III', 'IV'])
        d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d.mediums, 1)
        self.assertEqual(len(d.tracks), 4)

    def test_parse_tracklist_subtracks_dot(self):
        """Test standard Discogs position 12.2.9#5: "sub tracks, dots"."""
        release = self._make_release_from_positions(['1', '2.1', '2.2', '3'])
        d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d.mediums, 1)
        self.assertEqual(len(d.tracks), 3)

        release = self._make_release_from_positions(['A1', 'A2.1', 'A2.2',
                                                     'A3'])
        d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d.mediums, 1)
        self.assertEqual(len(d.tracks), 3)

    def test_parse_tracklist_subtracks_letter(self):
        """Test standard Discogs position 12.2.9#5: "sub tracks, letter"."""
        release = self._make_release_from_positions(['A1', 'A2a', 'A2b', 'A3'])
        d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d.mediums, 1)
        self.assertEqual(len(d.tracks), 3)

        release = self._make_release_from_positions(['A1', 'A2.a', 'A2.b',
                                                     'A3'])
        d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d.mediums, 1)
        self.assertEqual(len(d.tracks), 3)

    def test_parse_tracklist_subtracks_extra_material(self):
        """Test standard Discogs position 12.2.9#6: "extra material"."""
        release = self._make_release_from_positions(['1', '2', 'Video 1'])
        d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d.mediums, 2)
        self.assertEqual(len(d.tracks), 3)

    def test_parse_tracklist_subtracks_indices(self):
        """Test parsing of subtracks that include index tracks."""
        release = self._make_release_from_positions(['', '', '1.1', '1.2'])
        # Track 1: Index track with medium title
        release.data['tracklist'][0]['title'] = 'MEDIUM TITLE'
        # Track 2: Index track with track group title
        release.data['tracklist'][1]['title'] = 'TRACK GROUP TITLE'

        d = DiscogsPlugin().get_album_info(release)
        self.assertEqual(d.mediums, 1)
        self.assertEqual(d.tracks[0].disctitle, 'MEDIUM TITLE')
        self.assertEqual(len(d.tracks), 1)
        self.assertEqual(d.tracks[0].title, 'TRACK GROUP TITLE')

    def test_parse_tracklist_subtracks_nested_logical(self):
        """Test parsing of subtracks defined inside a index track that are
        logical subtracks (ie. should be grouped together into a single track).
        """
        release = self._make_release_from_positions(['1', '', '3'])
        # Track 2: Index track with track group title, and sub_tracks
        release.data['tracklist'][1]['title'] = 'TRACK GROUP TITLE'
        release.data['tracklist'][1]['sub_tracks'] = [
            self._make_track('TITLE ONE', '2.1', '01:01'),
            self._make_track('TITLE TWO', '2.2', '02:02')
        ]

        d = DiscogsPlugin().get_album_info(release)
        self.assertEqual(d.mediums, 1)
        self.assertEqual(len(d.tracks), 3)
        self.assertEqual(d.tracks[1].title, 'TRACK GROUP TITLE')

    def test_parse_tracklist_subtracks_nested_physical(self):
        """Test parsing of subtracks defined inside a index track that are
        physical subtracks (ie. should not be grouped together).
        """
        release = self._make_release_from_positions(['1', '', '4'])
        # Track 2: Index track with track group title, and sub_tracks
        release.data['tracklist'][1]['title'] = 'TRACK GROUP TITLE'
        release.data['tracklist'][1]['sub_tracks'] = [
            self._make_track('TITLE ONE', '2', '01:01'),
            self._make_track('TITLE TWO', '3', '02:02')
        ]

        d = DiscogsPlugin().get_album_info(release)
        self.assertEqual(d.mediums, 1)
        self.assertEqual(len(d.tracks), 4)
        self.assertEqual(d.tracks[1].title, 'TITLE ONE')
        self.assertEqual(d.tracks[2].title, 'TITLE TWO')

    def test_parse_tracklist_disctitles(self):
        """Test parsing of index tracks that act as disc titles."""
        release = self._make_release_from_positions(['', '1-1', '1-2', '',
                                                     '2-1'])
        # Track 1: Index track with medium title (Cd1)
        release.data['tracklist'][0]['title'] = 'MEDIUM TITLE CD1'
        # Track 4: Index track with medium title (Cd2)
        release.data['tracklist'][3]['title'] = 'MEDIUM TITLE CD2'

        d = DiscogsPlugin().get_album_info(release)
        self.assertEqual(d.mediums, 2)
        self.assertEqual(d.tracks[0].disctitle, 'MEDIUM TITLE CD1')
        self.assertEqual(d.tracks[1].disctitle, 'MEDIUM TITLE CD1')
        self.assertEqual(d.tracks[2].disctitle, 'MEDIUM TITLE CD2')
        self.assertEqual(len(d.tracks), 3)

    def test_parse_minimal_release(self):
        """Test parsing of a release with the minimal amount of information."""
        data = {'id': 123,
                'tracklist': [self._make_track('A', '1', '01:01')],
                'artists': [{'name': 'ARTIST NAME', 'id': 321, 'join': ''}],
                'title': 'TITLE'}
        release = Bag(data=data,
                      title=data['title'],
                      artists=[Bag(data=d) for d in data['artists']])
        d = DiscogsPlugin().get_album_info(release)
        self.assertEqual(d.artist, 'ARTIST NAME')
        self.assertEqual(d.album, 'TITLE')
        self.assertEqual(len(d.tracks), 1)

    def test_parse_release_without_required_fields(self):
        """Test parsing of a release that does not have the required fields."""
        release = Bag(data={}, refresh=lambda *args: None)
        with capture_log() as logs:
            d = DiscogsPlugin().get_album_info(release)

        self.assertEqual(d, None)
        self.assertIn('Release does not contain the required fields', logs[0])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
