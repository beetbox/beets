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

"""Test file manipulation functionality of Item.
"""
from __future__ import division, absolute_import, print_function

import shutil
import os
import stat
from os.path import join
import unittest

from test import _common
from test._common import item, touch
import beets.library
from beets import util


class MoveTest(_common.TestCase):
    def setUp(self):
        super(MoveTest, self).setUp()

        # make a temporary file
        self.path = join(self.temp_dir, b'temp.mp3')
        shutil.copy(join(_common.RSRC, b'full.mp3'), self.path)

        # add it to a temporary library
        self.lib = beets.library.Library(':memory:')
        self.i = beets.library.Item.from_path(self.path)
        self.lib.add(self.i)

        # set up the destination
        self.libdir = join(self.temp_dir, b'testlibdir')
        os.mkdir(self.libdir)
        self.lib.directory = self.libdir
        self.lib.path_formats = [('default',
                                  join('$artist', '$album', '$title'))]
        self.i.artist = 'one'
        self.i.album = 'two'
        self.i.title = 'three'
        self.dest = join(self.libdir, b'one', b'two', b'three.mp3')

        self.otherdir = join(self.temp_dir, b'testotherdir')

    def test_move_arrives(self):
        self.i.move()
        self.assertExists(self.dest)

    def test_move_to_custom_dir(self):
        self.i.move(basedir=self.otherdir)
        self.assertExists(join(self.otherdir, b'one', b'two', b'three.mp3'))

    def test_move_departs(self):
        self.i.move()
        self.assertNotExists(self.path)

    def test_move_in_lib_prunes_empty_dir(self):
        self.i.move()
        old_path = self.i.path
        self.assertExists(old_path)

        self.i.artist = u'newArtist'
        self.i.move()
        self.assertNotExists(old_path)
        self.assertNotExists(os.path.dirname(old_path))

    def test_copy_arrives(self):
        self.i.move(copy=True)
        self.assertExists(self.dest)

    def test_copy_does_not_depart(self):
        self.i.move(copy=True)
        self.assertExists(self.path)

    def test_move_changes_path(self):
        self.i.move()
        self.assertEqual(self.i.path, util.normpath(self.dest))

    def test_copy_already_at_destination(self):
        self.i.move()
        old_path = self.i.path
        self.i.move(copy=True)
        self.assertEqual(self.i.path, old_path)

    def test_move_already_at_destination(self):
        self.i.move()
        old_path = self.i.path
        self.i.move(copy=False)
        self.assertEqual(self.i.path, old_path)

    def test_read_only_file_copied_writable(self):
        # Make the source file read-only.
        os.chmod(self.path, 0o444)

        try:
            self.i.move(copy=True)
            self.assertTrue(os.access(self.i.path, os.W_OK))
        finally:
            # Make everything writable so it can be cleaned up.
            os.chmod(self.path, 0o777)
            os.chmod(self.i.path, 0o777)

    def test_move_avoids_collision_with_existing_file(self):
        # Make a conflicting file at the destination.
        dest = self.i.destination()
        os.makedirs(os.path.dirname(dest))
        touch(dest)

        self.i.move()
        self.assertNotEqual(self.i.path, dest)
        self.assertEqual(os.path.dirname(self.i.path),
                         os.path.dirname(dest))

    @unittest.skipUnless(_common.HAVE_SYMLINK, "need symlinks")
    def test_link_arrives(self):
        self.i.move(link=True)
        self.assertExists(self.dest)
        self.assertTrue(os.path.islink(self.dest))
        self.assertEqual(os.readlink(self.dest), self.path)

    @unittest.skipUnless(_common.HAVE_SYMLINK, "need symlinks")
    def test_link_does_not_depart(self):
        self.i.move(link=True)
        self.assertExists(self.path)

    @unittest.skipUnless(_common.HAVE_SYMLINK, "need symlinks")
    def test_link_changes_path(self):
        self.i.move(link=True)
        self.assertEqual(self.i.path, util.normpath(self.dest))

    @unittest.skipUnless(_common.HAVE_HARDLINK, "need hardlinks")
    def test_hardlink_arrives(self):
        self.i.move(hardlink=True)
        self.assertExists(self.dest)
        s1 = os.stat(self.path)
        s2 = os.stat(self.dest)
        self.assertTrue(
            (s1[stat.ST_INO], s1[stat.ST_DEV]) ==
            (s2[stat.ST_INO], s2[stat.ST_DEV])
        )

    @unittest.skipUnless(_common.HAVE_HARDLINK, "need hardlinks")
    def test_hardlink_does_not_depart(self):
        self.i.move(hardlink=True)
        self.assertExists(self.path)

    @unittest.skipUnless(_common.HAVE_HARDLINK, "need hardlinks")
    def test_hardlink_changes_path(self):
        self.i.move(hardlink=True)
        self.assertEqual(self.i.path, util.normpath(self.dest))


