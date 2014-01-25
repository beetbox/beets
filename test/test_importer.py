# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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
import os
import shutil
import StringIO

import _common
from _common import unittest
from beets import library
from beets import importer
from beets import mediafile
from beets.autotag import AlbumInfo, TrackInfo, AlbumMatch, TrackMatch
from beets import config

TEST_TITLES = ('The Opener', 'The Second Track', 'The Last Track')
class ImportHelper(object):
    def _setup_library(self):
        self.libdb = os.path.join(self.temp_dir, 'testlib.blb')
        self.libdir = os.path.join(self.temp_dir, 'testlibdir')
        os.mkdir(self.libdir)

        self.lib = library.Library(self.libdb)
        self.lib.directory = self.libdir
        self.lib.path_formats = [
            ('default', os.path.join('$artist', '$album', '$title')),
            ('singleton:true', os.path.join('singletons', '$title')),
            ('comp:true', os.path.join('compilations','$album', '$title')),
        ]

    def _create_import_dir(self):
        """Creates a directory with media files to import.
        Sets ``self.import_path`` to the path of the directory. Also sets
        ``self.media_files`` to a list of all the paths for created media files.

        The directory has following layout
          the_album/
            track_1.mp3
            track_2.mp3
            track_3.mp3
        """
        self.import_path = os.path.join(self.temp_dir, 'testsrcdir')
        album_path = os.path.join(self.import_path, 'the_album')
        os.makedirs(album_path)

        resource_path = os.path.join(_common.RSRC, 'full.mp3')

        metadata = {'artist': 'The Artist', 'album': 'The Album'}
        self.media_files = []
        for i in [1,2,3]:
            # Copy files
            medium_path = os.path.join(album_path, 'track_%d.mp3' % i)
            shutil.copy(resource_path, medium_path)
            medium = mediafile.MediaFile(medium_path)

            # Set metadata
            metadata['track'] = i
            metadata['title'] = TEST_TITLES[i-1]
            for attr in metadata: setattr(medium, attr, metadata[attr])
            medium.save()
            self.media_files.append(medium_path)

    def _run_import(self):
        # Run the UI "beet import" command!
        importer.ImportSession(self.lib,
                                logfile=None,
                                paths=[self.import_path],
                                query=None).run()

    def assert_file_in_lib(self, *segments):
        """Join the ``segments`` and assert that this path exists in the library
        directory
        """
        self.assertExists(os.path.join(self.libdir, *segments))


class ImportNonAutotaggedTest(_common.TestCase, ImportHelper):
    def setUp(self):
        super(ImportNonAutotaggedTest, self).setUp()

        self._setup_library()
        self._create_import_dir()

        config['import']['delete'] = False
        config['import']['threaded'] = False
        config['import']['singletons'] = False
        config['import']['move'] = False
        config['import']['autotag'] = False

        self.io.install()


    def test_album_created_with_track_artist(self):
        self._run_import()
        albums = self.lib.albums()
        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0].albumartist, 'The Album Artist')


    def test_import_copy_arrives_but_leaves_originals(self):
        self._run_import()
        self.assert_files_in_lib_dir()
        self.assert_import_files_exist()

    def test_threaded_import_copy_arrives(self):
        config['import']['threaded'] = True
        self._run_import()
        self.assert_files_in_lib_dir()
        self.assert_import_files_exist()

    def test_import_move(self):
        config['import']['move'] = True
        self._run_import()
        self.assert_files_in_lib_dir()
        self.assert_import_files_not_exist()


    def test_threaded_import_move(self):
        config['import']['move'] = True
        config['import']['threaded'] = True
        self._run_import()
        self.assert_files_in_lib_dir()
        self.assert_import_files_not_exist()

    def test_import_no_delete(self):
        config['import']['delete'] = False
        self._run_import()
        self.assert_files_in_lib_dir()
        self.assert_import_files_exist()

    def test_import_with_delete(self):
        config['import']['delete'] = True
        self._run_import()
        self.assert_files_in_lib_dir()
        self.assert_import_files_not_exist()

    def test_import_singleton(self):
        config['import']['singleton'] = True
        self._run_import()
        self.assert_import_files_exist()


    def assert_import_files_exist(self):
        for mediafile in self.media_files:
            self.assertTrue(os.path.exists(mediafile))

    def assert_import_files_not_exist(self):
        for mediafile in self.media_files:
            self.assertFalse(os.path.exists(mediafile))

    def assert_files_in_lib_dir(self):
        artist_folder = os.path.join(self.libdir, 'The Artist')
        album_folder = os.path.join(artist_folder, 'The Album')
        self.assertEqual(len(os.listdir(artist_folder)), 1)
        self.assertEqual(len(os.listdir(album_folder)), 3)

        filenames = set(os.listdir(album_folder))
        destinations = set('%s.mp3' % title for title in TEST_TITLES)
        self.assertEqual(filenames, destinations)

