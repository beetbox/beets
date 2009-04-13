# This file is part of beets.
# Copyright 2009, Adrian Sampson.
# 
# Beets is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Beets is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with beets.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for autotagging and MusicBrainz functionality.
"""

import unittest
import sys
import time
import musicbrainz2.model
sys.path.append('..')
from beets import autotag
from beets.autotag import mb
from beets.library import Item

class AutotagTest(unittest.TestCase):
    def test_likely_metadata_finds_pluralities(self):
        items = [Item({'artist': 'The Beetles', 'album': 'The White Album'}),
                 Item({'artist': 'The Beatles', 'album': 'The White Album'}),
                 Item({'artist': 'The Beatles', 'album': 'Teh White Album'})]
        l_artist, l_album = autotag.likely_metadata(items)
        self.assertEqual(l_artist, 'The Beatles')
        self.assertEqual(l_album, 'The White Album')

class MBQueryWaitTest(unittest.TestCase):
    def setup(self):
        # simulate startup
        mb.last_query_time = 0.0

    def test_do_not_wait_initially(self):
        time1 = time.time()
        mb._query_wait()
        time2 = time.time()
        self.assertTrue(time2 - time1 < 1.0)

    def test_second_rapid_query_waits(self):
        mb._query_wait()
        time1 = time.time()
        mb._query_wait()
        time2 = time.time()
        self.assertTrue(time2 - time1 > 1.0)

    def test_second_distant_query_does_not_wait(self):
        mb._query_wait()
        time.sleep(1.0)
        time1 = time.time()
        mb._query_wait()
        time2 = time.time()
        self.assertTrue(time2 - time1 < 1.0)


def make_release():
    release = musicbrainz2.model.Release()
    release.title = 'ALBUM TITLE'
    release.id = 'ALBUM ID'
    release.artist = musicbrainz2.model.Artist()
    release.artist.name = 'ARTIST NAME'
    release.artist.id = 'ARTIST ID'
    return release

class MBReleaseDictTest(unittest.TestCase):
    def _make_release(self, date_str='2009'):
        release = musicbrainz2.model.Release()
        release.title = 'ALBUM TITLE'
        release.id = 'ALBUM ID'
        release.artist = musicbrainz2.model.Artist()
        release.artist.name = 'ARTIST NAME'
        release.artist.id = 'ARTIST ID'

        event = musicbrainz2.model.ReleaseEvent()
        event.date = date_str
        release.releaseEvents.append(event)

        return release

    def _make_track(self, title, tr_id, duration):
        track = musicbrainz2.model.Track()
        track.title = title
        track.id = tr_id
        track.duration = duration
        return track
    
    def test_parse_release_with_year(self):
        release = self._make_release('1984')
        d = mb.release_dict(release)
        self.assertEqual(d['album'], 'ALBUM TITLE')
        self.assertEqual(d['album_id'], 'ALBUM ID')
        self.assertEqual(d['artist'], 'ARTIST NAME')
        self.assertEqual(d['artist_id'], 'ARTIST ID')
        self.assertEqual(d['year'], 1984)

    def test_parse_release_full_date(self):
        release = self._make_release('1987-03-31')
        d = mb.release_dict(release)
        self.assertEqual(d['year'], 1987)
        self.assertEqual(d['month'], 3)
        self.assertEqual(d['day'], 31)

    def test_parse_tracks(self):
        release = self._make_release()
        tracks = [self._make_track('TITLE ONE', 'ID ONE', 100.0 * 1000.0),
                  self._make_track('TITLE TWO', 'ID TWO', 200.0 * 1000.0)]
        d = mb.release_dict(release, tracks)
        t = d['tracks']
        self.assertEqual(len(t), 2)
        self.assertEqual(t[0]['title'], 'TITLE ONE')
        self.assertEqual(t[0]['id'], 'ID ONE')
        self.assertEqual(t[0]['length'], 100.0)
        self.assertEqual(t[1]['title'], 'TITLE TWO')
        self.assertEqual(t[1]['id'], 'ID TWO')
        self.assertEqual(t[1]['length'], 200.0)

    def test_parse_release_year_month_only(self):
        release = self._make_release('1987-03')
        d = mb.release_dict(release)
        self.assertEqual(d['year'], 1987)
        self.assertEqual(d['month'], 3)

class MBWhiteBoxTest(unittest.TestCase):
    def test_match_album_finds_el_producto(self):
        a = mb.match_album('the avalanches', 'el producto')
        self.assertEqual(a['album'], 'El Producto')
        self.assertEqual(a['artist'], 'The Avalanches')
        self.assertEqual(len(a['tracks']), 7)

    def test_match_album_tolerates_small_errors(self):
        a = mb.match_album('mia', 'kala ')
        self.assertEqual(a['artist'], 'M.I.A.')
        self.assertEqual(a['album'], 'Kala')

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

