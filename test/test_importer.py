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

"""Tests for the general importer functionality.
"""
import unittest
import os
import shutil

import _common
from beets import library
from beets import importer
from beets import mediafile
from beets.autotag import AlbumInfo, TrackInfo

TEST_TITLES = ('The Opener', 'The Second Track', 'The Last Track')
class NonAutotaggedImportTest(unittest.TestCase):
    def setUp(self):
        self.io = _common.DummyIO()
        self.io.install()

        self.libdb = os.path.join(_common.RSRC, 'testlib.blb')
        self.lib = library.Library(self.libdb)
        self.libdir = os.path.join(_common.RSRC, 'testlibdir')
        self.lib.directory = self.libdir
        self.lib.path_formats = [(
            'default', os.path.join('$artist', '$album', '$title')
        )]

        self.srcdir = os.path.join(_common.RSRC, 'testsrcdir')

    def tearDown(self):
        self.io.restore()
        if os.path.exists(self.libdb):
            os.remove(self.libdb)
        if os.path.exists(self.libdir):
            shutil.rmtree(self.libdir)
        if os.path.exists(self.srcdir):
            shutil.rmtree(self.srcdir)

    def _create_test_file(self, filepath, metadata):
        """Creates an mp3 file at the given path within self.srcdir.
        filepath is given as an array of folder names, ending with the
        file name. Sets the file's metadata from the provided dict.
        Returns the full, real path to the file.
        """
        realpath = os.path.join(self.srcdir, *filepath)
        if not os.path.exists(os.path.dirname(realpath)):
            os.makedirs(os.path.dirname(realpath))
        shutil.copy(os.path.join(_common.RSRC, 'full.mp3'), realpath)

        f = mediafile.MediaFile(realpath)
        for attr in metadata:
            setattr(f, attr, metadata[attr])
        f.save()

        return realpath

    def _run_import(self, titles=TEST_TITLES, delete=False, threaded=False,
                    singletons=False):
        # Make a bunch of tracks to import.
        paths = []
        for i, title in enumerate(titles):
            paths.append(self._create_test_file(
                ['the_album', 'track_%s.mp3' % (i+1)],
                {
                    'track': (i+1),
                    'artist': 'The Artist',
                    'album': 'The Album',
                    'title': title,
                }))

        # Run the UI "beet import" command!
        importer.run_import(
                lib=self.lib,
                paths=[os.path.dirname(paths[0])],
                copy=True,
                write=True,
                autot=False,
                logfile=None,
                art=False,
                threaded=threaded,
                color=False,
                delete=delete,
                quiet=True,
                resume=False,
                quiet_fallback='skip',
                choose_match_func = None,
                should_resume_func = None,
                singletons = singletons,
                choose_item_func = None,
                timid = False,
                query = None,
                incremental = False,
                ignore = [],
        )

        return paths

    def test_album_created_with_track_artist(self):
        self._run_import()
        albums = self.lib.albums()
        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0].albumartist, 'The Artist')

    def _copy_arrives(self):
        artist_folder = os.path.join(self.libdir, 'The Artist')
        album_folder = os.path.join(artist_folder, 'The Album')
        self.assertEqual(len(os.listdir(artist_folder)), 1)
        self.assertEqual(len(os.listdir(album_folder)), 3)

        filenames = set(os.listdir(album_folder))
        destinations = set('%s.mp3' % title for title in TEST_TITLES)
        self.assertEqual(filenames, destinations)
    def test_import_copy_arrives(self):
        self._run_import()
        self._copy_arrives()
    def test_threaded_import_copy_arrives(self):
        self._run_import(threaded=True)
        self._copy_arrives()

    def test_import_no_delete(self):
        paths = self._run_import(['sometrack'], delete=False)
        self.assertTrue(os.path.exists(paths[0]))

    def test_import_with_delete(self):
        paths = self._run_import(['sometrack'], delete=True)
        self.assertFalse(os.path.exists(paths[0]))

    def test_import_singleton(self):
        paths = self._run_import(['sometrack'], singletons=True)
        self.assertTrue(os.path.exists(paths[0]))

# Utilities for invoking the apply_choices coroutine.
def _call_apply(coros, items, info):
    task = importer.ImportTask(None, None, None)
    task.is_album = True
    task.set_choice((info, items))
    if not isinstance(coros, list):
        coros = [coros]
    for coro in coros:
        task = coro.send(task)
    return task
def _call_apply_choice(coro, items, choice, album=True):
    task = importer.ImportTask(None, None, items)
    task.is_album = album
    if not album:
        task.item = items[0]
    task.set_choice(choice)
    coro.send(task)

class ImportApplyTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        self.libdir = os.path.join(_common.RSRC, 'testlibdir')
        os.mkdir(self.libdir)
        self.libpath = os.path.join(_common.RSRC, 'testlib.blb')
        self.lib = library.Library(self.libpath, self.libdir)
        self.lib.path_formats = [
            ('default', 'one'),
            ('singleton:true', 'three'),
            ('comp:true', 'two'),
        ]

        self.srcpath = os.path.join(self.libdir, 'srcfile.mp3')
        shutil.copy(os.path.join(_common.RSRC, 'full.mp3'), self.srcpath)
        self.i = library.Item.from_path(self.srcpath)
        self.i.comp = False

        trackinfo = TrackInfo('one',  'trackid', 'some artist',
                              'artistid', 1)
        self.info = AlbumInfo(
            artist = 'some artist',
            album = 'some album',
            tracks = [trackinfo],
            va = False,
            album_id = 'albumid',
            artist_id = 'artistid',
            albumtype = 'soundtrack',
        )

    def tearDown(self):
        shutil.rmtree(self.libdir)
        if os.path.exists(self.libpath):
            os.unlink(self.libpath)

    def test_finalize_no_delete(self):
        config = _common.iconfig(self.lib, delete=False)
        applyc = importer.apply_choices(config)
        applyc.next()
        finalize = importer.finalize(config)
        finalize.next()
        _call_apply([applyc, finalize], [self.i], self.info)
        self.assertExists(self.srcpath)

    def test_finalize_with_delete(self):
        config = _common.iconfig(self.lib, delete=True)
        applyc = importer.apply_choices(config)
        applyc.next()
        finalize = importer.finalize(config)
        finalize.next()
        _call_apply([applyc, finalize], [self.i], self.info)
        self.assertNotExists(self.srcpath)

    def test_apply_asis_uses_album_path(self):
        coro = importer.apply_choices(_common.iconfig(self.lib))
        coro.next() # Prime coroutine.
        _call_apply_choice(coro, [self.i], importer.action.ASIS)
        self.assertExists(os.path.join(self.libdir, 'one.mp3'))

    def test_apply_match_uses_album_path(self):
        coro = importer.apply_choices(_common.iconfig(self.lib))
        coro.next() # Prime coroutine.
        _call_apply(coro, [self.i], self.info)
        self.assertExists(os.path.join(self.libdir, 'one.mp3'))

    def test_apply_tracks_uses_singleton_path(self):
        coro = importer.apply_choices(_common.iconfig(self.lib))
        coro.next() # Prime coroutine.

        task = importer.ImportTask.item_task(self.i)
        task.set_choice(self.info.tracks[0])
        coro.send(task)

        self.assertExists(
            os.path.join(self.libdir, 'three.mp3')
        )

    def test_apply_sentinel(self):
        coro = importer.apply_choices(_common.iconfig(self.lib))
        coro.next()
        coro.send(importer.ImportTask.done_sentinel('toppath'))
        # Just test no exception for now.

    def test_apply_populates_old_paths(self):
        coro = importer.apply_choices(_common.iconfig(self.lib))
        coro.next()
        task = _call_apply(coro, [self.i], self.info)
        self.assertEqual(task.old_paths, [self.srcpath])

    def test_reimport_moves_file_and_does_not_add_to_old_paths(self):
        # First, add the item to the library.
        temp_item = library.Item.from_path(self.srcpath)
        self.lib.add(temp_item)
        self.lib.save()

        # Then, re-import the same file.
        coro = importer.apply_choices(_common.iconfig(self.lib))
        coro.next()
        task = _call_apply(coro, [self.i], self.info)

        # Old file should be gone.
        self.assertNotExists(self.srcpath)
        # New file should be present.
        self.assertExists(os.path.join(self.libdir, 'one.mp3'))
        # Also, the old file should not be in old_paths because it does
        # not exist.
        self.assertEqual(task.old_paths, [])

