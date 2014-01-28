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
from beets import autotag
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

    def _create_import_dir(self, count=3):
        """Creates a directory with media files to import.
        Sets ``self.import_dir`` to the path of the directory. Also sets
        ``self.import_media`` to a list :class:`MediaFile` for all the files in
        the directory.

        The directory has following layout
          the_album/
            track_1.mp3
            track_2.mp3
            track_3.mp3

        :param count:  Number of files to create
        """
        self.import_dir = os.path.join(self.temp_dir, 'testsrcdir')
        album_path = os.path.join(self.import_dir, 'the_album')
        os.makedirs(album_path)

        resource_path = os.path.join(_common.RSRC, 'full.mp3')

        metadata = {
                     'artist': 'Tag Artist',
                     'album':  'Tag Album',
                     'albumartist':  None,
                     'mb_trackid': None,
                     'mb_albumid': None,
                     'comp': None
                   }
        self.media_files = []
        for i in range(count):
            # Copy files
            medium_path = os.path.join(album_path, 'track_%d.mp3' % (i+1))
            shutil.copy(resource_path, medium_path)
            medium = mediafile.MediaFile(medium_path)

            # Set metadata
            metadata['track'] = i+1
            metadata['title'] = 'Tag Title %d' % (i+1)
            for attr in metadata: setattr(medium, attr, metadata[attr])
            medium.save()
            self.media_files.append(medium)
        self.import_media = self.media_files

    def _setup_import_session(self, import_dir=None,
            delete=False, threaded=False, copy=True,
            singletons=False, move=False, autotag=True):
        config['import']['copy'] = copy
        config['import']['delete'] = delete
        config['import']['threaded'] = threaded
        config['import']['singletons'] = singletons
        config['import']['move'] = move
        config['import']['autotag'] = autotag
        config['import']['resume'] = False

        self.importer = TestImportSession(self.lib,
                                logfile=None,
                                paths=[import_dir or self.import_dir],
                                query=None)

    def _match_album(self, albumartist, album, tracks):
        """Stub for ``mb.match_album``.
        Yields AlbumInfo with ``tracks`` from ``_match_track``
        """
        albumartist = albumartist or 'Various'
        trackInfos = []
        for i in range(tracks):
            trackInfos.append(
                self._match_track(albumartist, u'Tag Title %d' % (i+1)).next())

        yield AlbumInfo(
            artist    = albumartist.replace('Tag', 'Applied'),
            album     = album.replace('Tag', 'Applied'),
            tracks    = trackInfos,
            va        = False,
            album_id  = u'albumid',
            artist_id = u'artistid',
            albumtype = u'soundtrack')

    def _match_track(self, artist, title):
        """Stub for ``mb.match_track``. Yields TrackInfo.
        """
        yield TrackInfo(
            title     = title.replace('Tag', 'Applied'),
            track_id  = u'trackid',
            artist    = artist.replace('Tag', 'Applied'),
            artist_id = u'artistid',
            length    = 1)


    def assert_file_in_lib(self, *segments):
        """Join the ``segments`` and assert that this path exists in the library
        directory
        """
        self.assertExists(os.path.join(self.libdir, *segments))

    def assert_file_not_in_lib(self, *segments):
        """Join the ``segments`` and assert that this path exists in the library
        directory
        """
        self.assertNotExists(os.path.join(self.libdir, *segments))

    def assert_lib_dir_empty(self):
        self.assertEqual(len(os.listdir(self.libdir)), 0)

class TestImportSession(importer.ImportSession):

    choice = None
    item_choice = None

    def choose_match(self, task):
        if self.choice:
            if hasattr(self.choice, 'pop'):
                return self.choice.pop(0)
            else:
                return self.choice
        else:
            return task.candidates[0]

    def choose_item(self, task):
        if self.item_choice:
            return self.item_choice
            if hasattr(self.item_choice, 'pop'):
                return self.item_choice.pop(0)
            else:
                return self.choice
        else:
            return task.candidates[0]