# Utilities for invoking the apply_choices, manipulate_files, and finalize
# coroutines.
def _call_stages(session, items, choice_or_info,
                 stages=[importer.apply_choices,
                         importer.manipulate_files,
                         importer.finalize],
                 album=True, toppath=None):
    # Set up the import task.
    task = importer.ImportTask(None, None, items)
    task.is_album = True
    task.toppath = toppath
    if not album:
        task.item = items[0]
    if isinstance(choice_or_info, importer.action):
        task.set_choice(choice_or_info)
    else:
        mapping = dict(zip(items, choice_or_info.tracks))
        task.set_choice(AlbumMatch(0, choice_or_info, mapping, set(), set()))

    # Call the coroutines.
    for stage in stages:
        coro = stage(session)
        coro.next()
        coro.send(task)

    return task

class ImportApplyTest(_common.TestCase, ImportHelper):
    def setUp(self):
        super(ImportApplyTest, self).setUp()

        self._setup_library()
        self.session = _common.import_session(self.lib)

        self.srcdir = os.path.join(self.temp_dir, 'testsrcdir')
        os.mkdir(self.srcdir)
        os.mkdir(os.path.join(self.srcdir, 'testalbum'))
        self.srcpath = os.path.join(self.srcdir, 'testalbum', 'srcfile.mp3')
        shutil.copy(os.path.join(_common.RSRC, 'full.mp3'), self.srcpath)

        # Set metadata
        medium = mediafile.MediaFile(self.srcpath)
        metadata = {
                     'artist': 'The Artist',
                     'album': 'The Album',
                     'title': 'Song',
                     'track': 1,
                   }
        for attr in metadata: setattr(medium, attr, metadata[attr])
        medium.save()

        self.i = library.Item.from_path(self.srcpath)
        self.i.comp = False
        self.lib.add(self.i)

        trackinfo = TrackInfo(
            title = 'Applied Title',
            track_id = 'trackid',
            artist = 'Applied Artist',
            artist_id = 'artistid',
            length = 1
        )
        self.info = AlbumInfo(
            artist = 'Applied Artist',
            album = 'Applied Album',
            tracks = [trackinfo],
            va = False,
            album_id = 'albumid',
            artist_id = 'artistid',
            albumtype = 'soundtrack',
        )

    def test_finalize_no_delete(self):
        config['import']['delete'] = False
        _call_stages(self.session, [self.i], self.info)
        self.assertExists(self.srcpath)

    def test_finalize_with_delete(self):
        config['import']['delete'] = True
        _call_stages(self.session, [self.i], self.info)
        self.assertNotExists(self.srcpath)

    def test_finalize_with_delete_prunes_directory_empty(self):
        config['import']['delete'] = True
        _call_stages(self.session, [self.i], self.info,
                     toppath=self.srcdir)
        self.assertNotExists(os.path.dirname(self.srcpath))

    def test_apply_asis_uses_album_path(self):
        _call_stages(self.session, [self.i], importer.action.ASIS)
        self.assert_file_in_lib( 'The Artist', 'The Album', 'Song.mp3')

    def test_apply_match_uses_album_path(self):
        _call_stages(self.session, [self.i], self.info)
        self.assert_file_in_lib(
                'Applied Artist', 'Applied Album', 'Applied Title.mp3')

    def test_apply_tracks_uses_singleton_path(self):
        apply_coro = importer.apply_choices(self.session)
        apply_coro.next()
        manip_coro = importer.manipulate_files(self.session)
        manip_coro.next()

        task = importer.ImportTask.item_task(self.i)
        task.set_choice(TrackMatch(0, self.info.tracks[0]))
        apply_coro.send(task)
        manip_coro.send(task)

        self.assert_file_in_lib('singletons', 'Applied Title.mp3')

    def test_apply_sentinel(self):
        coro = importer.apply_choices(self.session)
        coro.next()
        coro.send(importer.ImportTask.done_sentinel('toppath'))
        # Just test no exception for now.

    def test_apply_populates_old_paths(self):
        task = _call_stages(self.session, [self.i], self.info)
        self.assertEqual(task.old_paths, [self.srcpath])

    def test_reimport_inside_file_moves_and_does_not_add_to_old_paths(self):
        """Reimporting a file *inside* the library directory should
        *move* the file.
        """
        # Add the item to the library while inside the library directory.
        internal_srcpath = os.path.join(self.libdir, 'source.mp3')
        shutil.move(self.srcpath, internal_srcpath)
        temp_item = library.Item.from_path(internal_srcpath)
        self.lib.add(temp_item)
        self.lib._connection().commit()

        self.i = library.Item.from_path(internal_srcpath)
        self.i.comp = False

        # Then, re-import the same file.
        task = _call_stages(self.session, [self.i], self.info)

        # Old file should be gone.
        self.assertNotExists(internal_srcpath)
        # New file should be present.
        self.assert_file_in_lib(
                'Applied Artist', 'Applied Album', 'Applied Title.mp3')
        # Also, the old file should not be in old_paths because it does
        # not exist.
        self.assertEqual(task.old_paths, [])

    def test_reimport_outside_file_copies(self):
        """Reimporting a file *outside* the library directory should
        *copy* the file (when copying is enabled).
        """
        # First, add the item to the library.
        temp_item = library.Item.from_path(self.srcpath)
        self.lib.add(temp_item)
        self.lib._connection().commit()

        # Then, re-import the same file.
        task = _call_stages(self.session, [self.i], self.info)

        # Old file should still exist.
        self.assertExists(self.srcpath)
        # New file should also be present.
        self.assert_file_in_lib(
                'Applied Artist', 'Applied Album', 'Applied Title.mp3')
        # The old (copy-source) file should be marked for possible
        # deletion.
        self.assertEqual(task.old_paths, [self.srcpath])

    def test_apply_with_move(self):
        config['import']['move'] = True
        _call_stages(self.session, [self.i], self.info)
        self.assert_file_in_lib(
                'Applied Artist', 'Applied Album', 'Applied Title.mp3')
        self.assertNotExists(self.srcpath)

    def test_apply_with_move_prunes_empty_directory(self):
        config['import']['move'] = True
        _call_stages(self.session, [self.i], self.info, toppath=self.srcdir)
        self.assertNotExists(os.path.dirname(self.srcpath))

    def test_apply_with_move_prunes_with_extra_clutter(self):
        f = open(os.path.join(self.srcdir, 'testalbum', 'alog.log'), 'w')
        f.close()
        config['clutter'] = ['*.log']
        config['import']['move'] = True
        _call_stages(self.session, [self.i], self.info, toppath=self.srcdir)
        self.assertNotExists(os.path.dirname(self.srcpath))

    def test_manipulate_files_with_null_move(self):
        """It should be possible to "move" a file even when the file is
        already at the destination.
        """
        self.i.move()  # Already at destination.
        config['import']['move'] = True
        _call_stages(self.session, [self.i], self.info, toppath=self.srcdir,
                     stages=[importer.manipulate_files])
        self.assert_file_in_lib('singletons', 'Song.mp3')