class AsIsApplyTest(unittest.TestCase):
    def setUp(self):
        self.dbpath = os.path.join(_common.RSRC, 'templib.blb')
        self.lib = library.Library(self.dbpath)
        self.config = _common.iconfig(self.lib, write=False, copy=False)

        # Make an "album" that has a homogenous artist. (Modified by
        # individual tests.)
        i1 = _common.item()
        i2 = _common.item()
        i3 = _common.item()
        i1.title = 'first item'
        i2.title = 'second item'
        i3.title = 'third item'
        i1.comp = i2.comp = i3.comp = False
        i1.albumartist = i2.albumartist = i3.albumartist = ''
        self.items = [i1, i2, i3]

    def tearDown(self):
        os.remove(self.dbpath)

    def _apply_result(self):
        """Run the "apply" coroutine and get the resulting Album."""
        coro = importer.apply_choices(self.config)
        coro.next()
        _call_apply_choice(coro, self.items, importer.action.ASIS)

        return self.lib.albums()[0]

    def test_asis_homogenous_va_not_set(self):
        alb = self._apply_result()
        self.assertFalse(alb.comp)
        self.assertEqual(alb.albumartist, self.items[2].artist)

    def test_asis_heterogenous_va_set(self):
        self.items[0].artist = 'another artist'
        self.items[1].artist = 'some other artist'
        alb = self._apply_result()
        self.assertTrue(alb.comp)
        self.assertEqual(alb.albumartist, 'Various Artists')

    def test_asis_majority_artist_va_not_set(self):
        self.items[0].artist = 'another artist'
        alb = self._apply_result()
        self.assertFalse(alb.comp)
        self.assertEqual(alb.albumartist, self.items[2].artist)

class ApplyExistingItemsTest(unittest.TestCase, _common.ExtraAsserts):
    def setUp(self):
        self.libdir = os.path.join(_common.RSRC, 'testlibdir')
        os.mkdir(self.libdir)

        self.dbpath = os.path.join(_common.RSRC, 'templib.blb')
        self.lib = library.Library(self.dbpath, self.libdir)
        self.lib.path_formats = [
            ('default', '$artist/$title'),
        ]
        self.config = _common.iconfig(self.lib, write=False, copy=False)

        self.srcpath = os.path.join(self.libdir, 'srcfile.mp3')
        shutil.copy(os.path.join(_common.RSRC, 'full.mp3'), self.srcpath)
        self.i = library.Item.from_path(self.srcpath)
        self.i.comp = False

    def tearDown(self):
        os.remove(self.dbpath)
        shutil.rmtree(self.libdir)

    def _apply_asis(self, items, album=True):
        """Run the "apply" coroutine."""
        coro = importer.apply_choices(self.config)
        coro.next()
        _call_apply_choice(coro, items, importer.action.ASIS, album)

    def test_apply_existing_album_does_not_duplicate_item(self):
        # First, import an item to add it to the library.
        self._apply_asis([self.i])

        # Get the item's path and import it again.
        item = self.lib.items().next()
        new_item = library.Item.from_path(item.path)
        self._apply_asis([new_item])

        # Should not be duplicated.
        self.assertEqual(len(list(self.lib.items())), 1)

    def test_apply_existing_album_does_not_duplicate_album(self):
        # As above.
        self._apply_asis([self.i])
        item = self.lib.items().next()
        new_item = library.Item.from_path(item.path)
        self._apply_asis([new_item])

        # Should not be duplicated.
        self.assertEqual(len(list(self.lib.albums())), 1)

    def test_apply_existing_singleton_does_not_duplicate_album(self):
        self._apply_asis([self.i])
        item = self.lib.items().next()
        new_item = library.Item.from_path(item.path)
        self._apply_asis([new_item], False)

        # Should not be duplicated.
        self.assertEqual(len(list(self.lib.items())), 1)

    def test_apply_existing_item_new_metadata_does_not_duplicate(self):
        # We want to copy the item to a new location.
        self.config.copy = True

        # Import with existing metadata.
        self._apply_asis([self.i])

        # Import again with new metadata.
        item = self.lib.items().next()
        new_item = library.Item.from_path(item.path)
        new_item.title = 'differentTitle'
        self._apply_asis([new_item])

        # Should not be duplicated.
        self.assertEqual(len(list(self.lib.items())), 1)
        self.assertEqual(len(list(self.lib.albums())), 1)

    def test_apply_existing_item_new_metadata_moves_files(self):
        # As above, import with old metadata and then reimport with new.
        self.config.copy = True
        self._apply_asis([self.i])
        item = self.lib.items().next()
        new_item = library.Item.from_path(item.path)
        new_item.title = 'differentTitle'
        self._apply_asis([new_item])

        item = self.lib.items().next()
        self.assertTrue('differentTitle' in item.path)
        self.assertExists(item.path)

    def test_apply_existing_item_new_metadata_copy_disabled(self):
        # Import *without* copying to ensure that the path does *not* change.
        self.config.copy = False
        self._apply_asis([self.i])
        item = self.lib.items().next()
        new_item = library.Item.from_path(item.path)
        new_item.title = 'differentTitle'
        self._apply_asis([new_item])

        item = self.lib.items().next()
        self.assertFalse('differentTitle' in item.path)
        self.assertExists(item.path)

    def test_apply_existing_item_new_metadata_removes_old_files(self):
        self.config.copy = True
        self._apply_asis([self.i])
        item = self.lib.items().next()
        oldpath = item.path
        new_item = library.Item.from_path(item.path)
        new_item.title = 'differentTitle'
        self._apply_asis([new_item])

        item = self.lib.items().next()
        self.assertNotExists(oldpath)

    def test_apply_existing_item_new_metadata_delete_enabled(self):
        # The "delete" flag should be ignored -- only the "copy" flag
        # controls whether files move.
        self.config.copy = True
        self.config.delete = True # !
        self._apply_asis([self.i])
        item = self.lib.items().next()
        oldpath = item.path
        new_item = library.Item.from_path(item.path)
        new_item.title = 'differentTitle'
        self._apply_asis([new_item])

        item = self.lib.items().next()
        self.assertNotExists(oldpath)
        self.assertTrue('differentTitle' in item.path)
        self.assertExists(item.path)

    def test_apply_existing_item_preserves_file(self):
        # With copying enabled, import the item twice with same metadata.
        self.config.copy = True
        self._apply_asis([self.i])
        item = self.lib.items().next()
        oldpath = item.path
        new_item = library.Item.from_path(item.path)
        self._apply_asis([new_item])

        self.assertEqual(len(list(self.lib.items())), 1)
        item = self.lib.items().next()
        self.assertEqual(oldpath, item.path)
        self.assertExists(oldpath)

    def test_apply_existing_item_preserves_file_delete_enabled(self):
        self.config.copy = True
        self.config.delete = True # !
        self._apply_asis([self.i])
        item = self.lib.items().next()
        new_item = library.Item.from_path(item.path)
        self._apply_asis([new_item])

        self.assertEqual(len(list(self.lib.items())), 1)
        item = self.lib.items().next()
        self.assertExists(item.path)

    def test_same_album_does_not_duplicate(self):
        # With the -L flag, exactly the same item (with the same ID)
        # is re-imported. This test simulates that situation.
        self._apply_asis([self.i])
        item = self.lib.items().next()
        self._apply_asis([item])

        # Should not be duplicated.
        self.assertEqual(len(list(self.lib.items())), 1)
        self.assertEqual(len(list(self.lib.albums())), 1)

