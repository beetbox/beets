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
from tempfile import mkstemp
from zipfile import ZipFile
from tarfile import TarFile
from mock import patch

import _common
from _common import unittest
from helper import TestImportSession, TestHelper, has_program
from beets import importer
from beets.mediafile import MediaFile
from beets import autotag
from beets.autotag import AlbumInfo, TrackInfo, AlbumMatch
from beets import config


class AutotagStub(object):
    """Stub out MusicBrainz album and track matcher and control what the
    autotagger returns.
    """

    NONE   = 'NONE'
    IDENT  = 'IDENT'
    GOOD   = 'GOOD'
    BAD    = 'BAD'

    length = 2
    matching = IDENT

    def install(self):
        self.mb_match_album = autotag.mb.match_album
        self.mb_match_track = autotag.mb.match_track

        autotag.mb.match_album = self.match_album
        autotag.mb.match_track = self.match_track

        return self

    def restore(self):
        autotag.mb.match_album = self.mb_match_album
        autotag.mb.match_track = self.mb_match_album

    def match_album(self, albumartist, album, tracks):
        if self.matching == self.IDENT:
            yield self._make_album_match(albumartist, album, tracks)

        elif self.matching == self.GOOD:
            for i in range(self.length):
                yield self._make_album_match(albumartist, album, tracks, i)

        elif self.matching == self.BAD:
            for i in range(self.length):
                yield self._make_album_match(albumartist, album, tracks, i + 1)

    def match_track(self, artist, title):
        yield TrackInfo(
            title=title.replace('Tag', 'Applied'),
            track_id=u'trackid',
            artist=artist.replace('Tag', 'Applied'),
            artist_id=u'artistid',
            length=1
        )

    def _make_track_match(self, artist, album, number):
        return TrackInfo(
            title=u'Applied Title %d' % number,
            track_id=u'match %d' % number,
            artist=artist,
            length=1
        )

    def _make_album_match(self, artist, album, tracks, distance=0):
        if distance:
            id = ' ' + 'M' * distance
        else:
            id = ''
        if artist is None:
            artist = "Various Artists"
        else:
            artist = artist.replace('Tag', 'Applied') + id
        album = album.replace('Tag', 'Applied') + id

        trackInfos = []
        for i in range(tracks):
            trackInfos.append(self._make_track_match(artist, album, i + 1))

        return AlbumInfo(
            artist=artist,
            album=album,
            tracks=trackInfos,
            va=False,
            album_id=u'albumid' + id,
            artist_id=u'artistid' + id,
            albumtype=u'soundtrack'
        )


class ImportHelper(TestHelper):
    """Provides tools to setup a library, a directory containing files that are
    to be imported and an import session. The class also provides stubs for the
    autotagging library and several assertions for the library.
    """

    def setup_beets(self, disk=False):
        super(ImportHelper, self).setup_beets(disk)
        self.lib.path_formats = [
            ('default', os.path.join('$artist', '$album', '$title')),
            ('singleton:true', os.path.join('singletons', '$title')),
            ('comp:true', os.path.join('compilations', '$album', '$title')),
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
        if os.path.isdir(self.import_dir):
            shutil.rmtree(self.import_dir)

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
            medium_path = os.path.join(album_path, 'track_%d.mp3' % (i + 1))
            shutil.copy(resource_path, medium_path)
            medium = MediaFile(medium_path)

            # Set metadata
            metadata['track'] = i + 1
            metadata['title'] = 'Tag Title %d' % (i + 1)
            for attr in metadata:
                setattr(medium, attr, metadata[attr])
            medium.save()
            self.media_files.append(medium)
        self.import_media = self.media_files

    def _setup_import_session(self, import_dir=None, delete=False,
                              threaded=False, copy=True, singletons=False,
                              move=False, autotag=True):
        config['import']['copy'] = copy
        config['import']['delete'] = delete
        config['import']['timid'] = True
        config['threaded'] = False
        config['import']['singletons'] = singletons
        config['import']['move'] = move
        config['import']['autotag'] = autotag
        config['import']['resume'] = False

        self.importer = TestImportSession(
            self.lib, logfile=None, query=None,
            paths=[import_dir or self.import_dir]
        )

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


class NonAutotaggedImportTest(_common.TestCase, ImportHelper):
    def setUp(self):
        self.setup_beets(disk=True)
        self._create_import_dir(2)
        self._setup_import_session(autotag=False)

    def tearDown(self):
        self.teardown_beets()

    def test_album_created_with_track_artist(self):
        self.importer.run()
        albums = self.lib.albums()
        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0].albumartist, 'Tag Artist')

    def test_import_copy_arrives(self):
        self.importer.run()
        for mediafile in self.import_media:
            self.assert_file_in_lib(
                'Tag Artist', 'Tag Album', '%s.mp3' % mediafile.title
            )

    def test_threaded_import_copy_arrives(self):
        config['threaded'] = True

        self.importer.run()
        for mediafile in self.import_media:
            self.assert_file_in_lib(
                'Tag Artist', 'Tag Album', '%s.mp3' % mediafile.title
            )

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
                'Tag Artist', 'Tag Album', '%s.mp3' % mediafile.title
            )

    def test_threaded_import_move_deletes_import(self):
        config['import']['move'] = True
        config['threaded'] = True

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


