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

"""Tests for autotagging functionality.
"""
import os
import shutil
import re
import copy

import _common
from _common import unittest
from beets import autotag
from beets.autotag import match
from beets.library import Item
from beets.util import plurality
from beets.autotag import AlbumInfo, TrackInfo
from beets import config

class PluralityTest(unittest.TestCase):
    def test_plurality_consensus(self):
        objs = [1, 1, 1, 1]
        obj, freq = plurality(objs)
        self.assertEqual(obj, 1)
        self.assertEqual(freq, 4)

    def test_plurality_near_consensus(self):
        objs = [1, 1, 2, 1]
        obj, freq = plurality(objs)
        self.assertEqual(obj, 1)
        self.assertEqual(freq, 3)

    def test_plurality_conflict(self):
        objs = [1, 1, 2, 2, 3]
        obj, freq = plurality(objs)
        self.assert_(obj in (1, 2))
        self.assertEqual(freq, 2)

    def test_plurality_empty_sequence_raises_error(self):
        with self.assertRaises(ValueError):
            plurality([])

    def test_current_metadata_finds_pluralities(self):
        items = [Item({'artist': 'The Beetles', 'album': 'The White Album'}),
                 Item({'artist': 'The Beatles', 'album': 'The White Album'}),
                 Item({'artist': 'The Beatles', 'album': 'Teh White Album'})]
        l_artist, l_album, artist_consensus = match.current_metadata(items)
        self.assertEqual(l_artist, 'The Beatles')
        self.assertEqual(l_album, 'The White Album')
        self.assertFalse(artist_consensus)

    def test_current_metadata_artist_consensus(self):
        items = [Item({'artist': 'The Beatles', 'album': 'The White Album'}),
                 Item({'artist': 'The Beatles', 'album': 'The White Album'}),
                 Item({'artist': 'The Beatles', 'album': 'Teh White Album'})]
        l_artist, l_album, artist_consensus = match.current_metadata(items)
        self.assertEqual(l_artist, 'The Beatles')
        self.assertEqual(l_album, 'The White Album')
        self.assertTrue(artist_consensus)

    def test_albumartist_consensus(self):
        items = [Item({'artist': 'tartist1', 'album': 'album',
                       'albumartist': 'aartist'}),
                 Item({'artist': 'tartist2', 'album': 'album',
                       'albumartist': 'aartist'}),
                 Item({'artist': 'tartist3', 'album': 'album',
                       'albumartist': 'aartist'})]
        l_artist, l_album, artist_consensus = match.current_metadata(items)
        self.assertEqual(l_artist, 'aartist')
        self.assertFalse(artist_consensus)

def _make_item(title, track, artist=u'some artist'):
    return Item({
        'title': title, 'track': track,
        'artist': artist, 'album': u'some album',
        'length': 1,
        'mb_trackid': '', 'mb_albumid': '', 'mb_artistid': '',
    })

def _make_trackinfo():
    return [
        TrackInfo(u'one', None, u'some artist', length=1, index=1),
        TrackInfo(u'two', None, u'some artist', length=1, index=2),
        TrackInfo(u'three', None, u'some artist', length=1, index=3),
    ]

class TrackDistanceTest(unittest.TestCase):
    def test_identical_tracks(self):
        item = _make_item(u'one', 1)
        info = _make_trackinfo()[0]
        dist = match.track_distance(item, info, incl_artist=True)
        self.assertEqual(dist, 0.0)

    def test_different_title(self):
        item = _make_item(u'foo', 1)
        info = _make_trackinfo()[0]
        dist = match.track_distance(item, info, incl_artist=True)
        self.assertNotEqual(dist, 0.0)

    def test_different_artist(self):
        item = _make_item(u'one', 1)
        item.artist = u'foo'
        info = _make_trackinfo()[0]
        dist = match.track_distance(item, info, incl_artist=True)
        self.assertNotEqual(dist, 0.0)

    def test_various_artists_tolerated(self):
        item = _make_item(u'one', 1)
        item.artist = u'Various Artists'
        info = _make_trackinfo()[0]
        dist = match.track_distance(item, info, incl_artist=True)
        self.assertEqual(dist, 0.0)