class HelperTest(_common.TestCase):
    def test_ancestry_works_on_file(self):
        p = '/a/b/c'
        a = ['/', '/a', '/a/b']
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
        a = ['/', 'a', 'b', 'c']
        self.assertEqual(util.components(p), a)

    def test_components_works_on_dir(self):
        p = '/a/b/c/'
        a = ['/', 'a', 'b', 'c']
        self.assertEqual(util.components(p), a)

    def test_components_works_on_relative(self):
        p = 'a/b/c'
        a = ['a', 'b', 'c']
        self.assertEqual(util.components(p), a)


class AlbumFileTest(_common.TestCase):
    def setUp(self):
        super(AlbumFileTest, self).setUp()

        # Make library and item.
        self.lib = beets.library.Library(':memory:')
        self.lib.path_formats = \
            [('default', join('$albumartist', '$album', '$title'))]
        self.libdir = os.path.join(self.temp_dir, b'testlibdir')
        self.lib.directory = self.libdir
        self.i = item(self.lib)
        # Make a file for the item.
        self.i.path = self.i.destination()
        util.mkdirall(self.i.path)
        touch(self.i.path)
        # Make an album.
        self.ai = self.lib.add_album((self.i,))
        # Alternate destination dir.
        self.otherdir = os.path.join(self.temp_dir, b'testotherdir')

    def test_albuminfo_move_changes_paths(self):
        self.ai.album = u'newAlbumName'
        self.ai.move()
        self.ai.store()
        self.i.load()

        self.assertTrue(b'newAlbumName' in self.i.path)

    def test_albuminfo_move_moves_file(self):
        oldpath = self.i.path
        self.ai.album = u'newAlbumName'
        self.ai.move()
        self.ai.store()
        self.i.load()

        self.assertFalse(os.path.exists(oldpath))
        self.assertTrue(os.path.exists(self.i.path))

    def test_albuminfo_move_copies_file(self):
        oldpath = self.i.path
        self.ai.album = u'newAlbumName'
        self.ai.move(True)
        self.ai.store()
        self.i.load()

        self.assertTrue(os.path.exists(oldpath))
        self.assertTrue(os.path.exists(self.i.path))

    def test_albuminfo_move_to_custom_dir(self):
        self.ai.move(basedir=self.otherdir)
        self.i.load()
        self.ai.store()
        self.assertTrue(b'testotherdir' in self.i.path)