class ImportZipTest(unittest.TestCase, ImportHelper):

    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.teardown_beets()

    def test_import_zip(self):
        zip_path = self.create_archive()
        self.assertEqual(len(self.lib.items()), 0)
        self.assertEqual(len(self.lib.albums()), 0)

        self._setup_import_session(autotag=False, import_dir=zip_path)
        self.importer.run()
        self.assertEqual(len(self.lib.items()), 1)
        self.assertEqual(len(self.lib.albums()), 1)

    def create_archive(self):
        (handle, path) = mkstemp(dir=self.temp_dir)
        os.close(handle)
        archive = ZipFile(path, mode='w')
        archive.write(os.path.join(_common.RSRC, 'full.mp3'),
                      'full.mp3')
        archive.close()
        return path


class ImportTarTest(ImportZipTest):

    def create_archive(self):
        (handle, path) = mkstemp(dir=self.temp_dir)
        os.close(handle)
        archive = TarFile(path, mode='w')
        archive.add(os.path.join(_common.RSRC, 'full.mp3'),
                    'full.mp3')
        archive.close()
        return path


@unittest.skipIf(not has_program('unrar'), 'unrar program not found')
class ImportRarTest(ImportZipTest):

    def create_archive(self):
        return os.path.join(_common.RSRC, 'archive.rar')


@unittest.skip('Implment me!')
class ImportPasswordRarTest(ImportZipTest):

    def create_archive(self):
        return os.path.join(_common.RSRC, 'password.rar')


class ImportSingletonTest(_common.TestCase, ImportHelper):
    """Test ``APPLY`` and ``ASIS`` choices for an import session with singletons
    config set to True.
    """

    def setUp(self):
        self.setup_beets()
        self._create_import_dir(1)
        self._setup_import_session()
        config['import']['singletons'] = True
        self.matcher = AutotagStub().install()

    def tearDown(self):
        self.teardown_beets()
        self.matcher.restore()

    def test_apply_asis_adds_track(self):
        self.assertEqual(self.lib.items().get(), None)

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assertEqual(self.lib.items().get().title, 'Tag Title 1')

    def test_apply_asis_does_not_add_album(self):
        self.assertEqual(self.lib.albums().get(), None)

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assertEqual(self.lib.albums().get(), None)

    def test_apply_asis_adds_singleton_path(self):
        self.assert_lib_dir_empty()

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assert_file_in_lib('singletons', 'Tag Title 1.mp3')

    def test_apply_candidate_adds_track(self):
        self.assertEqual(self.lib.items().get(), None)

        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertEqual(self.lib.items().get().title, 'Applied Title 1')

    def test_apply_candidate_does_not_add_album(self):
        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertEqual(self.lib.albums().get(), None)

    def test_apply_candidate_adds_singleton_path(self):
        self.assert_lib_dir_empty()

        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assert_file_in_lib('singletons', 'Applied Title 1.mp3')

    def test_skip_does_not_add_first_track(self):
        self.importer.add_choice(importer.action.SKIP)
        self.importer.run()
        self.assertEqual(self.lib.items().get(), None)

    def test_skip_adds_other_tracks(self):
        self._create_import_dir(2)
        self.importer.add_choice(importer.action.SKIP)
        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assertEqual(len(self.lib.items()), 1)

    def test_import_single_files(self):
        resource_path = os.path.join(_common.RSRC, u'empty.mp3')
        single_path = os.path.join(self.import_dir, u'track_2.mp3')

        shutil.copy(resource_path, single_path)
        import_files = [
            os.path.join(self.import_dir, u'the_album'),
            single_path
        ]
        self._setup_import_session(singletons=False)
        self.importer.paths = import_files

        self.importer.add_choice(importer.action.ASIS)
        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()

        self.assertEqual(len(self.lib.items()), 2)
        self.assertEqual(len(self.lib.albums()), 2)