class NonAutotaggedImportTest(_common.TestCase, ImportHelper):
    def setUp(self):
        super(NonAutotaggedImportTest, self).setUp()

        self._setup_library()
        self._create_import_dir(2)
        self._setup_import_session(autotag=False)

    def test_album_created_with_track_artist(self):
        self.importer.run()
        albums = self.lib.albums()
        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0].albumartist, 'Tag Artist')

    def test_import_copy_arrives(self):
        self.importer.run()
        for mediafile in self.import_media:
            self.assert_file_in_lib(
                    'Tag Artist', 'Tag Album', '%s.mp3' % mediafile.title)

    def test_threaded_import_copy_arrives(self):
        config['import']['threaded'] = True

        self.importer.run()
        for mediafile in self.import_media:
            self.assert_file_in_lib(
                    'Tag Artist', 'Tag Album', '%s.mp3' % mediafile.title)

    def test_import_with_move_deletes_import_files(self):
        config['import']['move'] = True

        for mediafile in self.import_media:
            self.assertExists(mediafile.path)
        self.importer.run()
        for mediafile in self.import_media:
            self.assertNotExists(mediafile.path)

    def test_import_with_move_prunes_directory_empty(self):
        config['import']['move'] = True

        self.assertExists(os.path.join(self.import_dir, 'the_album'))
        self.importer.run()
        self.assertNotExists(os.path.join(self.import_dir, 'the_album'))

    def test_import_with_move_prunes_with_extra_clutter(self):
        f = open(os.path.join(self.import_dir, 'the_album', 'alog.log'), 'w')
        f.close()
        config['clutter'] = ['*.log']
        config['import']['move'] = True

        self.assertExists(os.path.join(self.import_dir, 'the_album'))
        self.importer.run()
        self.assertNotExists(os.path.join(self.import_dir, 'the_album'))

    def test_threaded_import_move_arrives(self):
        config['import']['move'] = True
        config['import']['threaded'] = True

        self.importer.run()
        for mediafile in self.import_media:
            self.assert_file_in_lib(
                    'Tag Artist', 'Tag Album', '%s.mp3' % mediafile.title)

    def test_threaded_import_move_deletes_import(self):
        config['import']['move'] = True
        config['import']['threaded'] = True

        self.importer.run()
        for mediafile in self.import_media:
            self.assertNotExists(mediafile.path)

    def test_import_without_delete_retains_files(self):
        config['import']['delete'] = False
        self.importer.run()
        for mediafile in self.import_media:
            self.assertExists(mediafile.path)

    def test_import_with_delete_removes_files(self):
        config['import']['delete'] = True

        self.importer.run()
        for mediafile in self.import_media:
            self.assertNotExists(mediafile.path)

    def test_import_with_delete_prunes_directory_empty(self):
        config['import']['delete'] = True
        self.assertExists(os.path.join(self.import_dir, 'the_album'))
        self.importer.run()
        self.assertNotExists(os.path.join(self.import_dir, 'the_album'))


class ImportTest(_common.TestCase, ImportHelper):
    def setUp(self):
        super(ImportTest, self).setUp()
        self._setup_library()
        self._create_import_dir(1)
        self._setup_import_session()

        autotag.mb.match_album = self._match_album
        autotag.mb.match_track = self._match_track

    def test_apply_asis_adds_album(self):
        self.importer.choice = importer.action.ASIS

        self.assertEqual(self.lib.albums().get(), None)
        self.importer.run()
        self.assertEqual(self.lib.albums().get().album, 'Tag Album')

    def test_apply_asis_adds_tracks(self):
        self.importer.choice = importer.action.ASIS

        self.assertEqual(self.lib.items().get(), None)
        self.importer.run()
        self.assertEqual(self.lib.items().get().title, 'Tag Title 1')

    def test_apply_asis_adds_album_path(self):
        self.importer.choice = importer.action.ASIS

        self.assert_lib_dir_empty()
        self.importer.run()
        self.assert_file_in_lib(
                'Tag Artist', 'Tag Album', 'Tag Title 1.mp3')

    def test_apply_candidate_adds_album(self):
        self.assertEqual(self.lib.albums().get(), None)
        self.importer.run()
        self.assertEqual(self.lib.albums().get().album, 'Applied Album')

    def test_apply_candidate_adds_tracks(self):
        self.assertEqual(self.lib.items().get(), None)
        self.importer.run()
        self.assertEqual(self.lib.items().get().title, 'Applied Title 1')

    def test_apply_candidate_adds_album_path(self):
        self.assert_lib_dir_empty()
        self.importer.run()
        self.assert_file_in_lib(
                'Applied Artist', 'Applied Album', 'Applied Title 1.mp3')

    def test_apply_with_move_deletes_import(self):
        config['import']['move'] = True

        import_file = os.path.join(self.import_dir, 'the_album', 'track_1.mp3')
        self.assertExists(import_file)
        self.importer.run()
        self.assertNotExists(import_file)

    def test_apply_with_delete_deletes_import(self):
        config['import']['delete'] = True

        import_file = os.path.join(self.import_dir, 'the_album', 'track_1.mp3')
        self.assertExists(import_file)
        self.importer.run()
        self.assertNotExists(import_file)

    def test_apply_tracks_adds_singleton(self):
        self.importer.choice = importer.action.TRACKS

        self.assertEqual(self.lib.items().get(), None)
        self.assertEqual(self.lib.albums().get(), None)
        self.importer.run()
        self.assertEqual(self.lib.items().get().title, 'Applied Title 1')
        self.assertEqual(self.lib.albums().get(), None)

    def test_apply_tracks_adds_singleton_path(self):
        self.importer.choice = importer.action.TRACKS

        self.assert_lib_dir_empty()
        self.importer.run()
        self.assert_file_in_lib('singletons', 'Applied Title 1.mp3')