class InferAlbumDataTest(unittest.TestCase):
    def setUp(self):
        i1 = _common.item()
        i2 = _common.item()
        i3 = _common.item()
        i1.title = 'first item'
        i2.title = 'second item'
        i3.title = 'third item'
        i1.comp = i2.comp = i3.comp = False
        i1.albumartist = i2.albumartist = i3.albumartist = ''
        i1.mb_albumartistid = i2.mb_albumartistid = i3.mb_albumartistid = ''
        self.items = [i1, i2, i3]

        self.task = importer.ImportTask(path='a path', toppath='top path',
                                        items=self.items)
        self.task.set_null_match()

    def _infer(self):
        importer._infer_album_fields(self.task)

    def test_asis_homogenous_single_artist(self):
        self.task.set_choice(importer.action.ASIS)
        self._infer()
        self.assertFalse(self.items[0].comp)
        self.assertEqual(self.items[0].albumartist, self.items[2].artist)

    def test_asis_heterogenous_va(self):
        self.items[0].artist = 'another artist'
        self.items[1].artist = 'some other artist'
        self.task.set_choice(importer.action.ASIS)

        self._infer()

        self.assertTrue(self.items[0].comp)
        self.assertEqual(self.items[0].albumartist, 'Various Artists')

    def test_asis_comp_applied_to_all_items(self):
        self.items[0].artist = 'another artist'
        self.items[1].artist = 'some other artist'
        self.task.set_choice(importer.action.ASIS)

        self._infer()

        for item in self.items:
            self.assertTrue(item.comp)
            self.assertEqual(item.albumartist, 'Various Artists')

    def test_asis_majority_artist_single_artist(self):
        self.items[0].artist = 'another artist'
        self.task.set_choice(importer.action.ASIS)

        self._infer()

        self.assertFalse(self.items[0].comp)
        self.assertEqual(self.items[0].albumartist, self.items[2].artist)

    def test_apply_gets_artist_and_id(self):
        self.task.set_choice(({}, self.items)) # APPLY

        self._infer()

        self.assertEqual(self.items[0].albumartist, self.items[0].artist)
        self.assertEqual(self.items[0].mb_albumartistid,
                         self.items[0].mb_artistid)

    def test_apply_lets_album_values_override(self):
        for item in self.items:
            item.albumartist = 'some album artist'
            item.mb_albumartistid = 'some album artist id'
        self.task.set_choice(({}, self.items)) # APPLY

        self._infer()

        self.assertEqual(self.items[0].albumartist,
                         'some album artist')
        self.assertEqual(self.items[0].mb_albumartistid,
                         'some album artist id')

    def test_small_single_artist_album(self):
        self.items = [self.items[0]]
        self.task.items = self.items
        self.task.set_choice(importer.action.ASIS)
        self._infer()
        self.assertFalse(self.items[0].comp)

    def test_first_item_null_apply(self):
        self.items[0] = None
        self.task.set_choice(({}, self.items)) # APPLY
        self._infer()
        self.assertFalse(self.items[1].comp)
        self.assertEqual(self.items[1].albumartist, self.items[2].artist)