class ImportTest(_common.TestCase, ImportHelper):
    """Test APPLY, ASIS and SKIP choices.
    """
    def setUp(self):
        self.setup_beets()
        self._create_import_dir(1)
        self._setup_import_session()
        self.matcher = AutotagStub().install()
        self.matcher.macthin = AutotagStub.GOOD

    def tearDown(self):
        self.teardown_beets()
        self.matcher.restore()

    def test_apply_asis_adds_album(self):
        self.assertEqual(self.lib.albums().get(), None)

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assertEqual(self.lib.albums().get().album, 'Tag Album')

    def test_apply_asis_adds_tracks(self):
        self.assertEqual(self.lib.items().get(), None)
        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assertEqual(self.lib.items().get().title, 'Tag Title 1')

    def test_apply_asis_adds_album_path(self):
        self.assert_lib_dir_empty()

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assert_file_in_lib('Tag Artist', 'Tag Album', 'Tag Title 1.mp3')

    def test_apply_candidate_adds_album(self):
        self.assertEqual(self.lib.albums().get(), None)

        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertEqual(self.lib.albums().get().album, 'Applied Album')

    def test_apply_candidate_adds_tracks(self):
        self.assertEqual(self.lib.items().get(), None)

        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertEqual(self.lib.items().get().title, 'Applied Title 1')

    def test_apply_candidate_adds_album_path(self):
        self.assert_lib_dir_empty()

        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assert_file_in_lib(
            'Applied Artist', 'Applied Album', 'Applied Title 1.mp3'
        )

    def test_apply_with_move_deletes_import(self):
        config['import']['move'] = True

        import_file = os.path.join(self.import_dir, 'the_album', 'track_1.mp3')
        self.assertExists(import_file)

        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertNotExists(import_file)

    def test_apply_with_delete_deletes_import(self):
        config['import']['delete'] = True

        import_file = os.path.join(self.import_dir, 'the_album', 'track_1.mp3')
        self.assertExists(import_file)

        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertNotExists(import_file)

    def test_skip_does_not_add_track(self):
        self.importer.add_choice(importer.action.SKIP)
        self.importer.run()
        self.assertEqual(self.lib.items().get(), None)


class ImportTracksTest(_common.TestCase, ImportHelper):
    """Test TRACKS and APPLY choice.
    """
    def setUp(self):
        self.setup_beets()
        self._create_import_dir(1)
        self._setup_import_session()
        self.matcher = AutotagStub().install()

    def tearDown(self):
        self.teardown_beets()
        self.matcher.restore()

    def test_apply_tracks_adds_singleton_track(self):
        self.assertEqual(self.lib.items().get(), None)
        self.assertEqual(self.lib.albums().get(), None)

        self.importer.add_choice(importer.action.TRACKS)
        self.importer.add_choice(importer.action.APPLY)
        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertEqual(self.lib.items().get().title, 'Applied Title 1')
        self.assertEqual(self.lib.albums().get(), None)

    def test_apply_tracks_adds_singleton_path(self):
        self.assert_lib_dir_empty()

        self.importer.add_choice(importer.action.TRACKS)
        self.importer.add_choice(importer.action.APPLY)
        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assert_file_in_lib('singletons', 'Applied Title 1.mp3')