class AsIsApplyTest(_common.TestCase):
    def setUp(self):
        super(AsIsApplyTest, self).setUp()

        self.dbpath = os.path.join(self.temp_dir, 'templib.blb')
        self.lib = library.Library(self.dbpath)
        self.session = _common.import_session(self.lib)

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

    def _apply_result(self):
        """Run the "apply" coroutines and get the resulting Album."""
        _call_stages(self.session, self.items, importer.action.ASIS,
                     stages=[importer.apply_choices])
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

class ApplyExistingItemsTest(_common.TestCase):
    def setUp(self):
        super(ApplyExistingItemsTest, self).setUp()

        self.libdir = os.path.join(self.temp_dir, 'testlibdir')
        os.mkdir(self.libdir)

        self.dbpath = os.path.join(self.temp_dir, 'templib.blb')
        self.lib = library.Library(self.dbpath, self.libdir)
        self.lib.path_formats = [
            ('default', '$artist/$title'),
        ]
        self.session = _common.import_session(self.lib)

        config['import']['write'] = False
        config['import']['copy'] = False

        self.srcpath = os.path.join(self.libdir, 'srcfile.mp3')
        shutil.copy(os.path.join(_common.RSRC, 'full.mp3'), self.srcpath)
        self.i = library.Item.from_path(self.srcpath)
        self.i.comp = False

    def _apply_asis(self, items, album=True):
        """Run the "apply" coroutine."""
        _call_stages(self.session, items, importer.action.ASIS, album=album,
                     stages=[importer.apply_choices,
                             importer.manipulate_files])

    def test_apply_existing_album_does_not_duplicate_item(self):
        # First, import an item to add it to the library.
        self._apply_asis([self.i])

        # Get the item's path and import it again.
        item = self.lib.items().get()
        new_item = library.Item.from_path(item.path)
        self._apply_asis([new_item])

        # Should not be duplicated.
        self.assertEqual(len(list(self.lib.items())), 1)

    def test_apply_existing_album_does_not_duplicate_album(self):
        # As above.
        self._apply_asis([self.i])
        item = self.lib.items().get()
        new_item = library.Item.from_path(item.path)
        self._apply_asis([new_item])

        # Should not be duplicated.
        self.assertEqual(len(list(self.lib.albums())), 1)

    def test_apply_existing_singleton_does_not_duplicate_album(self):
        self._apply_asis([self.i])
        item = self.lib.items().get()
        new_item = library.Item.from_path(item.path)
        self._apply_asis([new_item], False)

        # Should not be duplicated.
        self.assertEqual(len(list(self.lib.items())), 1)

    def test_apply_existing_item_new_metadata_does_not_duplicate(self):
        # We want to copy the item to a new location.
        config['import']['copy'] = True

        # Import with existing metadata.
        self._apply_asis([self.i])

        # Import again with new metadata.
        item = self.lib.items().get()
        new_item = library.Item.from_path(item.path)
        new_item.title = 'differentTitle'
        self._apply_asis([new_item])

        # Should not be duplicated.
        self.assertEqual(len(list(self.lib.items())), 1)
        self.assertEqual(len(list(self.lib.albums())), 1)

    def test_apply_existing_item_new_metadata_moves_files(self):
        # As above, import with old metadata and then reimport with new.
        config['import']['copy'] = True

        self._apply_asis([self.i])
        item = self.lib.items().get()
        new_item = library.Item.from_path(item.path)
        new_item.title = 'differentTitle'
        self._apply_asis([new_item])

        item = self.lib.items().get()
        self.assertTrue('differentTitle' in item.path)
        self.assertExists(item.path)

    def test_apply_existing_item_new_metadata_copy_disabled(self):
        # Import *without* copying to ensure that the path does *not* change.
        config['import']['copy'] = False

        self._apply_asis([self.i])
        item = self.lib.items().get()
        new_item = library.Item.from_path(item.path)
        new_item.title = 'differentTitle'
        self._apply_asis([new_item])

        item = self.lib.items().get()
        self.assertFalse('differentTitle' in item.path)
        self.assertExists(item.path)

    def test_apply_existing_item_new_metadata_removes_old_files(self):
        config['import']['copy'] = True

        self._apply_asis([self.i])
        item = self.lib.items().get()
        oldpath = item.path
        new_item = library.Item.from_path(item.path)
        new_item.title = 'differentTitle'
        self._apply_asis([new_item])

        item = self.lib.items().get()
        self.assertNotExists(oldpath)

    def test_apply_existing_item_new_metadata_delete_enabled(self):
        # The "delete" flag should be ignored -- only the "copy" flag
        # controls whether files move.
        config['import']['copy'] = True
        config['import']['delete'] = True  # !

        self._apply_asis([self.i])
        item = self.lib.items().get()
        oldpath = item.path
        new_item = library.Item.from_path(item.path)
        new_item.title = 'differentTitle'
        self._apply_asis([new_item])

        item = self.lib.items().get()
        self.assertNotExists(oldpath)
        self.assertTrue('differentTitle' in item.path)
        self.assertExists(item.path)

    def test_apply_existing_item_preserves_file(self):
        # With copying enabled, import the item twice with same metadata.
        config['import']['copy'] = True

        self._apply_asis([self.i])
        item = self.lib.items().get()
        oldpath = item.path
        new_item = library.Item.from_path(item.path)
        self._apply_asis([new_item])

        self.assertEqual(len(list(self.lib.items())), 1)
        item = self.lib.items().get()
        self.assertEqual(oldpath, item.path)
        self.assertExists(oldpath)

    def test_apply_existing_item_preserves_file_delete_enabled(self):
        config['import']['copy'] = True
        config['import']['delete'] = True  # !

        self._apply_asis([self.i])
        item = self.lib.items().get()
        new_item = library.Item.from_path(item.path)
        self._apply_asis([new_item])

        self.assertEqual(len(list(self.lib.items())), 1)
        item = self.lib.items().get()
        self.assertExists(item.path)

    def test_same_album_does_not_duplicate(self):
        # With the -L flag, exactly the same item (with the same ID)
        # is re-imported. This test simulates that situation.
        self._apply_asis([self.i])
        item = self.lib.items().get()
        self._apply_asis([item])

        # Should not be duplicated.
        self.assertEqual(len(list(self.lib.items())), 1)
        self.assertEqual(len(list(self.lib.albums())), 1)

