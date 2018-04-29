# -*- coding: utf-8 -*-

from __future__ import division, absolute_import, print_function

import os
import os.path
import tempfile
import shutil
import unittest

from beets import config
from beets.library import Item, Album, Library
from beetsplug.importfeeds import ImportFeedsPlugin


class ImportfeedsTestTest(unittest.TestCase):

    def setUp(self):
        config.clear()
        config.read(user=False)
        self.importfeeds = ImportFeedsPlugin()
        self.lib = Library(':memory:')
        self.feeds_dir = tempfile.mkdtemp()
        config['importfeeds']['dir'] = self.feeds_dir

    def tearDown(self):
        shutil.rmtree(self.feeds_dir)

    def test_multi_format_album_playlist(self):
        config['importfeeds']['formats'] = 'm3u_multi'
        album = Album(album='album/name', id=1)
        item_path = os.path.join('path', 'to', 'item')
        item = Item(title='song', album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        self.importfeeds.album_imported(self.lib, album)
        playlist_path = os.path.join(self.feeds_dir,
                                     os.listdir(self.feeds_dir)[0])
        self.assertTrue(playlist_path.endswith('album_name.m3u'))
        with open(playlist_path) as playlist:
            self.assertIn(item_path, playlist.read())

    def test_playlist_in_subdir(self):
        config['importfeeds']['formats'] = 'm3u'
        config['importfeeds']['m3u_name'] = \
            os.path.join('subdir', 'imported.m3u')
        album = Album(album='album/name', id=1)
        item_path = os.path.join('path', 'to', 'item')
        item = Item(title='song', album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        self.importfeeds.album_imported(self.lib, album)
        playlist = os.path.join(self.feeds_dir,
                                config['importfeeds']['m3u_name'].get())
        playlist_subdir = os.path.dirname(playlist)
        self.assertTrue(os.path.isdir(playlist_subdir))
        self.assertTrue(os.path.isfile(playlist))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