class AlbumDistanceTest(unittest.TestCase):
    def _mapping(self, items, info):
        out = {}
        for i, t in zip(items, info.tracks):
            out[i] = t
        return out

    def _dist(self, items, info):
        return match.distance(items, info, self._mapping(items, info))

    def test_identical_albums(self):
        items = []
        items.append(_make_item(u'one', 1))
        items.append(_make_item(u'two', 2))
        items.append(_make_item(u'three', 3))
        info = AlbumInfo(
            artist = u'some artist',
            album = u'some album',
            tracks = _make_trackinfo(),
            va = False,
            album_id = None, artist_id = None,
        )
        self.assertEqual(self._dist(items, info), 0)

    def test_incomplete_album(self):
        items = []
        items.append(_make_item(u'one', 1))
        items.append(_make_item(u'three', 3))
        info = AlbumInfo(
            artist = u'some artist',
            album = u'some album',
            tracks = _make_trackinfo(),
            va = False,
            album_id = None, artist_id = None,
        )
        dist = self._dist(items, info)
        self.assertNotEqual(dist, 0)
        # Make sure the distance is not too great
        self.assertTrue(dist < 0.2)

    def test_global_artists_differ(self):
        items = []
        items.append(_make_item(u'one', 1))
        items.append(_make_item(u'two', 2))
        items.append(_make_item(u'three', 3))
        info = AlbumInfo(
            artist = u'someone else',
            album = u'some album',
            tracks = _make_trackinfo(),
            va = False,
            album_id = None, artist_id = None,
        )
        self.assertNotEqual(self._dist(items, info), 0)

    def test_comp_track_artists_match(self):
        items = []
        items.append(_make_item(u'one', 1))
        items.append(_make_item(u'two', 2))
        items.append(_make_item(u'three', 3))
        info = AlbumInfo(
            artist = u'should be ignored',
            album = u'some album',
            tracks = _make_trackinfo(),
            va = True,
            album_id = None, artist_id = None,
        )
        self.assertEqual(self._dist(items, info), 0)

    def test_comp_no_track_artists(self):
        # Some VA releases don't have track artists (incomplete metadata).
        items = []
        items.append(_make_item(u'one', 1))
        items.append(_make_item(u'two', 2))
        items.append(_make_item(u'three', 3))
        info = AlbumInfo(
            artist = u'should be ignored',
            album = u'some album',
            tracks = _make_trackinfo(),
            va = True,
            album_id = None, artist_id = None,
        )
        info.tracks[0].artist = None
        info.tracks[1].artist = None
        info.tracks[2].artist = None
        self.assertEqual(self._dist(items, info), 0)

    def test_comp_track_artists_do_not_match(self):
        items = []
        items.append(_make_item(u'one', 1))
        items.append(_make_item(u'two', 2, u'someone else'))
        items.append(_make_item(u'three', 3))
        info = AlbumInfo(
            artist = u'some artist',
            album = u'some album',
            tracks = _make_trackinfo(),
            va = True,
            album_id = None, artist_id = None,
        )
        self.assertNotEqual(self._dist(items, info), 0)

    def test_tracks_out_of_order(self):
        items = []
        items.append(_make_item(u'one', 1))
        items.append(_make_item(u'three', 2))
        items.append(_make_item(u'two', 3))
        info = AlbumInfo(
            artist = u'some artist',
            album = u'some album',
            tracks = _make_trackinfo(),
            va = False,
            album_id = None, artist_id = None,
        )
        dist = self._dist(items, info)
        self.assertTrue(0 < dist < 0.2)

    def test_two_medium_release(self):
        items = []
        items.append(_make_item(u'one', 1))
        items.append(_make_item(u'two', 2))
        items.append(_make_item(u'three', 3))
        info = AlbumInfo(
            artist = u'some artist',
            album = u'some album',
            tracks = _make_trackinfo(),
            va = False,
            album_id = None, artist_id = None,
        )
        info.tracks[0].medium_index = 1
        info.tracks[1].medium_index = 2
        info.tracks[2].medium_index = 1
        dist = self._dist(items, info)
        self.assertEqual(dist, 0)

    def test_per_medium_track_numbers(self):
        items = []
        items.append(_make_item(u'one', 1))
        items.append(_make_item(u'two', 2))
        items.append(_make_item(u'three', 1))
        info = AlbumInfo(
            artist = u'some artist',
            album = u'some album',
            tracks = _make_trackinfo(),
            va = False,
            album_id = None, artist_id = None,
        )
        info.tracks[0].medium_index = 1
        info.tracks[1].medium_index = 2
        info.tracks[2].medium_index = 1
        dist = self._dist(items, info)
        self.assertEqual(dist, 0)

