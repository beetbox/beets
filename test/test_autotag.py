# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

"""Tests for autotagging functionality.
"""

import unittest
import sys
import os
import shutil
import re
sys.path.append('..')
from beets import autotag
from beets.library import Item

class AutotagTest(unittest.TestCase):
    def test_current_metadata_finds_pluralities(self):
        items = [Item({'artist': 'The Beetles', 'album': 'The White Album'}),
                 Item({'artist': 'The Beatles', 'album': 'The White Album'}),
                 Item({'artist': 'The Beatles', 'album': 'Teh White Album'})]
        l_artist, l_album = autotag.current_metadata(items)
        self.assertEqual(l_artist, 'The Beatles')
        self.assertEqual(l_album, 'The White Album')

def _mkmp3(path):
    shutil.copyfile(os.path.join('rsrc', 'min.mp3'), path)
class AlbumsInDirTest(unittest.TestCase):
    def setUp(self):
        # create a directory structure for testing
        self.base = os.path.join('rsrc', 'temp_albumsindir')
        os.mkdir(self.base)
        
        os.mkdir(os.path.join(self.base, 'album1'))
        os.mkdir(os.path.join(self.base, 'album2'))
        os.mkdir(os.path.join(self.base, 'more'))
        os.mkdir(os.path.join(self.base, 'more', 'album3'))
        os.mkdir(os.path.join(self.base, 'more', 'album4'))
        
        _mkmp3(os.path.join(self.base, 'album1', 'album1song1.mp3'))
        _mkmp3(os.path.join(self.base, 'album1', 'album1song2.mp3'))
        _mkmp3(os.path.join(self.base, 'album2', 'album2song.mp3'))
        _mkmp3(os.path.join(self.base, 'more', 'album3', 'album3song.mp3'))
        _mkmp3(os.path.join(self.base, 'more', 'album4', 'album4song.mp3'))
    def tearDown(self):
        shutil.rmtree(self.base)
    
    def test_finds_all_albums(self):
        albums = list(autotag.albums_in_dir(self.base))
        self.assertEqual(len(albums), 4)
    
    def test_separates_contents(self):
        found = []
        for album in autotag.albums_in_dir(self.base):
            found.append(re.search(r'album(.)song', album[0].path).group(1))
        self.assertTrue('1' in found)
        self.assertTrue('2' in found)
        self.assertTrue('3' in found)
        self.assertTrue('4' in found)
    
    def test_finds_multiple_songs(self):
        for album in autotag.albums_in_dir(self.base):
            n = re.search(r'album(.)song', album[0].path).group(1)
            if n == '1':
                self.assertEqual(len(album), 2)
            else:
                self.assertEqual(len(album), 1)

class OrderingTest(unittest.TestCase):
    def item(self, title, track):
        return Item({
            'title': title, 'track': track,
            'mb_trackid': '', 'mb_albumid': '', 'mb_artistid': '',
        })
    
    def test_order_corrects_metadata(self):
        items = []
        items.append(self.item('one', 1))
        items.append(self.item('three', 2))
        items.append(self.item('two', 3))
        trackinfo = []
        trackinfo.append({'title': 'one', 'track': 1})
        trackinfo.append({'title': 'two', 'track': 2})
        trackinfo.append({'title': 'three', 'track': 3})
        ordered = autotag.order_items(items, trackinfo)
        self.assertEqual(ordered[0].title, 'one')
        self.assertEqual(ordered[1].title, 'two')
        self.assertEqual(ordered[2].title, 'three')

    def test_order_works_with_incomplete_metadata(self):
        items = []
        items.append(self.item('one', 1))
        items.append(self.item('three', 1))
        items.append(self.item('two', 1))
        trackinfo = []
        trackinfo.append({'title': 'one', 'track': 1})
        trackinfo.append({'title': 'two', 'track': 2})
        trackinfo.append({'title': 'three', 'track': 3})
        ordered = autotag.order_items(items, trackinfo)
        self.assertEqual(ordered[0].title, 'one')
        self.assertEqual(ordered[1].title, 'two')
        self.assertEqual(ordered[2].title, 'three')

class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.items = []
        self.items.append(Item({}))
        self.items.append(Item({}))
        trackinfo = []
        trackinfo.append({
            'title': 'oneNew',
            'id':    'http://musicbrainz.org/track/dfa939ec-118c-4d0f-'
                     '84a0-60f3d1e6522c',
        })
        trackinfo.append({
            'title':  'twoNew',
            'id':     'http://musicbrainz.org/track/40130ed1-a27c-42fd-'
                      'a328-1ebefb6caef4',
        })
        self.info = {
            'tracks': trackinfo,
            'artist': 'artistNew',
            'album':  'albumNew',
            'album_id': 'http://musicbrainz.org/release/7edb51cb-77d6-'
                        '4416-a23c-3a8c2994a2c7',
            'artist_id': 'http://musicbrainz.org/artist/a6623d39-2d8e-'
                         '4f70-8242-0a9553b91e50',
        }
    
    def test_titles_applied(self):
        autotag.apply_metadata(self.items, self.info)
        self.assertEqual(self.items[0].title, 'oneNew')
        self.assertEqual(self.items[1].title, 'twoNew')
    
    def test_album_and_artist_applied_to_all(self):
        autotag.apply_metadata(self.items, self.info)
        self.assertEqual(self.items[0].album, 'albumNew')
        self.assertEqual(self.items[1].album, 'albumNew')
        self.assertEqual(self.items[0].artist, 'artistNew')
        self.assertEqual(self.items[1].artist, 'artistNew')
    
    def test_track_index_applied(self):
        autotag.apply_metadata(self.items, self.info)
        self.assertEqual(self.items[0].track, 1)
        self.assertEqual(self.items[1].track, 2)
    
    def test_track_total_applied(self):
        autotag.apply_metadata(self.items, self.info)
        self.assertEqual(self.items[0].tracktotal, 2)
        self.assertEqual(self.items[1].tracktotal, 2)
    
    def test_mb_trackid_applied(self):
        autotag.apply_metadata(self.items, self.info)
        self.assertEqual(self.items[0].mb_trackid,
                        'dfa939ec-118c-4d0f-84a0-60f3d1e6522c')
        self.assertEqual(self.items[1].mb_trackid,
                         '40130ed1-a27c-42fd-a328-1ebefb6caef4')
    
    def test_mb_albumid_and_artistid_applied(self):
        autotag.apply_metadata(self.items, self.info)
        for item in self.items:
            self.assertEqual(item.mb_albumid,
                             '7edb51cb-77d6-4416-a23c-3a8c2994a2c7')
            self.assertEqual(item.mb_artistid,
                             'a6623d39-2d8e-4f70-8242-0a9553b91e50')

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

