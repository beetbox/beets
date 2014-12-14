# This file is part of beets.
# Copyright 2014, Malte Ried
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
import os
import shutil
import unittest
from beets import config
from beets.mediafile import MediaFile
from test import _common
from test.test_importer import ImportHelper


class RegexFileFilterPluginTest(_common.TestCase, ImportHelper):
    """ Test the regex file filter plugin
    """
    def setUp(self):
        super(RegexFileFilterPluginTest, self).setUp()
        self.setup_beets()
        self.__create_import_dir(2)
        self._setup_import_session()
        config['import']['enumerate_only'] = True

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
        self.load_plugins('regexfilefilter')

        import_files = [self.import_dir]
        self._setup_import_session(singletons=singletons)
        self.importer.paths = import_files

        self.io.install()
        self.importer.run()
        out = self.io.getoutput()
        self.io.restore()
        self.unload_plugins()

        lines = out.splitlines()

        for line in lines:
            print line

        self.assertEqual(lines, expected_lines)

    def __reset_config(self):
        config['regexfilefilter'] = {}

    def test_import_default(self):
        """ The default configuration should import everything.
        """
        self.__reset_config()
        self.__run(self.all_paths)

    # Global options
    def test_import_global_match_folder(self):
        self.__reset_config()
        config['regexfilefilter']['folder_name_regex'] = 'artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])

    def test_import_global_invert_folder(self):
        self.__reset_config()
        config['regexfilefilter']['folder_name_regex'] = 'artist'
        config['regexfilefilter']['invert_folder_result'] = True
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]])

    def test_import_global_match_file(self):
        self.__reset_config()
        config['regexfilefilter']['file_name_regex'] = '.*2.*'
        self.__run([self.artist_paths[1],
                    self.album_paths[1],
                    self.misc_paths[1]])

    def test_import_global_invert_file(self):
        self.__reset_config()
        config['regexfilefilter']['file_name_regex'] = '.*2.*'
        config['regexfilefilter']['invert_file_result'] = True
        self.__run([self.artist_paths[0],
                    self.album_paths[0],
                    self.misc_paths[0]])

    def test_import_global_match_folder_case_sensitive(self):
        self.__reset_config()
        config['regexfilefilter']['folder_name_regex'] = 'Artist'
        self.__run([])

    def test_import_global_match_folder_ignore_case(self):
        self.__reset_config()
        config['regexfilefilter']['ignore_case'] = True
        config['regexfilefilter']['folder_name_regex'] = 'Artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])

    # Album options
    def test_import_album_match_folder(self):
        self.__reset_config()
        config['regexfilefilter']['album']['folder_name_regex'] = 'artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])
        self.__run(self.all_paths, singletons=True)

    def test_import_album_invert_folder(self):
        self.__reset_config()
        config['regexfilefilter']['album']['folder_name_regex'] = 'artist'
        config['regexfilefilter']['album']['invert_folder_result'] = True
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]])
        self.__run(self.all_paths, singletons=True)

    def test_import_album_match_file(self):
        self.__reset_config()
        config['regexfilefilter']['album']['file_name_regex'] = '.*2.*'
        self.__run([self.artist_paths[1],
                    self.album_paths[1],
                    self.misc_paths[1]])
        self.__run(self.all_paths, singletons=True)

    def test_import_album_invert_file(self):
        self.__reset_config()
        config['regexfilefilter']['album']['file_name_regex'] = '.*2.*'
        config['regexfilefilter']['album']['invert_file_result'] = True
        self.__run([self.artist_paths[0],
                    self.album_paths[0],
                    self.misc_paths[0]])
        self.__run(self.all_paths, singletons=True)

    def test_import_album_match_folder_case_sensitive(self):
        self.__reset_config()
        config['regexfilefilter']['album']['folder_name_regex'] = 'Artist'
        self.__run([])
        self.__run(self.all_paths, singletons=True)

    def test_import_album_match_folder_ignore_case(self):
        self.__reset_config()
        config['regexfilefilter']['ignore_case'] = True
        config['regexfilefilter']['album']['folder_name_regex'] = 'Artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])
        self.__run(self.all_paths, singletons=True)

    # Singleton options
    def test_import_singleton_match_folder(self):
        self.__reset_config()
        config['regexfilefilter']['singleton']['folder_name_regex'] = 'artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]], singletons=True)
        self.__run(self.all_paths)

    def test_import_singleton_invert_folder(self):
        self.__reset_config()
        config['regexfilefilter']['singleton']['folder_name_regex'] = 'artist'
        config['regexfilefilter']['singleton']['invert_folder_result'] = True
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]], singletons=True)
        self.__run(self.all_paths)

    def test_import_singleton_match_file(self):
        self.__reset_config()
        config['regexfilefilter']['singleton']['file_name_regex'] = '.*2.*'
        self.__run([self.artist_paths[1],
                    self.album_paths[1],
                    self.misc_paths[1]], singletons=True)
        self.__run(self.all_paths)

    def test_import_singleton_invert_file(self):
        self.__reset_config()
        config['regexfilefilter']['singleton']['file_name_regex'] = '.*2.*'
        config['regexfilefilter']['singleton']['invert_file_result'] = True
        self.__run([self.artist_paths[0],
                    self.album_paths[0],
                    self.misc_paths[0]], singletons=True)
        self.__run(self.all_paths)

    def test_import_singleton_match_folder_case_sensitive(self):
        self.__reset_config()
        config['regexfilefilter']['singleton']['folder_name_regex'] = 'Artist'
        self.__run([], singletons=True)
        self.__run(self.all_paths)

    def test_import_singleton_match_folder_ignore_case(self):
        self.__reset_config()
        config['regexfilefilter']['ignore_case'] = True
        config['regexfilefilter']['singleton']['folder_name_regex'] = 'Artist'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]], singletons=True)
        self.__run(self.all_paths)

    # Album and singleton options
    def test_import_both_match_folder(self):
        self.__reset_config()
        config['regexfilefilter']['album']['folder_name_regex'] = 'artist'
        config['regexfilefilter']['singleton']['folder_name_regex'] = 'misc'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]], singletons=True)

    def test_import_both_invert_folder(self):
        self.__reset_config()
        config['regexfilefilter']['album']['folder_name_regex'] = 'artist'
        config['regexfilefilter']['album']['invert_folder_result'] = True
        config['regexfilefilter']['singleton']['folder_name_regex'] = 'misc'
        config['regexfilefilter']['singleton']['invert_folder_result'] = True
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]])
        self.__run([self.artist_paths[0],
                    self.artist_paths[1],
                    self.album_paths[0],
                    self.album_paths[1]], singletons=True)

    def test_import_both_match_file(self):
        self.__reset_config()
        config['regexfilefilter']['album']['file_name_regex'] = '.*2.*'
        config['regexfilefilter']['singleton']['file_name_regex'] = '.*1.*'
        self.__run([self.artist_paths[1],
                    self.album_paths[1],
                    self.misc_paths[1]])
        self.__run([self.artist_paths[0],
                    self.album_paths[0],
                    self.misc_paths[0]], singletons=True)

    def test_import_both_invert_file(self):
        self.__reset_config()
        config['regexfilefilter']['album']['file_name_regex'] = '.*2.*'
        config['regexfilefilter']['album']['invert_file_result'] = True
        config['regexfilefilter']['singleton']['file_name_regex'] = '.*1.*'
        config['regexfilefilter']['singleton']['invert_file_result'] = True
        self.__run([self.artist_paths[0],
                    self.album_paths[0],
                    self.misc_paths[0]])
        self.__run([self.artist_paths[1],
                    self.album_paths[1],
                    self.misc_paths[1]], singletons=True)

    def test_import_both_match_folder_case_sensitive(self):
        self.__reset_config()
        config['regexfilefilter']['album']['folder_name_regex'] = 'Artist'
        config['regexfilefilter']['singleton']['folder_name_regex'] = 'Misc'
        self.__run([])
        self.__run([], singletons=True)

    def test_import_both_match_folder_ignore_case(self):
        self.__reset_config()
        config['regexfilefilter']['ignore_case'] = True
        config['regexfilefilter']['album']['folder_name_regex'] = 'Artist'
        config['regexfilefilter']['singleton']['folder_name_regex'] = 'Misc'
        self.__run([self.artist_paths[0],
                    self.artist_paths[1]])
        self.__run([self.misc_paths[0],
                    self.misc_paths[1]], singletons=True)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