def _mkmp3(path):
    shutil.copyfile(os.path.join(_common.RSRC, 'min.mp3'), path)
class AlbumsInDirTest(unittest.TestCase):
    def setUp(self):
        # create a directory structure for testing
        self.base = os.path.abspath(os.path.join(_common.RSRC, 'tempdir'))
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
        for _, album in autotag.albums_in_dir(self.base):
            found.append(re.search(r'album(.)song', album[0].path).group(1))
        self.assertTrue('1' in found)
        self.assertTrue('2' in found)
        self.assertTrue('3' in found)
        self.assertTrue('4' in found)

    def test_finds_multiple_songs(self):
        for _, album in autotag.albums_in_dir(self.base):
            n = re.search(r'album(.)song', album[0].path).group(1)
            if n == '1':
                self.assertEqual(len(album), 2)
            else:
                self.assertEqual(len(album), 1)

class MultiDiscAlbumsInDirTest(unittest.TestCase):
    def setUp(self):
        self.base = os.path.abspath(os.path.join(_common.RSRC, 'tempdir'))
        os.mkdir(self.base)

        self.dirs = [
            # Nested album with non-consecutive disc numbers and a subtitle.
            os.path.join(self.base, 'album1'),
            os.path.join(self.base, 'album1', 'cd 1'),
            os.path.join(self.base, 'album1', 'cd 3 - bonus'),
            # Nested album with a single disc and punctuation.
            os.path.join(self.base, 'album2'),
            os.path.join(self.base, 'album2', 'cd _ 1'),
            # Flattened album with case typo.
            os.path.join(self.base, 'artist'),
            os.path.join(self.base, 'artist', 'CAT disc 1'),
            os.path.join(self.base, 'artist', 'Cat disc 2'),
            # Prevent "CAT" being collapsed as a nested multi-disc album,
            # and test case insensitive sorting.
            os.path.join(self.base, 'artist', 'CATS'),
        ]
        self.files = [
            os.path.join(self.base, 'album1', 'cd 1', 'song1.mp3'),
            os.path.join(self.base, 'album1', 'cd 3 - bonus', 'song2.mp3'),
            os.path.join(self.base, 'album1', 'cd 3 - bonus', 'song3.mp3'),
            os.path.join(self.base, 'album2', 'cd _ 1', 'song4.mp3'),
            os.path.join(self.base, 'artist', 'CAT disc 1', 'song5.mp3'),
            os.path.join(self.base, 'artist', 'Cat disc 2', 'song6.mp3'),
            os.path.join(self.base, 'artist', 'CATS', 'song7.mp3'),
        ]

        for path in self.dirs:
            os.mkdir(path)
        for path in self.files:
            _mkmp3(path)

    def tearDown(self):
        shutil.rmtree(self.base)

    def test_coalesce_multi_disc_album(self):
        albums = list(autotag.albums_in_dir(self.base))
        self.assertEquals(len(albums), 4)
        # Nested album with non-consecutive disc numbers.
        root, items = albums[0]
        self.assertEquals(root, self.dirs[0:3])
        self.assertEquals(len(items), 3)
        # Nested album with a single disc and punctuation.
        root, items = albums[1]
        self.assertEquals(root, self.dirs[3:5])
        self.assertEquals(len(items), 1)
        # Flattened album with case typo.
        root, items = albums[2]
        self.assertEquals(root, self.dirs[6:8])
        self.assertEquals(len(items), 2)
        # Non-multi-disc album (sorted in between "cat" album).
        root, items = albums[3]
        self.assertEquals(root, self.dirs[8:])
        self.assertEquals(len(items), 1)

    def test_do_not_yield_empty_album(self):
        # Remove all the MP3s.
        for path in self.files:
            os.remove(path)
        albums = list(autotag.albums_in_dir(self.base))
        self.assertEquals(len(albums), 0)