class ArtFileTest(_common.TestCase):
    def setUp(self):
        super(ArtFileTest, self).setUp()

        # Make library and item.
        self.lib = beets.library.Library(':memory:')
        self.libdir = os.path.join(self.temp_dir, b'testlibdir')
        self.lib.directory = self.libdir
        self.i = item(self.lib)
        self.i.path = self.i.destination()
        # Make a music file.
        util.mkdirall(self.i.path)
        touch(self.i.path)
        # Make an album.
        self.ai = self.lib.add_album((self.i,))
        # Make an art file too.
        self.art = self.lib.get_album(self.i).art_destination('something.jpg')
        touch(self.art)
        self.ai.artpath = self.art
        self.ai.store()
        # Alternate destination dir.
        self.otherdir = os.path.join(self.temp_dir, b'testotherdir')

    def test_art_deleted_when_items_deleted(self):
        self.assertTrue(os.path.exists(self.art))
        self.ai.remove(True)
        self.assertFalse(os.path.exists(self.art))

    def test_art_moves_with_album(self):
        self.assertTrue(os.path.exists(self.art))
        oldpath = self.i.path
        self.ai.album = u'newAlbum'
        self.ai.move()
        self.i.load()

        self.assertNotEqual(self.i.path, oldpath)
        self.assertFalse(os.path.exists(self.art))
        newart = self.lib.get_album(self.i).art_destination(self.art)
        self.assertTrue(os.path.exists(newart))

    def test_art_moves_with_album_to_custom_dir(self):
        # Move the album to another directory.
        self.ai.move(basedir=self.otherdir)
        self.ai.store()
        self.i.load()

        # Art should be in new directory.
        self.assertNotExists(self.art)
        newart = self.lib.get_album(self.i).artpath
        self.assertExists(newart)
        self.assertTrue(b'testotherdir' in newart)

    def test_setart_copies_image(self):
        os.remove(self.art)

        newart = os.path.join(self.libdir, b'newart.jpg')
        touch(newart)
        i2 = item()
        i2.path = self.i.path
        i2.artist = u'someArtist'
        ai = self.lib.add_album((i2,))
        i2.move(True)

        self.assertEqual(ai.artpath, None)
        ai.set_art(newart)
        self.assertTrue(os.path.exists(ai.artpath))

    def test_setart_to_existing_art_works(self):
        os.remove(self.art)

        # Original art.
        newart = os.path.join(self.libdir, b'newart.jpg')
        touch(newart)
        i2 = item()
        i2.path = self.i.path
        i2.artist = u'someArtist'
        ai = self.lib.add_album((i2,))
        i2.move(True)
        ai.set_art(newart)

        # Set the art again.
        ai.set_art(ai.artpath)
        self.assertTrue(os.path.exists(ai.artpath))

    def test_setart_to_existing_but_unset_art_works(self):
        newart = os.path.join(self.libdir, b'newart.jpg')
        touch(newart)
        i2 = item()
        i2.path = self.i.path
        i2.artist = u'someArtist'
        ai = self.lib.add_album((i2,))
        i2.move(True)

        # Copy the art to the destination.
        artdest = ai.art_destination(newart)
        shutil.copy(newart, artdest)

        # Set the art again.
        ai.set_art(artdest)
        self.assertTrue(os.path.exists(ai.artpath))

    def test_setart_to_conflicting_file_gets_new_path(self):
        newart = os.path.join(self.libdir, b'newart.jpg')
        touch(newart)
        i2 = item()
        i2.path = self.i.path
        i2.artist = u'someArtist'
        ai = self.lib.add_album((i2,))
        i2.move(True)

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

        newart = os.path.join(self.libdir, b'newart.jpg')
        touch(newart)
        os.chmod(newart, 0o400)  # read-only

        try:
            i2 = item()
            i2.path = self.i.path
            i2.artist = u'someArtist'
            ai = self.lib.add_album((i2,))
            i2.move(True)
            ai.set_art(newart)

            mode = stat.S_IMODE(os.stat(ai.artpath).st_mode)
            self.assertTrue(mode & stat.S_IRGRP)
            self.assertTrue(os.access(ai.artpath, os.W_OK))

        finally:
            # Make everything writable so it can be cleaned up.
            os.chmod(newart, 0o777)
            os.chmod(ai.artpath, 0o777)

    def test_move_last_file_moves_albumart(self):
        oldartpath = self.lib.albums()[0].artpath
        self.assertExists(oldartpath)

        self.ai.album = u'different_album'
        self.ai.store()
        self.ai.items()[0].move()

        artpath = self.lib.albums()[0].artpath
        self.assertTrue(b'different_album' in artpath)
        self.assertExists(artpath)
        self.assertNotExists(oldartpath)

    def test_move_not_last_file_does_not_move_albumart(self):
        i2 = item()
        i2.albumid = self.ai.id
        self.lib.add(i2)

        oldartpath = self.lib.albums()[0].artpath
        self.assertExists(oldartpath)

        self.i.album = u'different_album'
        self.i.album_id = None  # detach from album
        self.i.move()

        artpath = self.lib.albums()[0].artpath
        self.assertFalse(b'different_album' in artpath)
        self.assertEqual(artpath, oldartpath)
        self.assertExists(oldartpath)


