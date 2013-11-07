"""Tests for the 'ihate' plugin"""

from _common import unittest
from beets.importer import ImportTask
from beets.library import Item
from beetsplug.ihate import IHatePlugin


class IHatePluginTest(unittest.TestCase):

    def test_hate_album(self):
        """ iHate tests for album """

        genre_p = []
        artist_p = []
        album_p = []
        white_p = []
        task = ImportTask()
        task.cur_artist = u'Test Artist'
        task.cur_album = u'Test Album'
        task.items = [Item(genre='Test Genre')]
        self.assertFalse(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                    album_p, white_p))
        genre_p = 'some_genre test\sgenre'.split()
        self.assertTrue(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))
        genre_p = []
        artist_p = 'bad_artist test\sartist'
        self.assertTrue(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))
        artist_p = []
        album_p = 'tribute christmas test'.split()
        self.assertTrue(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))
        album_p = []
        white_p = 'goodband test\sartist another_band'.split()
        genre_p = 'some_genre test\sgenre'.split()
        self.assertFalse(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))
        genre_p = []
        artist_p = 'bad_artist test\sartist'
        self.assertFalse(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))
        artist_p = []
        album_p = 'tribute christmas test'.split()
        self.assertFalse(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))

    def test_hate_singleton(self):
        """ iHate tests for singleton """

        genre_p = []
        artist_p = []
        album_p = []
        white_p = []
        task = ImportTask()
        task.cur_artist = u'Test Artist'
        task.items = [Item(genre='Test Genre')]
        self.assertFalse(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                    album_p, white_p))
        genre_p = 'some_genre test\sgenre'.split()
        self.assertTrue(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))
        genre_p = []
        artist_p = 'bad_artist test\sartist'
        self.assertTrue(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))
        artist_p = []
        album_p = 'tribute christmas test'.split()
        self.assertFalse(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))
        album_p = []
        white_p = 'goodband test\sartist another_band'.split()
        genre_p = 'some_genre test\sgenre'.split()
        self.assertFalse(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))
        genre_p = []
        artist_p = 'bad_artist test\sartist'
        self.assertFalse(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))
        artist_p = []
        album_p = 'tribute christmas test'.split()
        self.assertFalse(IHatePlugin.do_i_hate_this(task, genre_p, artist_p,
                                                   album_p, white_p))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