class AssignmentTest(unittest.TestCase):
    def item(self, title, track):
        return Item({
            'title': title, 'track': track,
            'mb_trackid': '', 'mb_albumid': '', 'mb_artistid': '',
        })

    def test_reorder_when_track_numbers_incorrect(self):
        items = []
        items.append(self.item(u'one', 1))
        items.append(self.item(u'three', 2))
        items.append(self.item(u'two', 3))
        trackinfo = []
        trackinfo.append(TrackInfo(u'one', None))
        trackinfo.append(TrackInfo(u'two', None))
        trackinfo.append(TrackInfo(u'three', None))
        mapping, extra_items, extra_tracks = \
            match.assign_items(items, trackinfo)
        self.assertEqual(extra_items, set())
        self.assertEqual(extra_tracks, set())
        self.assertEqual(mapping, {
            items[0]: trackinfo[0],
            items[1]: trackinfo[2],
            items[2]: trackinfo[1],
        })

    def test_order_works_with_invalid_track_numbers(self):
        items = []
        items.append(self.item(u'one', 1))
        items.append(self.item(u'three', 1))
        items.append(self.item(u'two', 1))
        trackinfo = []
        trackinfo.append(TrackInfo(u'one', None))
        trackinfo.append(TrackInfo(u'two', None))
        trackinfo.append(TrackInfo(u'three', None))
        mapping, extra_items, extra_tracks = \
            match.assign_items(items, trackinfo)
        self.assertEqual(extra_items, set())
        self.assertEqual(extra_tracks, set())
        self.assertEqual(mapping, {
            items[0]: trackinfo[0],
            items[1]: trackinfo[2],
            items[2]: trackinfo[1],
        })

    def test_order_works_with_missing_tracks(self):
        items = []
        items.append(self.item(u'one', 1))
        items.append(self.item(u'three', 3))
        trackinfo = []
        trackinfo.append(TrackInfo(u'one', None))
        trackinfo.append(TrackInfo(u'two', None))
        trackinfo.append(TrackInfo(u'three', None))
        mapping, extra_items, extra_tracks = \
            match.assign_items(items, trackinfo)
        self.assertEqual(extra_items, set())
        self.assertEqual(extra_tracks, set([trackinfo[1]]))
        self.assertEqual(mapping, {
            items[0]: trackinfo[0],
            items[1]: trackinfo[2],
        })

    def test_order_works_with_extra_tracks(self):
        items = []
        items.append(self.item(u'one', 1))
        items.append(self.item(u'two', 2))
        items.append(self.item(u'three', 3))
        trackinfo = []
        trackinfo.append(TrackInfo(u'one', None))
        trackinfo.append(TrackInfo(u'three', None))
        mapping, extra_items, extra_tracks = \
            match.assign_items(items, trackinfo)
        self.assertEqual(extra_items, set([items[1]]))
        self.assertEqual(extra_tracks, set())
        self.assertEqual(mapping, {
            items[0]: trackinfo[0],
            items[2]: trackinfo[1],
        })

    def test_order_works_when_track_names_are_entirely_wrong(self):
        # A real-world test case contributed by a user.
        def item(i, length):
            return Item({
                'artist': u'ben harper',
                'album': u'burn to shine',
                'title': u'ben harper - Burn to Shine ' + str(i),
                'track': i,
                'length': length,
                'mb_trackid': '', 'mb_albumid': '', 'mb_artistid': '',
            })
        items = []
        items.append(item(1, 241.37243007106997))
        items.append(item(2, 342.27781704375036))
        items.append(item(3, 245.95070222338137))
        items.append(item(4, 472.87662515485437))
        items.append(item(5, 279.1759535763187))
        items.append(item(6, 270.33333768012))
        items.append(item(7, 247.83435613222923))
        items.append(item(8, 216.54504531525072))
        items.append(item(9, 225.72775379800484))
        items.append(item(10, 317.7643606963552))
        items.append(item(11, 243.57001238834192))
        items.append(item(12, 186.45916150485752))

        def info(index, title, length):
            return TrackInfo(title, None, length=length, index=index)
        trackinfo = []
        trackinfo.append(info(1, u'Alone', 238.893))
        trackinfo.append(info(2, u'The Woman in You', 341.44))
        trackinfo.append(info(3, u'Less', 245.59999999999999))
        trackinfo.append(info(4, u'Two Hands of a Prayer', 470.49299999999999))
        trackinfo.append(info(5, u'Please Bleed', 277.86599999999999))
        trackinfo.append(info(6, u'Suzie Blue', 269.30599999999998))
        trackinfo.append(info(7, u'Steal My Kisses', 245.36000000000001))
        trackinfo.append(info(8, u'Burn to Shine', 214.90600000000001))
        trackinfo.append(info(9, u'Show Me a Little Shame', 224.09299999999999))
        trackinfo.append(info(10, u'Forgiven', 317.19999999999999))
        trackinfo.append(info(11, u'Beloved One', 243.733))
        trackinfo.append(info(12, u'In the Lord\'s Arms', 186.13300000000001))

        mapping, extra_items, extra_tracks = \
            match.assign_items(items, trackinfo)
        self.assertEqual(extra_items, set())
        self.assertEqual(extra_tracks, set())
        for item, info in mapping.iteritems():
            self.assertEqual(items.index(item), trackinfo.index(info))