class ImportCompilationTest(_common.TestCase, ImportHelper):
    def setUp(self):
        super(ImportCompilationTest, self).setUp()
        self._setup_library()
        self._create_import_dir(3)
        self._setup_import_session()

        autotag.mb.match_album = self._match_album
        autotag.mb.match_track = self._match_track

    def test_asis_homogenous_sets_albumartist(self):
        self.importer.choice = importer.action.ASIS

        self.importer.run()
        self.assertEqual(self.lib.albums().get().albumartist, 'Tag Artist')
        for item in self.lib.items():
            self.assertEqual(item.albumartist, 'Tag Artist')

    def test_asis_heterogenous_sets_various_albumartist(self):
        self.importer.choice = importer.action.ASIS

        self.import_media[0].artist = 'Other Artist'
        self.import_media[0].save()
        self.import_media[1].artist = 'Another Artist'
        self.import_media[1].save()

        self.importer.run()
        self.assertEqual(self.lib.albums().get().albumartist, 'Various Artists')
        for item in self.lib.items():
            self.assertEqual(item.albumartist, 'Various Artists')

    def test_asis_heterogenous_sets_sompilation(self):
        self.importer.choice = importer.action.ASIS

        self.import_media[0].artist = 'Other Artist'
        self.import_media[0].save()
        self.import_media[1].artist = 'Another Artist'
        self.import_media[1].save()

        self.importer.run()
        for item in self.lib.items():
            self.assertTrue(item.comp)

    def test_asis_sets_majority_albumartist(self):
        self.importer.choice = importer.action.ASIS

        self.import_media[0].artist = 'Other Artist'
        self.import_media[0].save()
        self.import_media[1].artist = 'Other Artist'
        self.import_media[1].save()

        self.importer.run()
        self.assertEqual(self.lib.albums().get().albumartist, 'Other Artist')
        for item in self.lib.items():
            self.assertEqual(item.albumartist, 'Other Artist')

    def test_asis_albumartist_tag_sets_albumartist(self):
        self.importer.choice = importer.action.ASIS

        self.import_media[0].artist = 'Other Artist'
        self.import_media[1].artist = 'Another Artist'
        for mediafile in self.import_media:
            mediafile.albumartist = 'Album Artist'
            mediafile.mb_albumartistid = 'Album Artist ID'
            mediafile.save()

        self.importer.run()
        self.assertEqual(self.lib.albums().get().albumartist, 'Album Artist')
        self.assertEqual(self.lib.albums().get().mb_albumartistid,
                'Album Artist ID')
        for item in self.lib.items():
            self.assertEqual(item.albumartist, 'Album Artist')
            self.assertEqual(item.mb_albumartistid, 'Album Artist ID')