class ImportCompilationTest(_common.TestCase, ImportHelper):
    """Test ASIS import of a folder containing tracks with different artists.
    """
    def setUp(self):
        self.setup_beets()
        self._create_import_dir(3)
        self._setup_import_session()
        self.matcher = AutotagStub().install()

    def tearDown(self):
        self.teardown_beets()
        self.matcher.restore()

    def test_asis_homogenous_sets_albumartist(self):
        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assertEqual(self.lib.albums().get().albumartist, 'Tag Artist')
        for item in self.lib.items():
            self.assertEqual(item.albumartist, 'Tag Artist')

    def test_asis_heterogenous_sets_various_albumartist(self):
        self.import_media[0].artist = 'Other Artist'
        self.import_media[0].save()
        self.import_media[1].artist = 'Another Artist'
        self.import_media[1].save()

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assertEqual(self.lib.albums().get().albumartist,
                         'Various Artists')
        for item in self.lib.items():
            self.assertEqual(item.albumartist, 'Various Artists')

    def test_asis_heterogenous_sets_sompilation(self):
        self.import_media[0].artist = 'Other Artist'
        self.import_media[0].save()
        self.import_media[1].artist = 'Another Artist'
        self.import_media[1].save()

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        for item in self.lib.items():
            self.assertTrue(item.comp)

    def test_asis_sets_majority_albumartist(self):
        self.import_media[0].artist = 'Other Artist'
        self.import_media[0].save()
        self.import_media[1].artist = 'Other Artist'
        self.import_media[1].save()

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assertEqual(self.lib.albums().get().albumartist, 'Other Artist')
        for item in self.lib.items():
            self.assertEqual(item.albumartist, 'Other Artist')

    def test_asis_albumartist_tag_sets_albumartist(self):
        self.import_media[0].artist = 'Other Artist'
        self.import_media[1].artist = 'Another Artist'
        for mediafile in self.import_media:
            mediafile.albumartist = 'Album Artist'
            mediafile.mb_albumartistid = 'Album Artist ID'
            mediafile.save()

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assertEqual(self.lib.albums().get().albumartist, 'Album Artist')
        self.assertEqual(self.lib.albums().get().mb_albumartistid,
                         'Album Artist ID')
        for item in self.lib.items():
            self.assertEqual(item.albumartist, 'Album Artist')
            self.assertEqual(item.mb_albumartistid, 'Album Artist ID')


class ImportExistingTest(_common.TestCase, ImportHelper):
    """Test importing files that are already in the library directory.
    """
    def setUp(self):
        self.setup_beets()
        self._create_import_dir(1)
        self.matcher = AutotagStub().install()

        self._setup_import_session()
        self.setup_importer = self.importer
        self.setup_importer.default_choice = importer.action.APPLY

        self._setup_import_session(import_dir=self.libdir)

    def tearDown(self):
        self.teardown_beets()
        self.matcher.restore()

    def test_does_not_duplicate_item(self):
        self.setup_importer.run()
        self.assertEqual(len((self.lib.items())), 1)

        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertEqual(len((self.lib.items())), 1)

    def test_does_not_duplicate_album(self):
        self.setup_importer.run()
        self.assertEqual(len((self.lib.albums())), 1)

        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertEqual(len((self.lib.albums())), 1)

    def test_does_not_duplicate_singleton_track(self):
        self.setup_importer.add_choice(importer.action.TRACKS)
        self.setup_importer.add_choice(importer.action.APPLY)
        self.setup_importer.run()
        self.assertEqual(len((self.lib.items())), 1)

        self.importer.add_choice(importer.action.TRACKS)
        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertEqual(len((self.lib.items())), 1)

    def test_asis_updates_metadata(self):
        self.setup_importer.run()
        medium = MediaFile(self.lib.items().get().path)
        medium.title = 'New Title'
        medium.save()

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assertEqual(self.lib.items().get().title, 'New Title')

    def test_asis_updated_moves_file(self):
        self.setup_importer.run()
        medium = MediaFile(self.lib.items().get().path)
        medium.title = 'New Title'
        medium.save()

        old_path = os.path.join('Applied Artist', 'Applied Album',
                                'Applied Title 1.mp3')
        self.assert_file_in_lib(old_path)

        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assert_file_in_lib('Applied Artist', 'Applied Album',
                                'New Title.mp3')
        self.assert_file_not_in_lib(old_path)

    def test_asis_updated_without_copy_does_not_move_file(self):
        self.setup_importer.run()
        medium = MediaFile(self.lib.items().get().path)
        medium.title = 'New Title'
        medium.save()

        old_path = os.path.join('Applied Artist', 'Applied Album',
                                'Applied Title 1.mp3')
        self.assert_file_in_lib(old_path)

        config['import']['copy'] = False
        self.importer.add_choice(importer.action.ASIS)
        self.importer.run()
        self.assert_file_not_in_lib('Applied Artist', 'Applied Album',
                                    'New Title.mp3')
        self.assert_file_in_lib(old_path)

    def test_outside_file_is_copied(self):
        config['import']['copy'] = False
        self.setup_importer.run()
        self.assertEqual(self.lib.items().get().path,
                         self.import_media[0].path)

        config['import']['copy'] = True
        self._setup_import_session()
        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        new_path = os.path.join('Applied Artist', 'Applied Album',
                                'Applied Title 1.mp3')

        self.assert_file_in_lib(new_path)
        self.assertEqual(self.lib.items().get().path,
                         os.path.join(self.libdir, new_path))

    def test_outside_file_is_moved(self):
        config['import']['copy'] = False
        self.setup_importer.run()
        self.assertEqual(self.lib.items().get().path,
                         self.import_media[0].path)

        self._setup_import_session(move=True)
        self.importer.add_choice(importer.action.APPLY)
        self.importer.run()
        self.assertNotExists(self.import_media[0].path)