class ApplyTestUtil(object):
    def _apply(self, info=None, per_disc_numbering=False):
        info = info or self.info
        mapping = {}
        for i, t in zip(self.items, info.tracks):
            mapping[i] = t
        config['per_disc_numbering'] = per_disc_numbering
        autotag.apply_metadata(info, mapping)

class ApplyTest(_common.TestCase, ApplyTestUtil):
    def setUp(self):
        super(ApplyTest, self).setUp()

        self.items = []
        self.items.append(Item({}))
        self.items.append(Item({}))
        trackinfo = []
        trackinfo.append(TrackInfo(
            u'oneNew', 'dfa939ec-118c-4d0f-84a0-60f3d1e6522c', medium=1,
            medium_index=1, artist_credit='trackArtistCredit',
            artist_sort='trackArtistSort', index=1,
        ))
        trackinfo.append(TrackInfo(u'twoNew',
                                   '40130ed1-a27c-42fd-a328-1ebefb6caef4',
                                   medium=2, medium_index=1, index=2))
        self.info = AlbumInfo(
            tracks = trackinfo,
            artist = u'artistNew',
            album = u'albumNew',
            album_id = '7edb51cb-77d6-4416-a23c-3a8c2994a2c7',
            artist_id = 'a6623d39-2d8e-4f70-8242-0a9553b91e50',
            artist_credit = u'albumArtistCredit',
            artist_sort = u'albumArtistSort',
            albumtype = u'album',
            va = False,
            mediums = 2,
        )

    def test_titles_applied(self):
        self._apply()
        self.assertEqual(self.items[0].title, 'oneNew')
        self.assertEqual(self.items[1].title, 'twoNew')

    def test_album_and_artist_applied_to_all(self):
        self._apply()
        self.assertEqual(self.items[0].album, 'albumNew')
        self.assertEqual(self.items[1].album, 'albumNew')
        self.assertEqual(self.items[0].artist, 'artistNew')
        self.assertEqual(self.items[1].artist, 'artistNew')

    def test_track_index_applied(self):
        self._apply()
        self.assertEqual(self.items[0].track, 1)
        self.assertEqual(self.items[1].track, 2)

    def test_track_total_applied(self):
        self._apply()
        self.assertEqual(self.items[0].tracktotal, 2)
        self.assertEqual(self.items[1].tracktotal, 2)

    def test_disc_index_applied(self):
        self._apply()
        self.assertEqual(self.items[0].disc, 1)
        self.assertEqual(self.items[1].disc, 2)

    def test_disc_total_applied(self):
        self._apply()
        self.assertEqual(self.items[0].disctotal, 2)
        self.assertEqual(self.items[1].disctotal, 2)

    def test_per_disc_numbering(self):
        self._apply(per_disc_numbering=True)
        self.assertEqual(self.items[0].track, 1)
        self.assertEqual(self.items[1].track, 1)

    def test_mb_trackid_applied(self):
        self._apply()
        self.assertEqual(self.items[0].mb_trackid,
                        'dfa939ec-118c-4d0f-84a0-60f3d1e6522c')
        self.assertEqual(self.items[1].mb_trackid,
                         '40130ed1-a27c-42fd-a328-1ebefb6caef4')

    def test_mb_albumid_and_artistid_applied(self):
        self._apply()
        for item in self.items:
            self.assertEqual(item.mb_albumid,
                             '7edb51cb-77d6-4416-a23c-3a8c2994a2c7')
            self.assertEqual(item.mb_artistid,
                             'a6623d39-2d8e-4f70-8242-0a9553b91e50')

    def test_albumtype_applied(self):
        self._apply()
        self.assertEqual(self.items[0].albumtype, 'album')
        self.assertEqual(self.items[1].albumtype, 'album')

    def test_album_artist_overrides_empty_track_artist(self):
        my_info = copy.deepcopy(self.info)
        self._apply(info=my_info)
        self.assertEqual(self.items[0].artist, 'artistNew')
        self.assertEqual(self.items[0].artist, 'artistNew')

    def test_album_artist_overriden_by_nonempty_track_artist(self):
        my_info = copy.deepcopy(self.info)
        my_info.tracks[0].artist = 'artist1!'
        my_info.tracks[1].artist = 'artist2!'
        self._apply(info=my_info)
        self.assertEqual(self.items[0].artist, 'artist1!')
        self.assertEqual(self.items[1].artist, 'artist2!')

    def test_artist_credit_applied(self):
        self._apply()
        self.assertEqual(self.items[0].albumartist_credit, 'albumArtistCredit')
        self.assertEqual(self.items[0].artist_credit, 'trackArtistCredit')
        self.assertEqual(self.items[1].albumartist_credit, 'albumArtistCredit')
        self.assertEqual(self.items[1].artist_credit, 'albumArtistCredit')

    def test_artist_sort_applied(self):
        self._apply()
        self.assertEqual(self.items[0].albumartist_sort, 'albumArtistSort')
        self.assertEqual(self.items[0].artist_sort, 'trackArtistSort')
        self.assertEqual(self.items[1].albumartist_sort, 'albumArtistSort')
        self.assertEqual(self.items[1].artist_sort, 'albumArtistSort')

