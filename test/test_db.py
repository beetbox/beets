#!/usr/bin/env python

"""
Tests for non-query database functions of Item.
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
    'track':      2,
    'tracktotal': 3,
    'disc':       4,
    'disctotal':  5,
    'lyrics':     u'the lyrics',
    'comments':   u'the comments',
    'bpm':        6,
    'comp':       True,
    'path':       'somepath',
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

class DestinationTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.i = item(self.lib)
    def tearDown(self):
        self.lib.conn.close()
    
    def test_directory_works_with_trailing_slash(self):
        self.lib.options['directory'] = 'one/'
        self.lib.options['path_format'] = 'two'
        self.assertEqual(self.i.destination(), np('one/two'))
    
    def test_directory_works_without_trailing_slash(self):
        self.lib.options['directory'] = 'one'
        self.lib.options['path_format'] = 'two'
        self.assertEqual(self.i.destination(), np('one/two'))
    
    def test_destination_substitues_metadata_values(self):
        self.lib.options['directory'] = 'base'
        self.lib.options['path_format'] = '$album/$artist $title'
        self.i.title = 'three'
        self.i.artist = 'two'
        self.i.album = 'one'
        self.assertEqual(self.i.destination(), np('base/one/two three'))
    
    def test_destination_substitutes_extension(self):
        self.lib.options['directory'] = 'base'
        self.lib.options['path_format'] = '$extension'
        self.i.path = 'hey.audioFormat'
        self.assertEqual(self.i.destination(), np('base/audioFormat'))
    
    def test_destination_pads_some_indices(self):
        self.lib.options['directory'] = 'base'
        self.lib.options['path_format'] = '$track $tracktotal ' \
            '$disc $disctotal $bpm $year'
        self.i.track = 1
        self.i.tracktotal = 2
        self.i.disc = 3
        self.i.disctotal = 4
        self.i.bpm = 5
        self.i.year = 6
        self.assertEqual(self.i.destination(), np('base/01 02 03 04 5 6'))
        
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')