class RemoveTest(_common.TestCase):
    def setUp(self):
        super(RemoveTest, self).setUp()

        # Make library and item.
        self.lib = beets.library.Library(':memory:')
        self.libdir = os.path.join(self.temp_dir, b'testlibdir')
        self.lib.directory = self.libdir
        self.i = item(self.lib)
        self.i.path = self.i.destination()
        # Make a music file.
        util.mkdirall(self.i.path)
        touch(self.i.path)
        # Make an album with the item.
        self.ai = self.lib.add_album((self.i,))

    def test_removing_last_item_prunes_empty_dir(self):
        parent = os.path.dirname(self.i.path)
        self.assertExists(parent)
        self.i.remove(True)
        self.assertNotExists(parent)

    def test_removing_last_item_preserves_nonempty_dir(self):
        parent = os.path.dirname(self.i.path)
        touch(os.path.join(parent, b'dummy.txt'))
        self.i.remove(True)
        self.assertExists(parent)

    def test_removing_last_item_prunes_dir_with_blacklisted_file(self):
        parent = os.path.dirname(self.i.path)
        touch(os.path.join(parent, b'.DS_Store'))
        self.i.remove(True)
        self.assertNotExists(parent)

    def test_removing_without_delete_leaves_file(self):
        path = self.i.path
        self.i.remove(False)
        self.assertExists(path)

    def test_removing_last_item_preserves_library_dir(self):
        self.i.remove(True)
        self.assertExists(self.libdir)

    def test_removing_item_outside_of_library_deletes_nothing(self):
        self.lib.directory = os.path.join(self.temp_dir, b'xxx')
        parent = os.path.dirname(self.i.path)
        self.i.remove(True)
        self.assertExists(parent)

    def test_removing_last_item_in_album_with_albumart_prunes_dir(self):
        artfile = os.path.join(self.temp_dir, b'testart.jpg')
        touch(artfile)
        self.ai.set_art(artfile)
        self.ai.store()

        parent = os.path.dirname(self.i.path)
        self.i.remove(True)
        self.assertNotExists(parent)


# Tests that we can "delete" nonexistent files.
class SoftRemoveTest(_common.TestCase):
    def setUp(self):
        super(SoftRemoveTest, self).setUp()

        self.path = os.path.join(self.temp_dir, b'testfile')
        touch(self.path)

    def test_soft_remove_deletes_file(self):
        util.remove(self.path, True)
        self.assertNotExists(self.path)

    def test_soft_remove_silent_on_no_file(self):
        try:
            util.remove(self.path + b'XXX', True)
        except OSError:
            self.fail(u'OSError when removing path')


class SafeMoveCopyTest(_common.TestCase):
    def setUp(self):
        super(SafeMoveCopyTest, self).setUp()

        self.path = os.path.join(self.temp_dir, b'testfile')
        touch(self.path)
        self.otherpath = os.path.join(self.temp_dir, b'testfile2')
        touch(self.otherpath)
        self.dest = self.path + b'.dest'

    def test_successful_move(self):
        util.move(self.path, self.dest)
        self.assertExists(self.dest)
        self.assertNotExists(self.path)

    def test_successful_copy(self):
        util.copy(self.path, self.dest)
        self.assertExists(self.dest)
        self.assertExists(self.path)

    def test_unsuccessful_move(self):
        with self.assertRaises(util.FilesystemError):
            util.move(self.path, self.otherpath)

    def test_unsuccessful_copy(self):
        with self.assertRaises(util.FilesystemError):
            util.copy(self.path, self.otherpath)

    def test_self_move(self):
        util.move(self.path, self.path)
        self.assertExists(self.path)

    def test_self_copy(self):
        util.copy(self.path, self.path)
        self.assertExists(self.path)