class ApplyCompilationTest(_common.TestCase, ApplyTestUtil):
    def setUp(self):
        super(ApplyCompilationTest, self).setUp()

        self.items = []
        self.items.append(Item({}))
        self.items.append(Item({}))
        trackinfo = []
        trackinfo.append(TrackInfo(
            u'oneNew',
            'dfa939ec-118c-4d0f-84a0-60f3d1e6522c',
            u'artistOneNew',
            'a05686fc-9db2-4c23-b99e-77f5db3e5282',
            index=1,
        ))
        trackinfo.append(TrackInfo(
            u'twoNew',
            '40130ed1-a27c-42fd-a328-1ebefb6caef4',
            u'artistTwoNew',
            '80b3cf5e-18fe-4c59-98c7-e5bb87210710',
            index=2,
        ))
        self.info = AlbumInfo(
            tracks = trackinfo,
            artist = u'variousNew',
            album = u'albumNew',
            album_id = '3b69ea40-39b8-487f-8818-04b6eff8c21a',
            artist_id = '89ad4ac3-39f7-470e-963a-56509c546377',
            albumtype = u'compilation',
            va = False,
        )

    def test_album_and_track_artists_separate(self):
        self._apply()
        self.assertEqual(self.items[0].artist, 'artistOneNew')
        self.assertEqual(self.items[1].artist, 'artistTwoNew')
        self.assertEqual(self.items[0].albumartist, 'variousNew')
        self.assertEqual(self.items[1].albumartist, 'variousNew')

    def test_mb_albumartistid_applied(self):
        self._apply()
        self.assertEqual(self.items[0].mb_albumartistid,
                         '89ad4ac3-39f7-470e-963a-56509c546377')
        self.assertEqual(self.items[1].mb_albumartistid,
                         '89ad4ac3-39f7-470e-963a-56509c546377')
        self.assertEqual(self.items[0].mb_artistid,
                         'a05686fc-9db2-4c23-b99e-77f5db3e5282')
        self.assertEqual(self.items[1].mb_artistid,
                         '80b3cf5e-18fe-4c59-98c7-e5bb87210710')

    def test_va_flag_cleared_does_not_set_comp(self):
        self._apply()
        self.assertFalse(self.items[0].comp)
        self.assertFalse(self.items[1].comp)

    def test_va_flag_sets_comp(self):
        va_info = copy.deepcopy(self.info)
        va_info.va = True
        self._apply(info=va_info)
        self.assertTrue(self.items[0].comp)
        self.assertTrue(self.items[1].comp)

