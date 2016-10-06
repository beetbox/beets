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

from test import _common
from test._common import unittest, Bag

from beetsplug.discogs import DiscogsPlugin


class DGAlbumInfoTest(_common.TestCase):
    def _make_release(self, date_str='2009', tracks=None, track_length=None,
                      track_artist=False):
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

    def test_set_media_for_tracks(self):
        tracks = [self._make_track('TITLE ONE', '1', '01:01'),
                  self._make_track('TITLE TWO', '2', '02:02')]
        release = self._make_release(tracks=tracks)

        d = DiscogsPlugin().get_album_info(release)
        t = d.tracks
        self.assertEqual(d.media, 'FORMAT')
        self.assertEqual(t[0].media, d.media)
        self.assertEqual(t[1].media, d.media)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
