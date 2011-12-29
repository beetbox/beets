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

"""Test file manipulation functionality of Item.
"""

import unittest
import shutil
import os
import stat
from os.path import join

import _common
from _common import item, touch
import beets.library
from beets import util

class MoveTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        # make a temporary file
        self.path = join(_common.RSRC, 'temp.mp3')
        shutil.copy(join(_common.RSRC, 'full.mp3'), self.path)
        
        # add it to a temporary library
        self.lib = beets.library.Library(':memory:')
        self.i = beets.library.Item.from_path(self.path)
        self.lib.add(self.i)
        
        # set up the destination
        self.libdir = join(_common.RSRC, 'testlibdir')
        self.lib.directory = self.libdir
        self.lib.path_formats = [('default',
                                  join('$artist', '$album', '$title'))]
        self.i.artist = 'one'
        self.i.album = 'two'
        self.i.title = 'three'
        self.dest = join(self.libdir, 'one', 'two', 'three.mp3')

        self.otherdir = join(_common.RSRC, 'testotherdir')
        
    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        if os.path.exists(self.libdir):
            shutil.rmtree(self.libdir)
        if os.path.exists(self.otherdir):
            shutil.rmtree(self.otherdir)
    
    def test_move_arrives(self):
        self.lib.move(self.i)
        self.assertExists(self.dest)
    
    def test_move_to_custom_dir(self):
        self.lib.move(self.i, basedir=self.otherdir)
        self.assertExists(join(self.otherdir, 'one', 'two', 'three.mp3'))
    
    def test_move_departs(self):
        self.lib.move(self.i)
        self.assertNotExists(self.path)

    def test_move_in_lib_prunes_empty_dir(self):
        self.lib.move(self.i)
        old_path = self.i.path
        self.assertExists(old_path)

        self.i.artist = 'newArtist'
        self.lib.move(self.i)
        self.assertNotExists(old_path)
        self.assertNotExists(os.path.dirname(old_path))
    
    def test_copy_arrives(self):
        self.lib.move(self.i, copy=True)
        self.assertExists(self.dest)
    
    def test_copy_does_not_depart(self):
        self.lib.move(self.i, copy=True)
        self.assertExists(self.path)
    
    def test_move_changes_path(self):
        self.lib.move(self.i)
        self.assertEqual(self.i.path, util.normpath(self.dest))

    def test_copy_already_at_destination(self):
        self.lib.move(self.i)
        old_path = self.i.path
        self.lib.move(self.i, copy=True)
        self.assertEqual(self.i.path, old_path)

    def test_move_already_at_destination(self):
        self.lib.move(self.i)
        old_path = self.i.path
        self.lib.move(self.i, copy=False)
        self.assertEqual(self.i.path, old_path)

    def test_read_only_file_copied_writable(self):
        # Make the source file read-only.
        os.chmod(self.path, 0444)

        try:
            self.lib.move(self.i, copy=True)
            self.assertTrue(os.access(self.i.path, os.W_OK))
        finally:
            # Make everything writable so it can be cleaned up.
            os.chmod(self.path, 0777)
            os.chmod(self.i.path, 0777)

    def test_move_avoids_collision_with_existing_file(self):
        # Make a conflicting file at the destination.
        dest = self.lib.destination(self.i)
        os.makedirs(os.path.dirname(dest))
        touch(dest)

        self.lib.move(self.i)
        self.assertNotEqual(self.i.path, dest)
        self.assertEqual(os.path.dirname(self.i.path),
                         os.path.dirname(dest))
    