class InferAlbumDataTest(_common.TestCase):
    def setUp(self):
        super(InferAlbumDataTest, self).setUp()

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

        self.task = importer.ImportTask(paths=['a path'], toppath='top path',
                                        items=self.items)
        self.task.set_null_candidates()

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

    def test_asis_track_albumartist_override(self):
        self.items[0].artist = 'another artist'
        self.items[1].artist = 'some other artist'
        for item in self.items:
            item.albumartist = 'some album artist'
            item.mb_albumartistid = 'some album artist id'
        self.task.set_choice(importer.action.ASIS)

        self._infer()

        self.assertEqual(self.items[0].albumartist,
                         'some album artist')
        self.assertEqual(self.items[0].mb_albumartistid,
                         'some album artist id')

    def test_apply_gets_artist_and_id(self):
        self.task.set_choice(AlbumMatch(0, None, {}, set(), set()))  # APPLY

        self._infer()

        self.assertEqual(self.items[0].albumartist, self.items[0].artist)
        self.assertEqual(self.items[0].mb_albumartistid,
                         self.items[0].mb_artistid)

    def test_apply_lets_album_values_override(self):
        for item in self.items:
            item.albumartist = 'some album artist'
            item.mb_albumartistid = 'some album artist id'
        self.task.set_choice(AlbumMatch(0, None, {}, set(), set()))  # APPLY

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
        self.task.set_choice(AlbumMatch(0, None, {}, set(), set()))  # APPLY
        self._infer()
        self.assertFalse(self.items[1].comp)
        self.assertEqual(self.items[1].albumartist, self.items[2].artist)

