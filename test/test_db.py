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

"""Tests for non-query database functions of Item.
"""

import unittest, sys, os
sys.path.append('..')
import beets.library

def lib(): return beets.library.Library('rsrc' + os.sep + 'test.blb')
def boracay(l): return beets.library.Item(l.conn.execute('select * from items '
    'where id=3').fetchone(), l)
def item(lib=None): return beets.library.Item({
    'title':      u'the title',
    'artist':     u'the artist',
    'album':      u'the album',
    'genre':      u'the genre',
    'composer':   u'the composer',
    'grouping':   u'the grouping',
    'year':       1,
    'month':      2,
    'day':        3,
    'track':      4,
    'tracktotal': 5,
    'disc':       6,
    'disctotal':  7,
    'lyrics':     u'the lyrics',
    'comments':   u'the comments',
    'bpm':        8,
    'comp':       True,
    'path':       'somepath',
    'length':     60.0,
    'bitrate':    128000,
}, lib)
np = beets.library._normpath

class LoadTest(unittest.TestCase):
    def setUp(self):
        self.lib = lib()
        self.i = boracay(self.lib)
    def tearDown(self):
        self.lib.conn.close()
    
    def test_load_restores_data_from_db(self):
        original_title = self.i.title
        self.i.title = 'something'
        self.i.load()
        self.assertEqual(original_title, self.i.title)
    
    def test_load_clears_dirty_flags(self):
        self.i.artist = 'something'
        self.i.load()
        self.assertTrue(not self.i.dirty['artist'])

class StoreTest(unittest.TestCase):
    def setUp(self):
        self.lib = lib()
        self.i = boracay(self.lib)
    def tearDown(self):
        self.lib.conn.close()
    
    def test_store_changes_database_value(self):
        self.i.year = 1987
        self.i.store()
        new_year = self.lib.conn.execute('select year from items where '
            'title="Boracay"').fetchone()['year']
        self.assertEqual(new_year, 1987)
    
    def test_store_only_writes_dirty_fields(self):
        original_genre = self.i.genre
        self.i.record['genre'] = 'beatboxing' # change value w/o dirtying
        self.i.store()
        new_genre = self.lib.conn.execute('select genre from items where '
            'title="Boracay"').fetchone()['genre']
        self.assertEqual(new_genre, original_genre)
    
    def test_store_clears_dirty_flags(self):
        self.i.composer = 'tvp'
        self.i.store()
        self.assertTrue(not self.i.dirty['composer'])

class AddTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.i = item(self.lib)
    def tearDown(self):
        self.lib.conn.close()
    
    def test_item_add_inserts_row(self):
        self.i.add()
        new_grouping = self.lib.conn.execute('select grouping from items '
            'where composer="the composer"').fetchone()['grouping']
        self.assertEqual(new_grouping, self.i.grouping)
    
    def test_library_add_inserts_row(self):
        self.lib.add(os.path.join('rsrc', 'full.mp3'))
        new_grouping = self.lib.conn.execute('select grouping from items '
            'where composer="the composer"').fetchone()['grouping']
        self.assertEqual(new_grouping, self.i.grouping)
        

class RemoveTest(unittest.TestCase):
    def setUp(self):
        self.lib = lib()
        self.i = boracay(self.lib)
    def tearDown(self):
        self.lib.conn.close()
    
    def test_remove_deletes_from_db(self):
        self.i.remove()
        c = self.lib.conn.execute('select * from items where id=3')
        self.assertEqual(c.fetchone(), None)

class GetSetTest(unittest.TestCase):
    def setUp(self):
        self.i = item()
    
    def test_set_changes_value(self):
        self.i.bpm = 4915
        self.assertEqual(self.i.bpm, 4915)
    
    def test_set_sets_dirty_flag(self):
        self.i.comp = not self.i.comp
        self.assertTrue(self.i.dirty['comp'])
    
    def test_set_does_not_dirty_if_value_unchanged(self):
        self.i.title = self.i.title
        self.assertTrue(not self.i.dirty['title'])
    
    def test_invalid_field_raises_attributeerror(self):
        self.assertRaises(AttributeError, getattr, self.i, 'xyzzy')

class DestinationTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.i = item(self.lib)
    def tearDown(self):
        self.lib.conn.close()
    
    def test_directory_works_with_trailing_slash(self):
        self.lib.directory = 'one/'
        self.lib.path_format = 'two'
        self.assertEqual(self.lib.destination(self.i), np('one/two'))
    
    def test_directory_works_without_trailing_slash(self):
        self.lib.directory = 'one'
        self.lib.path_format = 'two'
        self.assertEqual(self.lib.destination(self.i), np('one/two'))
    
    def test_destination_substitues_metadata_values(self):
        self.lib.directory = 'base'
        self.lib.path_format = '$album/$artist $title'
        self.i.title = 'three'
        self.i.artist = 'two'
        self.i.album = 'one'
        self.assertEqual(self.lib.destination(self.i),
                         np('base/one/two three'))
    
    def test_destination_preserves_extension(self):
        self.lib.directory = 'base'
        self.lib.path_format = '$title'
        self.i.path = 'hey.audioFormat'
        self.assertEqual(self.lib.destination(self.i),
                         np('base/the title.audioFormat'))
    
    def test_destination_pads_some_indices(self):
        self.lib.directory = 'base'
        self.lib.path_format = '$track $tracktotal ' \
            '$disc $disctotal $bpm $year'
        self.i.track = 1
        self.i.tracktotal = 2
        self.i.disc = 3
        self.i.disctotal = 4
        self.i.bpm = 5
        self.i.year = 6
        self.assertEqual(self.lib.destination(self.i),
                         np('base/01 02 03 04 5 6'))
    
    def test_destination_escapes_slashes(self):
        self.i.album = 'one/two'
        dest = self.lib.destination(self.i)
        self.assertTrue('one' in dest)
        self.assertTrue('two' in dest)
        self.assertFalse('one/two' in dest)
    
    def test_destination_long_names_truncated(self):
        self.i.title = 'X'*300
        self.i.artist = 'Y'*300
        for c in self.lib.destination(self.i).split(os.path.sep):
            self.assertTrue(len(c) <= 255)
    
    def test_destination_long_names_keep_extension(self):
        self.i.title = 'X'*300
        self.i.path = 'something.extn'
        dest = self.lib.destination(self.i)
        self.assertEqual(dest[-5:], '.extn')
        
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