class HelperTest(unittest.TestCase):
    def test_ancestry_works_on_file(self):
        p = '/a/b/c'
        a =  ['/','/a','/a/b']
        self.assertEqual(util.ancestry(p), a)
    def test_ancestry_works_on_dir(self):
        p = '/a/b/c/'
        a = ['/', '/a', '/a/b', '/a/b/c']
        self.assertEqual(util.ancestry(p), a)
    def test_ancestry_works_on_relative(self):
        p = 'a/b/c'
        a = ['a', 'a/b']
        self.assertEqual(util.ancestry(p), a)
    
    def test_components_works_on_file(self):
        p = '/a/b/c'
        a =  ['/', 'a', 'b', 'c']
        self.assertEqual(util.components(p), a)
    def test_components_works_on_dir(self):
        p = '/a/b/c/'
        a =  ['/', 'a', 'b', 'c']
        self.assertEqual(util.components(p), a)
    def test_components_works_on_relative(self):
        p = 'a/b/c'
        a =  ['a', 'b', 'c']
        self.assertEqual(util.components(p), a)

class AlbumFileTest(unittest.TestCase):
    def setUp(self):
        # Make library and item.
        self.lib = beets.library.Library(':memory:')
        self.lib.path_formats = \
            [('default', join('$albumartist', '$album', '$title'))]
        self.libdir = os.path.join(_common.RSRC, 'testlibdir')
        self.lib.directory = self.libdir
        self.i = item()
        # Make a file for the item.
        self.i.path = self.lib.destination(self.i)
        util.mkdirall(self.i.path)
        touch(self.i.path)
        # Make an album.
        self.ai = self.lib.add_album((self.i,))
        # Alternate destination dir.
        self.otherdir = os.path.join(_common.RSRC, 'testotherdir')
    def tearDown(self):
        if os.path.exists(self.libdir):
            shutil.rmtree(self.libdir)
        if os.path.exists(self.otherdir):
            shutil.rmtree(self.otherdir)

    def test_albuminfo_move_changes_paths(self):
        self.ai.album = 'newAlbumName'
        self.ai.move()
        self.lib.load(self.i)

        self.assert_('newAlbumName' in self.i.path)

    def test_albuminfo_move_moves_file(self):
        oldpath = self.i.path
        self.ai.album = 'newAlbumName'
        self.ai.move()
        self.lib.load(self.i)

        self.assertFalse(os.path.exists(oldpath))
        self.assertTrue(os.path.exists(self.i.path))

    def test_albuminfo_move_copies_file(self):
        oldpath = self.i.path
        self.ai.album = 'newAlbumName'
        self.ai.move(True)
        self.lib.load(self.i)

        self.assertTrue(os.path.exists(oldpath))
        self.assertTrue(os.path.exists(self.i.path))

    def test_albuminfo_move_to_custom_dir(self):
        self.ai.move(basedir=self.otherdir)
        self.lib.load(self.i)
        self.assertTrue('testotherdir' in self.i.path)

class ArtFileTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        # Make library and item.
        self.lib = beets.library.Library(':memory:')
        self.libdir = os.path.abspath(os.path.join(_common.RSRC, 'testlibdir'))
        self.lib.directory = self.libdir
        self.i = item()
        self.i.path = self.lib.destination(self.i)
        # Make a music file.
        util.mkdirall(self.i.path)
        touch(self.i.path)
        # Make an album.
        self.ai = self.lib.add_album((self.i,))
        # Make an art file too.
        self.art = self.lib.get_album(self.i).art_destination('something.jpg')
        touch(self.art)
        self.ai.artpath = self.art
        # Alternate destination dir.
        self.otherdir = os.path.join(_common.RSRC, 'testotherdir')
    def tearDown(self):
        if os.path.exists(self.libdir):
            shutil.rmtree(self.libdir)
        if os.path.exists(self.otherdir):
            shutil.rmtree(self.otherdir)

    def test_art_deleted_when_items_deleted(self):
        self.assertTrue(os.path.exists(self.art))
        self.ai.remove(True)
        self.assertFalse(os.path.exists(self.art))

    def test_art_moves_with_album(self):
        self.assertTrue(os.path.exists(self.art))
        oldpath = self.i.path
        self.ai.album = 'newAlbum'
        self.ai.move()
        self.lib.load(self.i)

        self.assertNotEqual(self.i.path, oldpath)
        self.assertFalse(os.path.exists(self.art))
        newart = self.lib.get_album(self.i).art_destination(self.art)
        self.assertTrue(os.path.exists(newart))

    def test_art_moves_with_album_to_custom_dir(self):
        # Move the album to another directory.
        self.ai.move(basedir=self.otherdir)
        self.lib.load(self.i)

        # Art should be in new directory.
        self.assertNotExists(self.art)
        newart = self.lib.get_album(self.i).artpath
        self.assertExists(newart)
        self.assertTrue('testotherdir' in newart)

    def test_setart_copies_image(self):
        os.remove(self.art)

        newart = os.path.join(self.libdir, 'newart.jpg')
        touch(newart)
        i2 = item()
        i2.path = self.i.path
        i2.artist = 'someArtist'
        ai = self.lib.add_album((i2,))
        self.lib.move(i2, True)
        
        self.assertEqual(ai.artpath, None)
        ai.set_art(newart)
        self.assertTrue(os.path.exists(ai.artpath))
    
    def test_setart_to_existing_art_works(self):
        os.remove(self.art)

        # Original art.
        newart = os.path.join(self.libdir, 'newart.jpg')
        touch(newart)
        i2 = item()
        i2.path = self.i.path
        i2.artist = 'someArtist'
        ai = self.lib.add_album((i2,))
        self.lib.move(i2, True)
        ai.set_art(newart)

        # Set the art again.
        ai.set_art(ai.artpath)
        self.assertTrue(os.path.exists(ai.artpath))

    def test_setart_to_existing_but_unset_art_works(self):
        newart = os.path.join(self.libdir, 'newart.jpg')
        touch(newart)
        i2 = item()
        i2.path = self.i.path
        i2.artist = 'someArtist'
        ai = self.lib.add_album((i2,))
        self.lib.move(i2, True)

        # Copy the art to the destination.
        artdest = ai.art_destination(newart)
        shutil.copy(newart, artdest)

        # Set the art again.
        ai.set_art(artdest)
        self.assertTrue(os.path.exists(ai.artpath))

    def test_setart_to_conflicting_file_gets_new_path(self):
        newart = os.path.join(self.libdir, 'newart.jpg')
        touch(newart)
        i2 = item()
        i2.path = self.i.path
        i2.artist = 'someArtist'
        ai = self.lib.add_album((i2,))
        self.lib.move(i2, True)

        # Make a file at the destination.
        artdest = ai.art_destination(newart)
        touch(artdest)

        # Set the art.
        ai.set_art(newart)
        self.assertNotEqual(artdest, ai.artpath)
        self.assertEqual(os.path.dirname(artdest),
                         os.path.dirname(ai.artpath))

    def test_setart_sets_permissions(self):
        os.remove(self.art)

        newart = os.path.join(self.libdir, 'newart.jpg')
        touch(newart)
        os.chmod(newart, 0400) # read-only
        
        try:
            i2 = item()
            i2.path = self.i.path
            i2.artist = 'someArtist'
            ai = self.lib.add_album((i2,))
            self.lib.move(i2, True)
            ai.set_art(newart)
            
            mode = stat.S_IMODE(os.stat(ai.artpath).st_mode)
            self.assertTrue(mode & stat.S_IRGRP)
            self.assertTrue(os.access(ai.artpath, os.W_OK))
            
        finally:
            # Make everything writable so it can be cleaned up.
            os.chmod(newart, 0777)
            os.chmod(ai.artpath, 0777)

    def test_move_last_file_moves_albumart(self):
        oldartpath = self.lib.albums()[0].artpath
        self.assertExists(oldartpath)

        self.ai.album = 'different_album'
        self.lib.move(self.i)

        artpath = self.lib.albums()[0].artpath
        self.assertTrue('different_album' in artpath)
        self.assertExists(artpath)
        self.assertNotExists(oldartpath)

    def test_move_not_last_file_does_not_move_albumart(self):
        i2 = item()
        i2.albumid = self.ai.id
        self.lib.add(i2)

        oldartpath = self.lib.albums()[0].artpath
        self.assertExists(oldartpath)

        self.i.album = 'different_album'
        self.i.album_id = None # detach from album
        self.lib.move(self.i)

        artpath = self.lib.albums()[0].artpath
        self.assertFalse('different_album' in artpath)
        self.assertEqual(artpath, oldartpath)
        self.assertExists(oldartpath)

class RemoveTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        # Make library and item.
        self.lib = beets.library.Library(':memory:')
        self.libdir = os.path.abspath(os.path.join(_common.RSRC, 'testlibdir'))
        self.lib.directory = self.libdir
        self.i = item()
        self.i.path = self.lib.destination(self.i)
        # Make a music file.
        util.mkdirall(self.i.path)
        touch(self.i.path)
        # Make an album with the item.
        self.ai = self.lib.add_album((self.i,))
    def tearDown(self):
        if os.path.exists(self.libdir):
            shutil.rmtree(self.libdir)

    def test_removing_last_item_prunes_empty_dir(self):
        parent = os.path.dirname(self.i.path)
        self.assertExists(parent)
        self.lib.remove(self.i, True)
        self.assertNotExists(parent)

    def test_removing_last_item_preserves_nonempty_dir(self):
        parent = os.path.dirname(self.i.path)
        touch(os.path.join(parent, 'dummy.txt'))
        self.lib.remove(self.i, True)
        self.assertExists(parent)

    def test_removing_last_item_prunes_dir_with_blacklisted_file(self):
        parent = os.path.dirname(self.i.path)
        touch(os.path.join(parent, '.DS_Store'))
        self.lib.remove(self.i, True)
        self.assertNotExists(parent)

    def test_removing_without_delete_leaves_file(self):
        path = self.i.path
        self.lib.remove(self.i)
        self.assertExists(path)

    def test_removing_last_item_preserves_library_dir(self):
        self.lib.remove(self.i, True)
        self.assertExists(self.libdir)

    def test_removing_item_outside_of_library_deletes_nothing(self):
        self.lib.directory = os.path.abspath(os.path.join(_common.RSRC, 'xxx'))
        parent = os.path.dirname(self.i.path)
        self.lib.remove(self.i, True)
        self.assertExists(parent)

    def test_removing_last_item_in_album_with_albumart_prunes_dir(self):
        artfile = os.path.join(_common.RSRC, 'testart.jpg')
        touch(artfile)
        self.ai.set_art(artfile)
        os.remove(artfile)

        parent = os.path.dirname(self.i.path)
        self.lib.remove(self.i, True)
        self.assertNotExists(parent)

# Tests that we can "delete" nonexistent files.
class SoftRemoveTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        self.path = os.path.join(_common.RSRC, 'testfile')
        touch(self.path)
    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_soft_remove_deletes_file(self):
        util.soft_remove(self.path)
        self.assertNotExists(self.path)

    def test_soft_remove_silent_on_no_file(self):
        try:
            util.soft_remove(self.path + 'XXX')
        except OSError:
            self.fail('OSError when removing path')

class SafeMoveCopyTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        self.path = os.path.join(_common.RSRC, 'testfile')
        touch(self.path)
        self.otherpath = os.path.join(_common.RSRC, 'testfile2')
        touch(self.otherpath)
        self.dest = self.path + '.dest'
    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        if os.path.exists(self.otherpath):
            os.remove(self.otherpath)
        if os.path.exists(self.dest):
            os.remove(self.dest)

    def test_existence_check(self):
        with self.assertRaises(OSError):
            util._assert_not_exists(self.path)

    def test_successful_move(self):
        util.move(self.path, self.dest)
        self.assertExists(self.dest)
        self.assertNotExists(self.path)

    def test_successful_copy(self):
        util.copy(self.path, self.dest)
        self.assertExists(self.dest)
        self.assertExists(self.path)

    def test_unsuccessful_move(self):
        with self.assertRaises(OSError):
            util.move(self.path, self.otherpath)

    def test_unsuccessful_copy(self):
        with self.assertRaises(OSError):
            util.copy(self.path, self.otherpath)

    def test_self_move(self):
        util.move(self.path, self.path)
        self.assertExists(self.path)

    def test_self_copy(self):
        util.copy(self.path, self.path)
        self.assertExists(self.path)

class PruneTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        self.base = os.path.join(_common.RSRC, 'testdir')
        os.mkdir(self.base)
        self.sub = os.path.join(self.base, 'subdir')
        os.mkdir(self.sub)
    def tearDown(self):
        if os.path.exists(self.base):
            shutil.rmtree(self.base)

    def test_prune_existent_directory(self):
        util.prune_dirs(self.sub, self.base)
        self.assertExists(self.base)
        self.assertNotExists(self.sub)

    def test_prune_nonexistent_directory(self):
        util.prune_dirs(os.path.join(self.sub, 'another'), self.base)
        self.assertExists(self.base)
        self.assertNotExists(self.sub)

class WalkTest(unittest.TestCase):
    def setUp(self):
        self.base = os.path.join(_common.RSRC, 'testdir')
        os.mkdir(self.base)
        touch(os.path.join(self.base, 'y'))
        touch(os.path.join(self.base, 'x'))
        os.mkdir(os.path.join(self.base, 'd'))
        touch(os.path.join(self.base, 'd', 'z'))
    def tearDown(self):
        if os.path.exists(self.base):
            shutil.rmtree(self.base)

    def test_sorted_files(self):
        res = list(util.sorted_walk(self.base))
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0],
                         (self.base, ['d'], ['x', 'y']))
        self.assertEqual(res[1],
                         (os.path.join(self.base, 'd'), [], ['z']))

    def test_ignore_file(self):
        res = list(util.sorted_walk(self.base, ('x',)))
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0],
                         (self.base, ['d'], ['y']))
        self.assertEqual(res[1],
                         (os.path.join(self.base, 'd'), [], ['z']))

    def test_ignore_directory(self):
        res = list(util.sorted_walk(self.base, ('d',)))
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0],
                         (self.base, [], ['x', 'y']))

    def test_ignore_everything(self):
        res = list(util.sorted_walk(self.base, ('*',)))
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0],
                         (self.base, [], []))

class UniquePathTest(unittest.TestCase):
    def setUp(self):
        self.base = os.path.join(_common.RSRC, 'testdir')
        os.mkdir(self.base)
        touch(os.path.join(self.base, 'x.mp3'))
        touch(os.path.join(self.base, 'x.1.mp3'))
        touch(os.path.join(self.base, 'x.2.mp3'))
        touch(os.path.join(self.base, 'y.mp3'))
    def tearDown(self):
        if os.path.exists(self.base):
            shutil.rmtree(self.base)

    def test_new_file_unchanged(self):
        path = util.unique_path(os.path.join(self.base, 'z.mp3'))
        self.assertEqual(path, os.path.join(self.base, 'z.mp3'))

    def test_conflicting_file_appends_1(self):
        path = util.unique_path(os.path.join(self.base, 'y.mp3'))
        self.assertEqual(path, os.path.join(self.base, 'y.1.mp3'))

    def test_conflicting_file_appends_higher_number(self):
        path = util.unique_path(os.path.join(self.base, 'x.mp3'))
        self.assertEqual(path, os.path.join(self.base, 'x.3.mp3'))

    def test_conflicting_file_with_number_increases_number(self):
        path = util.unique_path(os.path.join(self.base, 'x.1.mp3'))
        self.assertEqual(path, os.path.join(self.base, 'x.3.mp3'))

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
