import os
import os.path
import tempfile
import shutil

from _common import unittest
from beets import config
from beets.library import Item, Album, Library
from beetsplug.importfeeds import album_imported, ImportFeedsPlugin


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

        album_imported(self.lib, album)
        playlist_path = os.path.join(self.feeds_dir,
                                     os.listdir(self.feeds_dir)[0])
        self.assertTrue(playlist_path.endswith('album_name.m3u'))
        with open(playlist_path) as playlist:
            self.assertIn(item_path, playlist.read())


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