class DuplicateCheckTest(_common.TestCase):
    def setUp(self):
        super(DuplicateCheckTest, self).setUp()

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

        task = importer.ImportTask(paths=['a path'], toppath='top path',
                                   items=[item])
        task.set_candidates(artist, album, None, None)
        if asis:
            task.set_choice(importer.action.ASIS)
        else:
            info = AlbumInfo(album, None, artist, None, None)
            task.set_choice(AlbumMatch(0, info, {}, set(), set()))
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
            task.set_choice(TrackMatch(0, TrackInfo(title, None, artist)))
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
        self.album.store()
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

    def test_duplicate_album_existing(self):
        res = importer._duplicate_check(self.lib,
                                        self._album_task(False, existing=True))
        self.assertFalse(res)

    def test_duplicate_item_existing(self):
        res = importer._item_duplicate_check(self.lib,
                                        self._item_task(False, existing=True))
        self.assertFalse(res)

class TagLogTest(_common.TestCase):
    def test_tag_log_line(self):
        sio = StringIO.StringIO()
        session = _common.import_session(logfile=sio)
        session.tag_log('status', 'path')
        assert 'status path' in sio.getvalue()

    def test_tag_log_unicode(self):
        sio = StringIO.StringIO()
        session = _common.import_session(logfile=sio)
        session.tag_log('status', 'caf\xc3\xa9')
        assert 'status caf' in sio.getvalue()

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
