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

"""Tests for non-query database functions of Item.
"""

import unittest, sys, os
sys.path.append('..')
import beets.library

def lib(): return beets.library.Library('rsrc' + os.sep + 'test.blb')
def boracay(l): return beets.library.Item(l.conn.execute('select * from items '
    'where id=3').fetchone())
def item(): return beets.library.Item({
    'title':       u'the title',
    'artist':      u'the artist',
    'album':       u'the album',
    'genre':       u'the genre',
    'composer':    u'the composer',
    'grouping':    u'the grouping',
    'year':        1,
    'month':       2,
    'day':         3,
    'track':       4,
    'tracktotal':  5,
    'disc':        6,
    'disctotal':   7,
    'lyrics':      u'the lyrics',
    'comments':    u'the comments',
    'bpm':         8,
    'comp':        True,
    'path':        'somepath',
    'length':      60.0,
    'bitrate':     128000,
    'mb_trackid':  'someID-1',
    'mb_albumid':  'someID-2',
    'mb_artistid': 'someID-3',
})
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
        self.lib.load(self.i)
        self.assertEqual(original_title, self.i.title)
    
    def test_load_clears_dirty_flags(self):
        self.i.artist = 'something'
        self.lib.load(self.i)
        self.assertTrue(not self.i.dirty['artist'])

class StoreTest(unittest.TestCase):
    def setUp(self):
        self.lib = lib()
        self.i = boracay(self.lib)
    def tearDown(self):
        self.lib.conn.close()
    
    def test_store_changes_database_value(self):
        self.i.year = 1987
        self.lib.store(self.i)
        new_year = self.lib.conn.execute('select year from items where '
            'title="Boracay"').fetchone()['year']
        self.assertEqual(new_year, 1987)
    
    def test_store_only_writes_dirty_fields(self):
        original_genre = self.i.genre
        self.i.record['genre'] = 'beatboxing' # change value w/o dirtying
        self.lib.store(self.i)
        new_genre = self.lib.conn.execute('select genre from items where '
            'title="Boracay"').fetchone()['genre']
        self.assertEqual(new_genre, original_genre)
    
    def test_store_clears_dirty_flags(self):
        self.i.composer = 'tvp'
        self.lib.store(self.i)
        self.assertTrue(not self.i.dirty['composer'])

class AddTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.i = item()
    def tearDown(self):
        self.lib.conn.close()
    
    def test_item_add_inserts_row(self):
        self.lib.add(self.i)
        new_grouping = self.lib.conn.execute('select grouping from items '
            'where composer="the composer"').fetchone()['grouping']
        self.assertEqual(new_grouping, self.i.grouping)
    
    def test_library_add_path_inserts_row(self):
        i = beets.library.Item.from_path(os.path.join('rsrc', 'full.mp3'))
        self.lib.add(i)
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
        self.lib.remove(self.i)
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
        self.i = item()
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
    
    def test_destination_escapes_leading_dot(self):
        self.i.album = '.something'
        dest = self.lib.destination(self.i)
        self.assertTrue('something' in dest)
        self.assertFalse('/.' in dest)
    
    def test_destination_preserves_legitimate_slashes(self):
        self.i.artist = 'one'
        self.i.album = 'two'
        dest = self.lib.destination(self.i)
        self.assertTrue(os.path.join('one', 'two') in dest)
    
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
    
    def test_sanitize_unix_replaces_leading_dot(self):
        p = beets.library._sanitize_path('one/.two/three', 'Darwin')
        self.assertFalse('.' in p)
    
    def test_sanitize_windows_replaces_trailing_dot(self):
        p = beets.library._sanitize_path('one/two./three', 'Windows')
        self.assertFalse('.' in p)
    
    def test_sanitize_windows_replaces_illegal_chars(self):
        p = beets.library._sanitize_path(':*?"<>|', 'Windows')
        self.assertFalse(':' in p)
        self.assertFalse('*' in p)
        self.assertFalse('?' in p)
        self.assertFalse('"' in p)
        self.assertFalse('<' in p)
        self.assertFalse('>' in p)
        self.assertFalse('|' in p)
    
    def test_sanitize_replaces_colon_with_dash(self):
        p = beets.library._sanitize_path(u':', 'Darwin')
        self.assertEqual(p, u'-')

class MigrationTest(unittest.TestCase):
    """Tests the ability to change the database schema between
    versions.
    """
    def setUp(self):
        # Three different "schema versions".
        self.older_fields = [('field_one', 'int')]
        self.old_fields = self.older_fields + [('field_two', 'int')]
        self.new_fields = self.old_fields + [('field_three', 'int')]
        self.newer_fields = self.new_fields + [('field_four', 'int')]
        
        # Set up a library with old_fields.
        self.libfile = os.path.join('rsrc', 'templib.blb')
        old_lib = beets.library.Library(self.libfile, fields=self.old_fields)
        # Add an item to the old library.
        old_lib.conn.execute(
            'insert into items (field_one, field_two) values (4, 2)'
        )
        old_lib.save()
        del old_lib
        
    def tearDown(self):
        os.unlink(self.libfile)
    
    def test_open_with_same_fields_leaves_untouched(self):
        new_lib = beets.library.Library(self.libfile, fields=self.old_fields)
        c = new_lib.conn.cursor()
        c.execute("select * from items")
        row = c.fetchone()
        self.assertEqual(len(row), len(self.old_fields))
    
    def test_open_with_new_field_adds_column(self):
        new_lib = beets.library.Library(self.libfile, fields=self.new_fields)
        c = new_lib.conn.cursor()
        c.execute("select * from items")
        row = c.fetchone()
        self.assertEqual(len(row), len(self.new_fields))
    
    def test_open_with_fewer_fields_leaves_untouched(self):
        new_lib = beets.library.Library(self.libfile, fields=self.older_fields)
        c = new_lib.conn.cursor()
        c.execute("select * from items")
        row = c.fetchone()
        self.assertEqual(len(row), len(self.old_fields))
    
    def test_open_with_multiple_new_fields(self):
        new_lib = beets.library.Library(self.libfile, fields=self.newer_fields)
        c = new_lib.conn.cursor()
        c.execute("select * from items")
        row = c.fetchone()
        self.assertEqual(len(row), len(self.newer_fields))
        

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