class StringDistanceTest(unittest.TestCase):
    def test_equal_strings(self):
        dist = match.string_dist(u'Some String', u'Some String')
        self.assertEqual(dist, 0.0)

    def test_different_strings(self):
        dist = match.string_dist(u'Some String', u'Totally Different')
        self.assertNotEqual(dist, 0.0)

    def test_punctuation_ignored(self):
        dist = match.string_dist(u'Some String', u'Some.String!')
        self.assertEqual(dist, 0.0)

    def test_case_ignored(self):
        dist = match.string_dist(u'Some String', u'sOME sTring')
        self.assertEqual(dist, 0.0)

    def test_leading_the_has_lower_weight(self):
        dist1 = match.string_dist(u'XXX Band Name', u'Band Name')
        dist2 = match.string_dist(u'The Band Name', u'Band Name')
        self.assert_(dist2 < dist1)

    def test_parens_have_lower_weight(self):
        dist1 = match.string_dist(u'One .Two.', u'One')
        dist2 = match.string_dist(u'One (Two)', u'One')
        self.assert_(dist2 < dist1)

    def test_brackets_have_lower_weight(self):
        dist1 = match.string_dist(u'One .Two.', u'One')
        dist2 = match.string_dist(u'One [Two]', u'One')
        self.assert_(dist2 < dist1)

    def test_ep_label_has_zero_weight(self):
        dist = match.string_dist(u'My Song (EP)', u'My Song')
        self.assertEqual(dist, 0.0)

    def test_featured_has_lower_weight(self):
        dist1 = match.string_dist(u'My Song blah Someone', u'My Song')
        dist2 = match.string_dist(u'My Song feat Someone', u'My Song')
        self.assert_(dist2 < dist1)

    def test_postfix_the(self):
        dist = match.string_dist(u'The Song Title', u'Song Title, The')
        self.assertEqual(dist, 0.0)

    def test_postfix_a(self):
        dist = match.string_dist(u'A Song Title', u'Song Title, A')
        self.assertEqual(dist, 0.0)

    def test_postfix_an(self):
        dist = match.string_dist(u'An Album Title', u'Album Title, An')
        self.assertEqual(dist, 0.0)

    def test_empty_strings(self):
        dist = match.string_dist(u'', u'')
        self.assertEqual(dist, 0.0)

    def test_solo_pattern(self):
        # Just make sure these don't crash.
        match.string_dist(u'The ', u'')
        match.string_dist(u'(EP)', u'(EP)')
        match.string_dist(u', An', u'')

    def test_heuristic_does_not_harm_distance(self):
        dist = match.string_dist(u'Untitled', u'[Untitled]')
        self.assertEqual(dist, 0.0)

    def test_ampersand_expansion(self):
        dist = match.string_dist(u'And', u'&')
        self.assertEqual(dist, 0.0)

    def test_accented_characters(self):
        dist = match.string_dist(u'\xe9\xe1\xf1', u'ean')
        self.assertEqual(dist, 0.0)

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