class GroupAlbumsImportTest(_common.TestCase, ImportHelper):
    def setUp(self):
        self.setup_beets()
        self._create_import_dir(3)
        self.matcher = AutotagStub().install()
        self.matcher.matching = AutotagStub.NONE
        self._setup_import_session()

        # Split tracks into two albums and use both as-is
        self.importer.add_choice(importer.action.ALBUMS)
        self.importer.add_choice(importer.action.ASIS)
        self.importer.add_choice(importer.action.ASIS)

    def tearDown(self):
        self.teardown_beets()
        self.matcher.restore()

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

    def test_incremental(self):
        config['import']['incremental'] = True
        self.import_media[0].album  = "Album B"
        self.import_media[0].save()

        self.importer.run()
        albums = set([album.album for album in self.lib.albums()])
        self.assertEqual(albums, set(['Album B', 'Tag Album']))


class GlobalGroupAlbumsImportTest(GroupAlbumsImportTest):

    def setUp(self):
        super(GlobalGroupAlbumsImportTest, self).setUp()
        self.importer.clear_choices()
        self.importer.default_choice = importer.action.ASIS
        config['import']['group_albums'] = True


class ChooseCandidateTest(_common.TestCase, ImportHelper):
    def setUp(self):
        self.setup_beets()
        self._create_import_dir(1)
        self._setup_import_session()
        self.matcher = AutotagStub().install()
        self.matcher.matching = AutotagStub.BAD

    def tearDown(self):
        self.teardown_beets()
        self.matcher.restore()

    def test_choose_first_candidate(self):
        self.importer.add_choice(1)
        self.importer.run()
        self.assertEqual(self.lib.albums().get().album, 'Applied Album M')

    def test_choose_second_candidate(self):
        self.importer.add_choice(2)
        self.importer.run()
        self.assertEqual(self.lib.albums().get().album, 'Applied Album MM')


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

    def test_asis_homogenous_single_artist(self):
        self.task.set_choice(importer.action.ASIS)
        self.task.infer_album_fields()
        self.assertFalse(self.items[0].comp)
        self.assertEqual(self.items[0].albumartist, self.items[2].artist)

    def test_asis_heterogenous_va(self):
        self.items[0].artist = 'another artist'
        self.items[1].artist = 'some other artist'
        self.task.set_choice(importer.action.ASIS)

        self.task.infer_album_fields()

        self.assertTrue(self.items[0].comp)
        self.assertEqual(self.items[0].albumartist, 'Various Artists')

    def test_asis_comp_applied_to_all_items(self):
        self.items[0].artist = 'another artist'
        self.items[1].artist = 'some other artist'
        self.task.set_choice(importer.action.ASIS)

        self.task.infer_album_fields()

        for item in self.items:
            self.assertTrue(item.comp)
            self.assertEqual(item.albumartist, 'Various Artists')

    def test_asis_majority_artist_single_artist(self):
        self.items[0].artist = 'another artist'
        self.task.set_choice(importer.action.ASIS)

        self.task.infer_album_fields()

        self.assertFalse(self.items[0].comp)
        self.assertEqual(self.items[0].albumartist, self.items[2].artist)

    def test_asis_track_albumartist_override(self):
        self.items[0].artist = 'another artist'
        self.items[1].artist = 'some other artist'
        for item in self.items:
            item.albumartist = 'some album artist'
            item.mb_albumartistid = 'some album artist id'
        self.task.set_choice(importer.action.ASIS)

        self.task.infer_album_fields()

        self.assertEqual(self.items[0].albumartist,
                         'some album artist')
        self.assertEqual(self.items[0].mb_albumartistid,
                         'some album artist id')

    def test_apply_gets_artist_and_id(self):
        self.task.set_choice(AlbumMatch(0, None, {}, set(), set()))  # APPLY

        self.task.infer_album_fields()

        self.assertEqual(self.items[0].albumartist, self.items[0].artist)
        self.assertEqual(self.items[0].mb_albumartistid,
                         self.items[0].mb_artistid)

    def test_apply_lets_album_values_override(self):
        for item in self.items:
            item.albumartist = 'some album artist'
            item.mb_albumartistid = 'some album artist id'
        self.task.set_choice(AlbumMatch(0, None, {}, set(), set()))  # APPLY

        self.task.infer_album_fields()

        self.assertEqual(self.items[0].albumartist,
                         'some album artist')
        self.assertEqual(self.items[0].mb_albumartistid,
                         'some album artist id')

    def test_small_single_artist_album(self):
        self.items = [self.items[0]]
        self.task.items = self.items
        self.task.set_choice(importer.action.ASIS)
        self.task.infer_album_fields()
        self.assertFalse(self.items[0].comp)


class ImportDuplicateAlbumTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()

        # Original album
        self.add_album_fixture(albumartist=u'artist', album=u'album')

        # Create duplicate through autotagger
        self.match_album_patcher = patch('beets.autotag.mb.match_album')
        self.match_album = self.match_album_patcher.start()
        track_info = TrackInfo(
            title=u'new title',
            track_id=u'trackid',
        )
        album_info = AlbumInfo(
            artist=u'artist',
            album=u'album',
            tracks=[track_info],
            album_id=u'albumid',
            artist_id=u'artistid',
        )
        self.match_album.return_value = iter([album_info])

        # Create import session
        self.importer = self.create_importer()
        config['import']['autotag'] = True

    def tearDown(self):
        self.match_album_patcher.stop()
        self.teardown_beets()

    def test_remove_duplicate_album(self):
        item = self.lib.items().get()
        self.assertEqual(item.title, u't\xeftle 0')
        self.assertTrue(os.path.isfile(item.path))

        self.importer.default_resolution = self.importer.Resolution.REMOVE
        self.importer.run()

        self.assertFalse(os.path.isfile(item.path))
        self.assertEqual(len(self.lib.albums()), 1)
        self.assertEqual(len(self.lib.items()), 1)
        item = self.lib.items().get()
        self.assertEqual(item.title, u'new title')

    def test_keep_duplicate_album(self):
        self.importer.default_resolution = self.importer.Resolution.KEEPBOTH
        self.importer.run()

        self.assertEqual(len(self.lib.albums()), 2)
        self.assertEqual(len(self.lib.items()), 2)

    def test_skip_duplicate_album(self):
        item = self.lib.items().get()
        self.assertEqual(item.title, u't\xeftle 0')

        self.importer.default_resolution = self.importer.Resolution.SKIP
        self.importer.run()

        self.assertEqual(len(self.lib.albums()), 1)
        self.assertEqual(len(self.lib.items()), 1)
        item = self.lib.items().get()
        self.assertEqual(item.title, u't\xeftle 0')

    def test_twice_in_import_dir(self):
        self.skipTest('write me')

    def add_album_fixture(self, **kwargs):
        # TODO move this into upstream
        album = super(ImportDuplicateAlbumTest, self).add_album_fixture()
        album.update(kwargs)
        album.store()
        return album


class ImportDuplicateSingletonTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()

        # Original file in library
        self.add_item_fixture(artist=u'artist', title=u'title',
                              mb_trackid='old trackid')

        # Create duplicate through autotagger
        self.match_track_patcher = patch('beets.autotag.mb.match_track')
        self.match_track = self.match_track_patcher.start()
        track_info = TrackInfo(
            artist=u'artist',
            title=u'title',
            track_id=u'new trackid',
        )
        self.match_track.return_value = iter([track_info])

        # Import session
        self.importer = self.create_importer()
        config['import']['autotag'] = True
        config['import']['singletons'] = True

    def tearDown(self):
        self.match_track_patcher.stop()
        self.teardown_beets()

    def test_remove_duplicate(self):
        item = self.lib.items().get()
        self.assertEqual(item.mb_trackid, u'old trackid')
        self.assertTrue(os.path.isfile(item.path))

        self.importer.default_resolution = self.importer.Resolution.REMOVE
        self.importer.run()

        self.assertFalse(os.path.isfile(item.path))
        self.assertEqual(len(self.lib.items()), 1)
        item = self.lib.items().get()
        self.assertEqual(item.mb_trackid, u'new trackid')

    def test_keep_duplicate(self):
        self.assertEqual(len(self.lib.items()), 1)

        self.importer.default_resolution = self.importer.Resolution.KEEPBOTH
        self.importer.run()

        self.assertEqual(len(self.lib.items()), 2)

    def test_skip_duplicate(self):
        item = self.lib.items().get()
        self.assertEqual(item.mb_trackid, u'old trackid')

        self.importer.default_resolution = self.importer.Resolution.SKIP
        self.importer.run()

        self.assertEqual(len(self.lib.items()), 1)
        item = self.lib.items().get()
        self.assertEqual(item.mb_trackid, u'old trackid')

    def test_twice_in_import_dir(self):
        self.skipTest('write me')

    def add_item_fixture(self, **kwargs):
        # Move this to TestHelper
        item = self.add_item_fixtures()[0]
        item.update(kwargs)
        item.store()
        return item


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


class ResumeImportTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()

    def tearDown(self):
        self.teardown_beets()

    @patch('beets.plugins.send')
    def test_resume_album(self, plugins_send):
        self.importer = self.create_importer(album_count=2)
        self.config['import']['resume'] = True

        # Aborts import after one album. This also ensures that we skip
        # the first album in the second try.
        def raise_exception(event, **kwargs):
            if event == 'album_imported':
                raise importer.ImportAbort
        plugins_send.side_effect = raise_exception

        self.importer.run()
        self.assertEqual(len(self.lib.albums()), 1)
        self.assertIsNotNone(self.lib.albums('album:album 0').get())

        self.importer.run()
        self.assertEqual(len(self.lib.albums()), 2)
        self.assertIsNotNone(self.lib.albums('album:album 1').get())

    @patch('beets.plugins.send')
    def test_resume_singleton(self, plugins_send):
        self.importer = self.create_importer(item_count=2)
        self.config['import']['resume'] = True
        self.config['import']['singletons'] = True

        # Aborts import after one track. This also ensures that we skip
        # the first album in the second try.
        def raise_exception(event, **kwargs):
            if event == 'item_imported':
                raise importer.ImportAbort
        plugins_send.side_effect = raise_exception

        self.importer.run()
        self.assertEqual(len(self.lib.items()), 1)
        self.assertIsNotNone(self.lib.items('title:track 0').get())

        self.importer.run()
        self.assertEqual(len(self.lib.items()), 2)
        self.assertIsNotNone(self.lib.items('title:track 1').get())


class IncrementalImportTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.config['import']['incremental'] = True

    def tearDown(self):
        self.teardown_beets()

    def test_incremental_album(self):
        importer = self.create_importer(album_count=1)
        importer.run()

        # Change album name so the original file would be imported again
        # if incremental was off.
        album = self.lib.albums().get()
        album['album'] = 'edited album'
        album.store()

        importer = self.create_importer(album_count=1)
        importer.run()
        self.assertEqual(len(self.lib.albums()), 2)

    def test_incremental_item(self):
        self.config['import']['singletons'] = True
        importer = self.create_importer(item_count=1)
        importer.run()

        # Change track name so the original file would be imported again
        # if incremental was off.
        item = self.lib.items().get()
        item['artist'] = 'edited artist'
        item.store()

        importer = self.create_importer(item_count=1)
        importer.run()
        self.assertEqual(len(self.lib.items()), 2)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
