"""Tests for the 'ihate' plugin"""
import os
import shutil

from _common import unittest
from beets import importer, config
from beets.library import Item
from beets.mediafile import MediaFile
from beetsplug.ihate import IHatePlugin
from test import _common
from test.helper import capture_log
from test.test_importer import ImportHelper


class IHatePluginTest(ImportHelper):
    def setUp(self):
        self.setup_beets()
        self.__create_import_dir(2)
        self._setup_import_session()
        config['import']['pretend'] = True

        self.all_paths = [self.artist_paths[0], self.artist_paths[1],
                          self.album_paths[0], self.album_paths[1],
                          self.misc_paths[0], self.misc_paths[1]]

    def tearDown(self):
        self.teardown_beets()

    def __copy_file(self, dest_path, metadata):
        # Copy files
        resource_path = os.path.join(_common.RSRC, 'full.mp3')
        shutil.copy(resource_path, dest_path)
        medium = MediaFile(dest_path)
        # Set metadata
        for attr in metadata:
            setattr(medium, attr, metadata[attr])
        medium.save()

    def __create_import_dir(self, count):
        self.import_dir = os.path.join(self.temp_dir, 'testsrcdir')
        if os.path.isdir(self.import_dir):
            shutil.rmtree(self.import_dir)

        artist_path = os.path.join(self.import_dir, 'artist')
        album_path = os.path.join(artist_path, 'album')
        misc_path = os.path.join(self.import_dir, 'misc')
        os.makedirs(album_path)
        os.makedirs(misc_path)

        metadata = {
            'artist': 'Tag Artist',
            'album':  'Tag Album',
            'albumartist':  None,
            'mb_trackid': None,
            'mb_albumid': None,
            'comp': None
        }
        self.album_paths = []
        for i in range(count):
            metadata['track'] = i + 1
            metadata['title'] = 'Tag Title Album %d' % (i + 1)
            dest_path = os.path.join(album_path, '%02d - track.mp3' % (i + 1))
            self.__copy_file(dest_path, metadata)
            self.album_paths.append(dest_path)

        self.artist_paths = []
        metadata['album'] = None
        for i in range(count):
            metadata['track'] = i + 10
            metadata['title'] = 'Tag Title Artist %d' % (i + 1)
            dest_path = os.path.join(artist_path, 'track_%d.mp3' % (i + 1))
            self.__copy_file(dest_path, metadata)
            self.artist_paths.append(dest_path)

        self.misc_paths = []
        for i in range(count):
            metadata['artist'] = 'Artist %d' % (i + 42)
            metadata['track'] = i + 5
            metadata['title'] = 'Tag Title Misc %d' % (i + 1)
            dest_path = os.path.join(misc_path, 'track_%d.mp3' % (i + 1))
            self.__copy_file(dest_path, metadata)
            self.misc_paths.append(dest_path)

    def __run(self, expected_lines, singletons=False):
        self.load_plugins('ihate')

        import_files = [self.import_dir]
        self._setup_import_session(singletons=singletons)
        self.importer.paths = import_files

        with capture_log() as logs:
            self.importer.run()
        self.unload_plugins()
        IHatePlugin.listeners = None

        logs = [line for line in logs if not line.startswith('Sending event:')]

        self.assertEqual(logs, expected_lines)

    def __reset_config(self):
        config['ihate'] = {}

    def test_hate(self):

        match_pattern = {}
        test_item = Item(
            genre='TestGenre',
            album=u'TestAlbum',
            artist=u'TestArtist')
        task = importer.SingletonImportTask(None, test_item)

        # Empty query should let it pass.
        self.assertFalse(IHatePlugin.do_i_hate_this(task, match_pattern))

        # 1 query match.
        match_pattern = ["artist:bad_artist", "artist:TestArtist"]
        self.assertTrue(IHatePlugin.do_i_hate_this(task, match_pattern))

        # 2 query matches, either should trigger.
        match_pattern = ["album:test", "artist:testartist"]
        self.assertTrue(IHatePlugin.do_i_hate_this(task, match_pattern))

        # Query is blocked by AND clause.
        match_pattern = ["album:notthis genre:testgenre"]
        self.assertFalse(IHatePlugin.do_i_hate_this(task, match_pattern))

        # Both queries are blocked by AND clause with unmatched condition.
        match_pattern = ["album:notthis genre:testgenre",
                         "artist:testartist album:notthis"]
        self.assertFalse(IHatePlugin.do_i_hate_this(task, match_pattern))

        # Only one query should fire.
        match_pattern = ["album:testalbum genre:testgenre",
                         "artist:testartist album:notthis"]
        self.assertTrue(IHatePlugin.do_i_hate_this(task, match_pattern))

    def test_import_default(self):
        """ The default configuration should import everything.
        """
        self.__reset_config()
        self.__run(self.all_paths)

    def test_import_nothing(self):
        self.__reset_config()
        config['ihate']['regex_invert_folder_result'] = True
        config['ihate']['regex_invert_file_result'] = True
        self.__run([])

    # Global options
    def test_import_global_match_folder(self):
        self.__reset_config()
        config['ihate']['regex_folder_name'] = 'artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])

    def test_import_global_invert_folder(self):
        self.__reset_config()
        config['ihate']['regex_folder_name'] = 'artist'
        config['ihate']['regex_invert_folder_result'] = True
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]])

    def test_import_global_match_file(self):
        self.__reset_config()
        config['ihate']['regex_file_name'] = '.*2.*'
        self.__run([self.artist_paths[1],
                    self.album_paths[1],
                    self.misc_paths[1]])

    def test_import_global_invert_file(self):
        self.__reset_config()
        config['ihate']['regex_file_name'] = '.*2.*'
        config['ihate']['regex_invert_file_result'] = True
        self.__run([self.artist_paths[0],
                    self.album_paths[0],
                    self.misc_paths[0]])

    def test_import_global_match_folder_case_sensitive(self):
        self.__reset_config()
        config['ihate']['regex_folder_name'] = 'Artist'
        self.__run([])

    def test_import_global_match_folder_ignore_case(self):
        self.__reset_config()
        config['ihate']['regex_ignore_case'] = True
        config['ihate']['regex_folder_name'] = 'Artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])

    # Album options
    def test_import_album_match_folder(self):
        self.__reset_config()
        config['ihate']['album']['regex_folder_name'] = 'artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])
        self.__run(self.all_paths, singletons=True)

    def test_import_album_invert_folder(self):
        self.__reset_config()
        config['ihate']['album']['regex_folder_name'] = 'artist'
        config['ihate']['album']['regex_invert_folder_result'] = True
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]])
        self.__run(self.all_paths, singletons=True)

    def test_import_album_match_file(self):
        self.__reset_config()
        config['ihate']['album']['regex_file_name'] = '.*2.*'
        self.__run([self.artist_paths[1],
                    self.album_paths[1],
                    self.misc_paths[1]])
        self.__run(self.all_paths, singletons=True)

    def test_import_album_invert_file(self):
        self.__reset_config()
        config['ihate']['album']['regex_file_name'] = '.*2.*'
        config['ihate']['album']['regex_invert_file_result'] = True
        self.__run([self.artist_paths[0],
                    self.album_paths[0],
                    self.misc_paths[0]])
        self.__run(self.all_paths, singletons=True)

    def test_import_album_match_folder_case_sensitive(self):
        self.__reset_config()
        config['ihate']['album']['regex_folder_name'] = 'Artist'
        self.__run([])
        self.__run(self.all_paths, singletons=True)

    def test_import_album_match_folder_ignore_case(self):
        self.__reset_config()
        config['ihate']['regex_ignore_case'] = True
        config['ihate']['album']['regex_folder_name'] = 'Artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])
        self.__run(self.all_paths, singletons=True)

    # Singleton options
    def test_import_singleton_match_folder(self):
        self.__reset_config()
        config['ihate']['singleton']['regex_folder_name'] = 'artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]], singletons=True)
        self.__run(self.all_paths)

    def test_import_singleton_invert_folder(self):
        self.__reset_config()
        config['ihate']['singleton']['regex_folder_name'] = 'artist'
        config['ihate']['singleton']['regex_invert_folder_result'] = True
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]], singletons=True)
        self.__run(self.all_paths)

    def test_import_singleton_match_file(self):
        self.__reset_config()
        config['ihate']['singleton']['regex_file_name'] = '.*2.*'
        self.__run([self.artist_paths[1],
                    self.album_paths[1],
                    self.misc_paths[1]], singletons=True)
        self.__run(self.all_paths)

    def test_import_singleton_invert_file(self):
        self.__reset_config()
        config['ihate']['singleton']['regex_file_name'] = '.*2.*'
        config['ihate']['singleton']['regex_invert_file_result'] = True
        self.__run([self.artist_paths[0],
                    self.album_paths[0],
                    self.misc_paths[0]], singletons=True)
        self.__run(self.all_paths)

    def test_import_singleton_match_folder_case_sensitive(self):
        self.__reset_config()
        config['ihate']['singleton']['regex_folder_name'] = 'Artist'
        self.__run([], singletons=True)
        self.__run(self.all_paths)

    def test_import_singleton_match_folder_ignore_case(self):
        self.__reset_config()
        config['ihate']['regex_ignore_case'] = True
        config['ihate']['singleton']['regex_folder_name'] = 'Artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]], singletons=True)
        self.__run(self.all_paths)

    # Album and singleton options
    def test_import_both_match_folder(self):
        self.__reset_config()
        config['ihate']['album']['regex_folder_name'] = 'artist'
        config['ihate']['singleton']['regex_folder_name'] = 'misc'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]], singletons=True)

    def test_import_both_invert_folder(self):
        self.__reset_config()
        config['ihate']['album']['regex_folder_name'] = 'artist'
        config['ihate']['album']['regex_invert_folder_result'] = True
        config['ihate']['singleton']['regex_folder_name'] = 'misc'
        config['ihate']['singleton']['regex_invert_folder_result'] = True
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]])
        self.__run([self.artist_paths[0],
                    self.artist_paths[1],
                    self.album_paths[0],
                    self.album_paths[1]], singletons=True)

    def test_import_both_match_file(self):
        self.__reset_config()
        config['ihate']['album']['regex_file_name'] = '.*2.*'
        config['ihate']['singleton']['regex_file_name'] = '.*1.*'
        self.__run([self.artist_paths[1],
                    self.album_paths[1],
                    self.misc_paths[1]])
        self.__run([self.artist_paths[0],
                    self.album_paths[0],
                    self.misc_paths[0]], singletons=True)

    def test_import_both_invert_file(self):
        self.__reset_config()
        config['ihate']['album']['regex_file_name'] = '.*2.*'
        config['ihate']['album']['regex_invert_file_result'] = True
        config['ihate']['singleton']['regex_file_name'] = '.*1.*'
        config['ihate']['singleton']['regex_invert_file_result'] = True
        self.__run([self.artist_paths[0],
                    self.album_paths[0],
                    self.misc_paths[0]])
        self.__run([self.artist_paths[1],
                    self.album_paths[1],
                    self.misc_paths[1]], singletons=True)

    def test_import_both_match_folder_case_sensitive(self):
        self.__reset_config()
        config['ihate']['album']['regex_folder_name'] = 'Artist'
        config['ihate']['singleton']['regex_folder_name'] = 'Misc'
        self.__run([])
        self.__run([], singletons=True)

    def test_import_both_match_folder_ignore_case(self):
        self.__reset_config()
        config['ihate']['regex_ignore_case'] = True
        config['ihate']['album']['regex_folder_name'] = 'Artist'
        config['ihate']['singleton']['regex_folder_name'] = 'Misc'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]], singletons=True)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