class PruneTest(_common.TestCase):
    def setUp(self):
        super(PruneTest, self).setUp()

        self.base = os.path.join(self.temp_dir, b'testdir')
        os.mkdir(self.base)
        self.sub = os.path.join(self.base, b'subdir')
        os.mkdir(self.sub)

    def test_prune_existent_directory(self):
        util.prune_dirs(self.sub, self.base)
        self.assertExists(self.base)
        self.assertNotExists(self.sub)

    def test_prune_nonexistent_directory(self):
        util.prune_dirs(os.path.join(self.sub, b'another'), self.base)
        self.assertExists(self.base)
        self.assertNotExists(self.sub)


class WalkTest(_common.TestCase):
    def setUp(self):
        super(WalkTest, self).setUp()

        self.base = os.path.join(self.temp_dir, b'testdir')
        os.mkdir(self.base)
        touch(os.path.join(self.base, b'y'))
        touch(os.path.join(self.base, b'x'))
        os.mkdir(os.path.join(self.base, b'd'))
        touch(os.path.join(self.base, b'd', b'z'))

    def test_sorted_files(self):
        res = list(util.sorted_walk(self.base))
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0],
                         (self.base, [b'd'], [b'x', b'y']))
        self.assertEqual(res[1],
                         (os.path.join(self.base, b'd'), [], [b'z']))

    def test_ignore_file(self):
        res = list(util.sorted_walk(self.base, (b'x',)))
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0],
                         (self.base, [b'd'], [b'y']))
        self.assertEqual(res[1],
                         (os.path.join(self.base, b'd'), [], [b'z']))

    def test_ignore_directory(self):
        res = list(util.sorted_walk(self.base, (b'd',)))
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0],
                         (self.base, [], [b'x', b'y']))

    def test_ignore_everything(self):
        res = list(util.sorted_walk(self.base, (b'*',)))
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0],
                         (self.base, [], []))


class UniquePathTest(_common.TestCase):
    def setUp(self):
        super(UniquePathTest, self).setUp()

        self.base = os.path.join(self.temp_dir, b'testdir')
        os.mkdir(self.base)
        touch(os.path.join(self.base, b'x.mp3'))
        touch(os.path.join(self.base, b'x.1.mp3'))
        touch(os.path.join(self.base, b'x.2.mp3'))
        touch(os.path.join(self.base, b'y.mp3'))

    def test_new_file_unchanged(self):
        path = util.unique_path(os.path.join(self.base, b'z.mp3'))
        self.assertEqual(path, os.path.join(self.base, b'z.mp3'))

    def test_conflicting_file_appends_1(self):
        path = util.unique_path(os.path.join(self.base, b'y.mp3'))
        self.assertEqual(path, os.path.join(self.base, b'y.1.mp3'))

    def test_conflicting_file_appends_higher_number(self):
        path = util.unique_path(os.path.join(self.base, b'x.mp3'))
        self.assertEqual(path, os.path.join(self.base, b'x.3.mp3'))

    def test_conflicting_file_with_number_increases_number(self):
        path = util.unique_path(os.path.join(self.base, b'x.1.mp3'))
        self.assertEqual(path, os.path.join(self.base, b'x.3.mp3'))


class MkDirAllTest(_common.TestCase):
    def test_parent_exists(self):
        path = os.path.join(self.temp_dir, b'foo', b'bar', b'baz', b'qux.mp3')
        util.mkdirall(path)
        self.assertTrue(os.path.isdir(
            os.path.join(self.temp_dir, b'foo', b'bar', b'baz')
        ))

    def test_child_does_not_exist(self):
        path = os.path.join(self.temp_dir, b'foo', b'bar', b'baz', b'qux.mp3')
        util.mkdirall(path)
        self.assertTrue(not os.path.exists(
            os.path.join(self.temp_dir, b'foo', b'bar', b'baz', b'qux.mp3')
        ))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
