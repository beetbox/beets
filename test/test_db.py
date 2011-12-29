# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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
import unittest
import os
import sqlite3
import ntpath
import posixpath
import shutil
import re

import _common
from _common import item
import beets.library
from beets import util

def lib():
    return beets.library.Library(os.path.join(_common.RSRC, 'test.blb'))
def boracay(l): return beets.library.Item(l.conn.execute('select * from items '
    'where id=3').fetchone())
np = util.normpath

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
        i = beets.library.Item.from_path(os.path.join(_common.RSRC, 'full.mp3'))
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
        self.lib.path_formats = [('default', 'two')]
        self.assertEqual(self.lib.destination(self.i), np('one/two'))
    
    def test_directory_works_without_trailing_slash(self):
        self.lib.directory = 'one'
        self.lib.path_formats = [('default', 'two')]
        self.assertEqual(self.lib.destination(self.i), np('one/two'))
    
    def test_destination_substitues_metadata_values(self):
        self.lib.directory = 'base'
        self.lib.path_formats = [('default', '$album/$artist $title')]
        self.i.title = 'three'
        self.i.artist = 'two'
        self.i.album = 'one'
        self.assertEqual(self.lib.destination(self.i),
                         np('base/one/two three'))
    
    def test_destination_preserves_extension(self):
        self.lib.directory = 'base'
        self.lib.path_formats = [('default', '$title')]
        self.i.path = 'hey.audioFormat'
        self.assertEqual(self.lib.destination(self.i),
                         np('base/the title.audioFormat'))
    
    def test_destination_pads_some_indices(self):
        self.lib.directory = 'base'
        self.lib.path_formats = [('default', '$track $tracktotal ' \
            '$disc $disctotal $bpm')]
        self.i.track = 1
        self.i.tracktotal = 2
        self.i.disc = 3
        self.i.disctotal = 4
        self.i.bpm = 5
        self.assertEqual(self.lib.destination(self.i),
                         np('base/01 02 03 04 5'))

    def test_destination_pads_date_values(self):
        self.lib.directory = 'base'
        self.lib.path_formats = [('default', '$year-$month-$day')]
        self.i.year = 1
        self.i.month = 2
        self.i.day = 3
        self.assertEqual(self.lib.destination(self.i),
                         np('base/0001-02-03'))
    
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
    
    def test_distination_windows_removes_both_separators(self):
        self.i.title = 'one \\ two / three.mp3'
        p = self.lib.destination(self.i, ntpath)
        self.assertFalse('one \\ two' in p)
        self.assertFalse('one / two' in p)
        self.assertFalse('two \\ three' in p)
        self.assertFalse('two / three' in p)
    
    def test_sanitize_unix_replaces_leading_dot(self):
        p = util.sanitize_path('one/.two/three', posixpath)
        self.assertFalse('.' in p)
    
    def test_sanitize_windows_replaces_trailing_dot(self):
        p = util.sanitize_path('one/two./three', ntpath)
        self.assertFalse('.' in p)
    
    def test_sanitize_windows_replaces_illegal_chars(self):
        p = util.sanitize_path(':*?"<>|', ntpath)
        self.assertFalse(':' in p)
        self.assertFalse('*' in p)
        self.assertFalse('?' in p)
        self.assertFalse('"' in p)
        self.assertFalse('<' in p)
        self.assertFalse('>' in p)
        self.assertFalse('|' in p)

    def test_sanitize_replaces_colon_with_dash(self):
        p = util.sanitize_path(u':', posixpath)
        self.assertEqual(p, u'-')
    
    def test_path_with_format(self):
        self.lib.path_formats = [('default', '$artist/$album ($format)')]
        p = self.lib.destination(self.i)
        self.assert_('(FLAC)' in p)

    def test_heterogeneous_album_gets_single_directory(self):
        i1, i2 = item(), item()
        self.lib.add_album([i1, i2])
        i1.year, i2.year = 2009, 2010
        self.lib.path_formats = [('default', '$album ($year)/$track $title')]
        dest1, dest2 = self.lib.destination(i1), self.lib.destination(i2)
        self.assertEqual(os.path.dirname(dest1), os.path.dirname(dest2))
    
    def test_default_path_for_non_compilations(self):
        self.i.comp = False
        self.lib.add_album([self.i])
        self.lib.directory = 'one'
        self.lib.path_formats = [('default', 'two'),
                                 ('comp:true', 'three')]
        self.assertEqual(self.lib.destination(self.i), np('one/two'))

    def test_singleton_path(self):
        i = item()
        self.lib.directory = 'one'
        self.lib.path_formats = [
            ('default', 'two'),
            ('singleton:true', 'four'),
            ('comp:true', 'three'),
        ]
        self.assertEqual(self.lib.destination(i), np('one/four'))

    def test_comp_before_singleton_path(self):
        i = item()
        i.comp = True
        self.lib.directory = 'one'
        self.lib.path_formats = [
            ('default', 'two'),
            ('comp:true', 'three'),
            ('singleton:true', 'four'),
        ]
        self.assertEqual(self.lib.destination(i), np('one/three'))

    def test_comp_path(self):
        self.i.comp = True
        self.lib.add_album([self.i])
        self.lib.directory = 'one'
        self.lib.path_formats = [
            ('default', 'two'),
            ('comp:true', 'three'),
        ]
        self.assertEqual(self.lib.destination(self.i), np('one/three'))

    def test_albumtype_query_path(self):
        self.i.comp = True
        self.lib.add_album([self.i])
        self.i.albumtype = 'sometype'
        self.lib.directory = 'one'
        self.lib.path_formats = [
            ('default', 'two'),
            ('albumtype:sometype', 'four'),
            ('comp:true', 'three'),
        ]
        self.assertEqual(self.lib.destination(self.i), np('one/four'))

    def test_albumtype_path_fallback_to_comp(self):
        self.i.comp = True
        self.lib.add_album([self.i])
        self.i.albumtype = 'sometype'
        self.lib.directory = 'one'
        self.lib.path_formats = [
            ('default', 'two'),
            ('albumtype:anothertype', 'four'),
            ('comp:true', 'three'),
        ]
        self.assertEqual(self.lib.destination(self.i), np('one/three'))

    def test_syspath_windows_format(self):
        path = ntpath.join('a', 'b', 'c')
        outpath = util.syspath(path, ntpath)
        self.assertTrue(isinstance(outpath, unicode))
        self.assertTrue(outpath.startswith(u'\\\\?\\'))

    def test_syspath_posix_unchanged(self):
        path = posixpath.join('a', 'b', 'c')
        outpath = util.syspath(path, posixpath)
        self.assertEqual(path, outpath)

    def test_sanitize_windows_replaces_trailing_space(self):
        p = util.sanitize_path('one/two /three', ntpath)
        self.assertFalse(' ' in p)

    def test_component_sanitize_replaces_separators(self):
        name = posixpath.join('a', 'b')
        newname = util.sanitize_for_path(name, posixpath)
        self.assertNotEqual(name, newname)

    def test_component_sanitize_pads_with_zero(self):
        name = util.sanitize_for_path(1, posixpath, 'track')
        self.assertTrue(name.startswith('0'))

    def test_component_sanitize_uses_kbps_bitrate(self):
        val = util.sanitize_for_path(12345, posixpath, 'bitrate')
        self.assertEqual(val, u'12kbps')

    def test_artist_falls_back_to_albumartist(self):
        self.i.artist = ''
        self.i.albumartist = 'something'
        self.lib.path_formats = [('default', '$artist')]
        p = self.lib.destination(self.i)
        self.assertEqual(p.rsplit(os.path.sep, 1)[1], 'something')

    def test_albumartist_falls_back_to_artist(self):
        self.i.artist = 'trackartist'
        self.i.albumartist = ''
        self.lib.path_formats = [('default', '$albumartist')]
        p = self.lib.destination(self.i)
        self.assertEqual(p.rsplit(os.path.sep, 1)[1], 'trackartist')

    def test_artist_overrides_albumartist(self):
        self.i.artist = 'theartist'
        self.i.albumartist = 'something'
        self.lib.path_formats = [('default', '$artist')]
        p = self.lib.destination(self.i)
        self.assertEqual(p.rsplit(os.path.sep, 1)[1], 'theartist')

    def test_albumartist_overrides_artist(self):
        self.i.artist = 'theartist'
        self.i.albumartist = 'something'
        self.lib.path_formats = [('default', '$albumartist')]
        p = self.lib.destination(self.i)
        self.assertEqual(p.rsplit(os.path.sep, 1)[1], 'something')

    def test_sanitize_path_works_on_empty_string(self):
        p = util.sanitize_path('', posixpath)
        self.assertEqual(p, '')

    def test_sanitize_with_custom_replace_overrides_built_in_sub(self):
        p = util.sanitize_path('a/.?/b', posixpath, [
            (re.compile(r'foo'), 'bar'),
        ])
        self.assertEqual(p, 'a/.?/b')

    def test_sanitize_with_custom_replace_adds_replacements(self):
        p = util.sanitize_path('foo/bar', posixpath, [
            (re.compile(r'foo'), 'bar'),
        ])
        self.assertEqual(p, 'bar/bar')

class DestinationFunctionTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.lib.directory = '/base'
        self.lib.path_formats = [('default', u'path')]
        self.i = item()
    def tearDown(self):
        self.lib.conn.close()

    def _setf(self, fmt):
        self.lib.path_formats.insert(0, ('default', fmt))
    def _assert_dest(self, dest):
        self.assertEqual(self.lib.destination(self.i), dest)

    def test_upper_case_literal(self):
        self._setf(u'%upper{foo}')
        self._assert_dest('/base/FOO')
    
    def test_upper_case_variable(self):
        self._setf(u'%upper{$title}')
        self._assert_dest('/base/THE TITLE')

    def test_title_case_variable(self):
        self._setf(u'%title{$title}')
        self._assert_dest('/base/The Title')

    def test_left_variable(self):
        self._setf(u'%left{$title, 3}')
        self._assert_dest('/base/the')
    
    def test_right_variable(self):
        self._setf(u'%right{$title,3}')
        self._assert_dest('/base/tle')

    def test_if_false(self):
        self._setf(u'x%if{,foo}')
        self._assert_dest('/base/x')
    
    def test_if_true(self):
        self._setf(u'%if{bar,foo}')
        self._assert_dest('/base/foo')
    
    def test_if_else_false(self):
        self._setf(u'%if{,foo,baz}')
        self._assert_dest('/base/baz')

    def test_if_int_value(self):
        self._setf(u'%if{0,foo,baz}')
        self._assert_dest('/base/baz')

    def test_nonexistent_function(self):
        self._setf(u'%foo{bar}')
        self._assert_dest('/base/%foo{bar}')
    
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
        self.libfile = os.path.join(_common.RSRC, 'templib.blb')
        old_lib = beets.library.Library(self.libfile,
                                        item_fields=self.old_fields)
        # Add an item to the old library.
        old_lib.conn.execute(
            'insert into items (field_one, field_two) values (4, 2)'
        )
        old_lib.save()
        del old_lib
        
    def tearDown(self):
        os.unlink(self.libfile)
    
    def test_open_with_same_fields_leaves_untouched(self):
        new_lib = beets.library.Library(self.libfile,
                                        item_fields=self.old_fields)
        c = new_lib.conn.cursor()
        c.execute("select * from items")
        row = c.fetchone()
        self.assertEqual(len(row), len(self.old_fields))
    
    def test_open_with_new_field_adds_column(self):
        new_lib = beets.library.Library(self.libfile,
                                        item_fields=self.new_fields)
        c = new_lib.conn.cursor()
        c.execute("select * from items")
        row = c.fetchone()
        self.assertEqual(len(row), len(self.new_fields))
    
    def test_open_with_fewer_fields_leaves_untouched(self):
        new_lib = beets.library.Library(self.libfile,
                                        item_fields=self.older_fields)
        c = new_lib.conn.cursor()
        c.execute("select * from items")
        row = c.fetchone()
        self.assertEqual(len(row), len(self.old_fields))
    
    def test_open_with_multiple_new_fields(self):
        new_lib = beets.library.Library(self.libfile,
                                        item_fields=self.newer_fields)
        c = new_lib.conn.cursor()
        c.execute("select * from items")
        row = c.fetchone()
        self.assertEqual(len(row), len(self.newer_fields))

    def test_open_old_db_adds_album_table(self):
        conn = sqlite3.connect(self.libfile)
        conn.execute('drop table albums')
        conn.close()

        conn = sqlite3.connect(self.libfile)
        self.assertRaises(sqlite3.OperationalError, conn.execute,
                         'select * from albums')
        conn.close()

        new_lib = beets.library.Library(self.libfile,
                                        item_fields=self.newer_fields)
        try:
            new_lib.conn.execute("select * from albums")
        except sqlite3.OperationalError:
            self.fail("select failed")

    def test_album_data_preserved(self):
        conn = sqlite3.connect(self.libfile)
        conn.execute('drop table albums')
        conn.execute('create table albums (id primary key, album)')
        conn.execute("insert into albums values (1, 'blah')")
        conn.commit()
        conn.close()

        new_lib = beets.library.Library(self.libfile,
                                        item_fields=self.newer_fields)
        albums = new_lib.conn.execute('select * from albums').fetchall()
        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0][1], 'blah')

    def test_move_artist_to_albumartist(self):
        conn = sqlite3.connect(self.libfile)
        conn.execute('drop table albums')
        conn.execute('create table albums (id primary key, artist)')
        conn.execute("insert into albums values (1, 'theartist')")
        conn.commit()
        conn.close()

        new_lib = beets.library.Library(self.libfile,
                                        item_fields=self.newer_fields)
        c = new_lib.conn.execute("select * from albums")
        album = c.fetchone()
        self.assertEqual(album['albumartist'], 'theartist')

class AlbumInfoTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.i = item()
        self.lib.add_album((self.i,))

    def test_albuminfo_reflects_metadata(self):
        ai = self.lib.get_album(self.i)
        self.assertEqual(ai.mb_albumartistid, self.i.mb_albumartistid)
        self.assertEqual(ai.albumartist, self.i.albumartist)
        self.assertEqual(ai.album, self.i.album)
        self.assertEqual(ai.year, self.i.year)

    def test_albuminfo_stores_art(self):
        ai = self.lib.get_album(self.i)
        ai.artpath = '/my/great/art'
        new_ai = self.lib.get_album(self.i)
        self.assertEqual(new_ai.artpath, '/my/great/art')
    
    def test_albuminfo_for_two_items_doesnt_duplicate_row(self):
        i2 = item()
        self.lib.add(i2)
        self.lib.get_album(self.i)
        self.lib.get_album(i2)
        
        c = self.lib.conn.cursor()
        c.execute('select * from albums where album=?', (self.i.album,))
        # Cursor should only return one row.
        self.assertNotEqual(c.fetchone(), None)
        self.assertEqual(c.fetchone(), None)

    def test_individual_tracks_have_no_albuminfo(self):
        i2 = item()
        i2.album = 'aTotallyDifferentAlbum'
        self.lib.add(i2)
        ai = self.lib.get_album(i2)
        self.assertEqual(ai, None)

    def test_get_album_by_id(self):
        ai = self.lib.get_album(self.i)
        ai = self.lib.get_album(self.i.id)
        self.assertNotEqual(ai, None)

    def test_album_items_consistent(self):
        ai = self.lib.get_album(self.i)
        for item in ai.items():
            if item.id == self.i.id:
                break
        else:
            self.fail("item not found")

    def test_albuminfo_changes_affect_items(self):
        ai = self.lib.get_album(self.i)
        ai.album = 'myNewAlbum'
        i = self.lib.items().next()
        self.assertEqual(i.album, 'myNewAlbum')

    def test_albuminfo_change_albumartist_changes_items(self):
        ai = self.lib.get_album(self.i)
        ai.albumartist = 'myNewArtist'
        i = self.lib.items().next()
        self.assertEqual(i.albumartist, 'myNewArtist')
        self.assertNotEqual(i.artist, 'myNewArtist')

    def test_albuminfo_change_artist_does_not_change_items(self):
        ai = self.lib.get_album(self.i)
        ai.artist = 'myNewArtist'
        i = self.lib.items().next()
        self.assertNotEqual(i.artist, 'myNewArtist')

    def test_albuminfo_remove_removes_items(self):
        item_id = self.i.id
        self.lib.get_album(self.i).remove()
        c = self.lib.conn.execute('SELECT id FROM items WHERE id=?', (item_id,))
        self.assertEqual(c.fetchone(), None)

    def test_removing_last_item_removes_album(self):
        self.assertEqual(len(self.lib.albums()), 1)
        self.lib.remove(self.i)
        self.assertEqual(len(self.lib.albums()), 0)