class ImportExistingTest(_common.TestCase, ImportHelper):
    def setUp(self):
        super(ImportExistingTest, self).setUp()
        self._setup_library()
        self._create_import_dir(1)

        autotag.mb.match_album = self._match_album
        autotag.mb.match_track = self._match_track

        config['import']['delete'] = True
        self._setup_import_session(copy=True)
        self.setup_importer = self.importer

        self._setup_import_session(import_dir=self.libdir)

    def test_does_not_duplicate_item(self):
        self.setup_importer.run()
        self.assertEqual(len((self.lib.items())), 1)
        self.importer.run()
        self.assertEqual(len((self.lib.items())), 1)

    def test_does_not_duplicate_album(self):
        self.setup_importer.run()
        self.assertEqual(len((self.lib.albums())), 1)
        self.importer.run()
        self.assertEqual(len((self.lib.albums())), 1)

    def test_does_not_duplicate_singleton_track(self):
        self.setup_importer.choice = \
              self.importer.choice = importer.action.TRACKS

        self.setup_importer.run()
        self.assertEqual(len((self.lib.items())), 1)
        self.importer.run()
        self.assertEqual(len((self.lib.items())), 1)

    def test_asis_updates_metadata(self):
        self.setup_importer.run()
        medium = mediafile.MediaFile(self.lib.items().get().path)
        medium.title = 'New Title'
        medium.save()

        self.importer.choice = importer.action.ASIS
        self.importer.run()
        self.assertEqual(self.lib.items().get().title, 'New Title')

    def test_asis_updated_moves_file(self):
        self.setup_importer.run()
        medium = mediafile.MediaFile(self.lib.items().get().path)
        medium.title = 'New Title'
        medium.save()

        old_path = os.path.join(
                'Applied Artist', 'Applied Album', 'Applied Title 1.mp3')
        self.assert_file_in_lib(old_path)

        self.importer.choice = importer.action.ASIS
        self.importer.run()
        self.assert_file_in_lib('Applied Artist', 'Applied Album', 'New Title.mp3')
        self.assert_file_not_in_lib(old_path)

    def test_asis_updated_without_copy_does_not_move_file(self):
        self.setup_importer.run()
        medium = mediafile.MediaFile(self.lib.items().get().path)
        medium.title = 'New Title'
        medium.save()

        old_path = os.path.join(
                'Applied Artist', 'Applied Album', 'Applied Title 1.mp3')
        self.assert_file_in_lib(old_path)

        config['import']['copy'] = False
        self.importer.choice = importer.action.ASIS
        self.importer.run()
        self.assert_file_not_in_lib('Applied Artist', 'Applied Album', 'New Title.mp3')
        self.assert_file_in_lib(old_path)

    def test_outside_file_is_copied(self):
        config['import']['copy'] = False
        self.setup_importer.run()
        self.assertEqual(self.lib.items().get().path, self.import_media[0].path)

        config['import']['copy'] = True
        self._setup_import_session()
        self.importer.run()
        new_path = os.path.join(
                'Applied Artist', 'Applied Album', 'Applied Title 1.mp3')

        self.assert_file_in_lib(new_path)
        self.assertEqual(self.lib.items().get().path,
                os.path.join(self.libdir,new_path))

    def test_outside_file_is_moved(self):
        config['import']['copy'] = False
        self.setup_importer.run()
        self.assertEqual(self.lib.items().get().path, self.import_media[0].path)

        self._setup_import_session()
        config['import']['move'] = True
        self.importer.run()
        self.assertNotExists(self.import_media[0].path)

class ImportFlatAlbumTest(_common.TestCase, ImportHelper):
    def setUp(self):
        super(ImportFlatAlbumTest, self).setUp()
        self._setup_library()
        self._create_import_dir(3)

        autotag.mb.match_album = self._match_album
        autotag.mb.match_track = self._match_track

        self._setup_import_session(copy=True)

        self.importer.choice = [
                importer.action.ALBUMS,
                importer.action.ASIS,
                importer.action.ASIS]

    def test_add_album_for_different_artist_and_different_album(self):
        self.import_media[0].artist = "Artist B"
        self.import_media[0].album  = "Album B"
        self.import_media[0].save()

        self.importer.run()
        albums = set([album.album for album in self.lib.albums()])
        self.assertEqual(albums, set(['Album B', 'Tag Album']))

    def test_add_album_for_different_artist_and_same_albumartist(self):
        self.import_media[0].artist = "Artist B"
        self.import_media[0].albumartist = "Album Artist"
        self.import_media[0].save()
        self.import_media[1].artist = "Artist C"
        self.import_media[1].albumartist = "Album Artist"
        self.import_media[1].save()

        self.importer.run()
        artists = set([album.albumartist for album in self.lib.albums()])
        self.assertEqual(artists, set(['Album Artist', 'Tag Artist']))

    def test_add_album_for_same_artist_and_different_album(self):
        self.import_media[0].album  = "Album B"
        self.import_media[0].save()

        self.importer.run()
        albums = set([album.album for album in self.lib.albums()])
        self.assertEqual(albums, set(['Album B', 'Tag Album']))

    def test_add_album_for_same_album_and_different_artist(self):
        self.import_media[0].artist  = "Artist B"
        self.import_media[0].save()

        self.importer.run()
        artists = set([album.albumartist for album in self.lib.albums()])
        self.assertEqual(artists, set(['Artist B', 'Tag Artist']))

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