class DuplicateCheckTest(unittest.TestCase):
    def setUp(self):
        self.lib = library.Library(':memory:')
        self.i = _common.item()
        self.album = self.lib.add_album([self.i])

    def _album_task(self, asis, artist=None, album=None, existing=False):
        if existing:
            item = self.i
        else:
            item = _common.item()
        artist = artist or item.albumartist
        album = album or item.album

        task = importer.ImportTask(path='a path', toppath='top path',
                                   items=[item])
        task.set_match(artist, album, None, None)
        if asis:
            task.set_choice(importer.action.ASIS)
        else:
            task.set_choice((
                AlbumInfo(album, None, artist, None, None),
                [item]
            ))
        return task

    def _item_task(self, asis, artist=None, title=None, existing=False):
        if existing:
            item = self.i
        else:
            item = _common.item()
        artist = artist or item.artist
        title = title or item.title

        task = importer.ImportTask.item_task(item)
        if asis:
            item.artist = artist
            item.title = title
            task.set_choice(importer.action.ASIS)
        else:
            task.set_choice(TrackInfo(title, None, artist))
        return task

    def test_duplicate_album_apply(self):
        res = importer._duplicate_check(self.lib, self._album_task(False))
        self.assertTrue(res)

    def test_different_album_apply(self):
        res = importer._duplicate_check(self.lib,
                                        self._album_task(False, 'xxx', 'yyy'))
        self.assertFalse(res)

    def test_duplicate_album_asis(self):
        res = importer._duplicate_check(self.lib, self._album_task(True))
        self.assertTrue(res)

    def test_different_album_asis(self):
        res = importer._duplicate_check(self.lib,
                                        self._album_task(True, 'xxx', 'yyy'))
        self.assertFalse(res)

    def test_duplicate_va_album(self):
        self.album.albumartist = 'an album artist'
        res = importer._duplicate_check(self.lib,
                    self._album_task(False, 'an album artist'))
        self.assertTrue(res)

    def test_duplicate_item_apply(self):
        res = importer._item_duplicate_check(self.lib, 
                                             self._item_task(False))
        self.assertTrue(res)

    def test_different_item_apply(self):
        res = importer._item_duplicate_check(self.lib, 
                                    self._item_task(False, 'xxx', 'yyy'))
        self.assertFalse(res)

    def test_duplicate_item_asis(self):
        res = importer._item_duplicate_check(self.lib, 
                                             self._item_task(True))
        self.assertTrue(res)

    def test_different_item_asis(self):
        res = importer._item_duplicate_check(self.lib, 
                                    self._item_task(True, 'xxx', 'yyy'))
        self.assertFalse(res)

    def test_recent_item(self):
        recent = set()
        importer._item_duplicate_check(self.lib, 
                                       self._item_task(False, 'xxx', 'yyy'), 
                                       recent)
        res = importer._item_duplicate_check(self.lib, 
                                       self._item_task(False, 'xxx', 'yyy'), 
                                       recent)
        self.assertTrue(res)

    def test_recent_album(self):
        recent = set()
        importer._duplicate_check(self.lib, 
                                  self._album_task(False, 'xxx', 'yyy'), 
                                  recent)
        res = importer._duplicate_check(self.lib, 
                                  self._album_task(False, 'xxx', 'yyy'), 
                                  recent)
        self.assertTrue(res)

    def test_duplicate_album_existing(self):
        res = importer._duplicate_check(self.lib,
                                        self._album_task(False, existing=True))
        self.assertFalse(res)

    def test_duplicate_item_existing(self):
        res = importer._item_duplicate_check(self.lib, 
                                        self._item_task(False, existing=True))
        self.assertFalse(res)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