class BaseAlbumTest(unittest.TestCase):
    def test_field_access(self):
        album = beets.library.BaseAlbum(None, {'fld1':'foo'})
        self.assertEqual(album.fld1, 'foo')

    def test_field_access_unset_values(self):
        album = beets.library.BaseAlbum(None, {})
        self.assertRaises(AttributeError, getattr, album, 'field')

class ArtDestinationTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.i = item()
        self.i.path = self.lib.destination(self.i)
        self.lib.art_filename = 'artimage'
        self.ai = self.lib.add_album((self.i,))
        
    def test_art_filename_respects_setting(self):
        art = self.ai.art_destination('something.jpg')
        self.assert_('%sartimage.jpg' % os.path.sep in art)
        
    def test_art_path_in_item_dir(self):
        art = self.ai.art_destination('something.jpg')
        track = self.lib.destination(self.i)
        self.assertEqual(os.path.dirname(art), os.path.dirname(track))

class PathStringTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.i = item()
        self.lib.add(self.i)

    def test_item_path_is_bytestring(self):
        self.assert_(isinstance(self.i.path, str))

    def test_fetched_item_path_is_bytestring(self):
        i = list(self.lib.items())[0]
        self.assert_(isinstance(i.path, str))

    def test_unicode_path_becomes_bytestring(self):
        self.i.path = u'unicodepath'
        self.assert_(isinstance(self.i.path, str))

    def test_unicode_in_database_becomes_bytestring(self):
        self.lib.conn.execute("""
        update items set path=? where id=?
        """, (self.i.id, u'somepath'))
        i = list(self.lib.items())[0]
        self.assert_(isinstance(i.path, str))

    def test_special_chars_preserved_in_database(self):
        path = 'b\xe1r'
        self.i.path = path
        self.lib.store(self.i)
        i = list(self.lib.items())[0]
        self.assertEqual(i.path, path)

    def test_special_char_path_added_to_database(self):
        self.lib.remove(self.i)
        path = 'b\xe1r'
        i = item()
        i.path = path
        self.lib.add(i)
        i = list(self.lib.items())[0]
        self.assertEqual(i.path, path)

    def test_destination_returns_bytestring(self):
        self.i.artist = u'b\xe1r'
        dest = self.lib.destination(self.i)
        self.assert_(isinstance(dest, str))

    def test_art_destination_returns_bytestring(self):
        self.i.artist = u'b\xe1r'
        alb = self.lib.add_album([self.i])
        dest = alb.art_destination(u'image.jpg')
        self.assert_(isinstance(dest, str))

    def test_artpath_stores_special_chars(self):
        path = 'b\xe1r'
        alb = self.lib.add_album([self.i])
        alb.artpath = path
        alb = self.lib.get_album(self.i)
        self.assertEqual(path, alb.artpath)

    def test_sanitize_path_with_special_chars(self):
        path = 'b\xe1r?'
        new_path = util.sanitize_path(path)
        self.assert_(new_path.startswith('b\xe1r'))

    def test_sanitize_path_returns_bytestring(self):
        path = 'b\xe1r?'
        new_path = util.sanitize_path(path)
        self.assert_(isinstance(new_path, str))

    def test_unicode_artpath_becomes_bytestring(self):
        alb = self.lib.add_album([self.i])
        alb.artpath = u'somep\xe1th'
        self.assert_(isinstance(alb.artpath, str))

    def test_unicode_artpath_in_database_decoded(self):
        alb = self.lib.add_album([self.i])
        self.lib.conn.execute(
            "update albums set artpath=? where id=?",
            (u'somep\xe1th', alb.id)
        )
        alb = self.lib.get_album(alb.id)
        self.assert_(isinstance(alb.artpath, str))

class MtimeTest(unittest.TestCase):
    def setUp(self):
        self.ipath = os.path.join(_common.RSRC, 'testfile.mp3')
        shutil.copy(os.path.join(_common.RSRC, 'full.mp3'), self.ipath)
        self.i = beets.library.Item.from_path(self.ipath)
        self.lib = beets.library.Library(':memory:')
        self.lib.add(self.i)

    def tearDown(self):
        if os.path.exists(self.ipath):
            os.remove(self.ipath)

    def _mtime(self):
        return os.path.getmtime(self.ipath)

    def test_mtime_initially_up_to_date(self):
        self.assertGreaterEqual(self.i.mtime, self._mtime())

    def test_mtime_reset_on_db_modify(self):
        self.i.title = 'something else'
        self.assertLess(self.i.mtime, self._mtime())

    def test_mtime_up_to_date_after_write(self):
        self.i.title = 'something else'
        self.i.write()
        self.assertGreaterEqual(self.i.mtime, self._mtime())

    def test_mtime_up_to_date_after_read(self):
        self.i.title = 'something else'
        self.i.read()
        self.assertGreaterEqual(self.i.mtime, self._mtime())

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
