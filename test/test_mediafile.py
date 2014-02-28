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

"""Automatically-generated blanket testing for the MediaFile metadata
layer.
"""
import os
import shutil
import tempfile
import datetime
import time

import _common
from _common import unittest
from beets.mediafile import MediaFile


class ArtTestMixin(object):
    """Test reads and writes of the ``art`` property.
    """

    @property
    def png_data(self):
        if not self._png_data:
            with open(os.path.join(_common.RSRC, 'image-2x3.png'), 'rb') as f:
                self._png_data = f.read()
        return self._png_data
    _png_data = None

    @property
    def jpg_data(self):
        if not self._jpg_data:
            with open(os.path.join(_common.RSRC, 'image-2x3.jpg'), 'rb') as f:
                self._jpg_data = f.read()
        return self._jpg_data
    _jpg_data = None

    def test_set_png_art(self):
        mediafile = self._mediafile_fixture('empty')
        mediafile.art = self.png_data
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.art, self.png_data)

    def test_set_jpg_art(self):
        mediafile = self._mediafile_fixture('empty')
        mediafile.art = self.jpg_data
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.art, self.jpg_data)


# TODO include this in ReadWriteTestBase if implemented
class LazySaveTestMixin(object):
    """Mediafile should only write changes when tags have changed
    """

    def test_unmodified(self):
        mediafile = self._mediafile_fixture('full')
        mtime = self._set_past_mtime(mediafile.path)
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

        mediafile.save()
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

    def test_same_tag_value(self):
        mediafile = self._mediafile_fixture('full')
        mtime = self._set_past_mtime(mediafile.path)
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

        mediafile.title = mediafile.title
        mediafile.save()
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

    def test_tag_value_change(self):
        mediafile = self._mediafile_fixture('full')
        mtime = self._set_past_mtime(mediafile.path)
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

        mediafile.title = mediafile.title
        mediafile.album = 'another'
        mediafile.save()
        self.assertNotEqual(os.stat(mediafile.path).st_mtime, mtime)

    def _set_past_mtime(self, path):
        mtime = round(time.time()-10000)
        os.utime(path, (mtime, mtime))
        return mtime


class ReadWriteTestBase(ArtTestMixin):
    """Test writing and reading tags. Subclasses must set ``extension`` and
    ``audio_properties``.
    """

    full_initial_tags = {
        'title':      u'full',
        'artist':     u'the artist',
        'album':      u'the album',
        'genre':      u'the genre',
        'composer':   u'the composer',
        'grouping':   u'the grouping',
        'year':       2001,
        'month':      0,
        'day':        0,
        'date':       datetime.date(2001, 1, 1),
        'track':      2,
        'tracktotal': 3,
        'disc':       4,
        'disctotal':  5,
        'lyrics':     u'the lyrics',
        'comments':   u'the comments',
        'bpm':        6,
        'comp':       True,
        'mb_trackid': '8b882575-08a5-4452-a7a7-cbb8a1531f9e',
        'mb_albumid': '9e873859-8aa4-4790-b985-5a953e8ef628',
        'mb_artistid':'7cf0ea9d-86b9-4dad-ba9e-2355a64899ea',
        'art':        None,
        'label':      u'the label',
    }

    empty_tags = {
        'title':      u'',
        'artist':     u'',
        'album':      u'',
        'genre':      u'',
        'composer':   u'',
        'grouping':   u'',
        'year':       0,
        'month':      0,
        'day':        0,
        'date':       datetime.date.min,
        'track':      0,
        'tracktotal': 0,
        'disc':       0,
        'disctotal':  0,
        'lyrics':     u'',
        'comments':   u'',
        'bpm':        0,
        'comp':       False,
        'mb_trackid': u'',
        'mb_albumid': u'',
        'mb_artistid':u'',
        'art':        None,
        'label':      u'',

        # Additional, non-iTunes fields.
        'rg_track_peak':        0.0,
        'rg_track_gain':        0.0,
        'rg_album_peak':        0.0,
        'rg_album_gain':        0.0,
        'albumartist':          u'',
        'mb_albumartistid':     u'',
        'artist_sort':          u'',
        'albumartist_sort':     u'',
        'acoustid_fingerprint': u'',
        'acoustid_id':          u'',
        'mb_releasegroupid':    u'',
        'asin':                 u'',
        'catalognum':           u'',
        'disctitle':            u'',
        'script':               u'',
        'language':             u'',
        'country':              u'',
        'albumstatus':          u'',
        'media':                u'',
        'albumdisambig':        u'',
        'artist_credit':        u'',
        'albumartist_credit':   u'',
        'original_year':        0,
        'original_month':       0,
        'original_day':         0,
        'original_date':        datetime.date.min,
    }

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_read_audio_properties(self):
        mediafile = self._mediafile_fixture('full')
        for key, value in self.audio_properties.items():
            if isinstance(value, float):
                self.assertAlmostEqual(getattr(mediafile, key), value, delta=0.1)
            else:
                self.assertEqual(getattr(mediafile, key), value)

    def test_read_full(self):
        mediafile = self._mediafile_fixture('full')
        self.assertTags(mediafile, self.full_initial_tags)

    def test_read_empty(self):
        mediafile = self._mediafile_fixture('empty')
        self.assertTags(mediafile, self.empty_tags)

    def test_write_empty(self):
        mediafile = self._mediafile_fixture('empty')
        tags = self._generate_tags()

        for key, value in tags.items():
            setattr(mediafile, key, value)
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertTags(mediafile, tags)

    def test_overwrite_full(self):
        mediafile = self._mediafile_fixture('full')
        tags = self._generate_tags()

        for key, value in tags.items():
            setattr(mediafile, key, value)
        mediafile.save()

        # Make sure the tags are already set when writing a second time
        for key, value in tags.items():
            setattr(mediafile, key, value)
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertTags(mediafile, tags)

    def test_write_date_components(self):
        mediafile = self._mediafile_fixture('full')
        mediafile.year = 2001
        mediafile.month = 1
        mediafile.day = 2
        mediafile.original_year = 1999
        mediafile.original_month = 12
        mediafile.original_day = 30
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.year, 2001)
        self.assertEqual(mediafile.month, 1)
        self.assertEqual(mediafile.day, 2)
        self.assertEqual(mediafile.date, datetime.date(2001,1,2))
        self.assertEqual(mediafile.original_year, 1999)
        self.assertEqual(mediafile.original_month, 12)
        self.assertEqual(mediafile.original_day, 30)
        self.assertEqual(mediafile.original_date, datetime.date(1999,12,30))

    def test_write_dates(self):
        mediafile = self._mediafile_fixture('full')
        mediafile.date = datetime.date(2001,1,2)
        mediafile.original_date = datetime.date(1999,12,30)
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.year, 2001)
        self.assertEqual(mediafile.month, 1)
        self.assertEqual(mediafile.day, 2)
        self.assertEqual(mediafile.date, datetime.date(2001,1,2))
        self.assertEqual(mediafile.original_year, 1999)
        self.assertEqual(mediafile.original_month, 12)
        self.assertEqual(mediafile.original_day, 30)
        self.assertEqual(mediafile.original_date, datetime.date(1999,12,30))

    def test_read_write_float_none(self):
        mediafile = self._mediafile_fixture('full')
        mediafile.rg_track_gain = None
        mediafile.rg_track_peak = None
        mediafile.original_year = None
        mediafile.original_month = None
        mediafile.original_day = None
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.rg_track_gain, 0)
        self.assertEqual(mediafile.rg_track_peak, 0)
        self.assertEqual(mediafile.original_year, 0)
        self.assertEqual(mediafile.original_month, 0)
        self.assertEqual(mediafile.original_day, 0)

    def test_write_packed(self):
        mediafile = self._mediafile_fixture('empty')

        mediafile.tracktotal = 2
        mediafile.track = 1
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.track, 1)
        self.assertEqual(mediafile.tracktotal, 2)

    def test_write_counters_without_total(self):
        mediafile = self._mediafile_fixture('full')
        self.assertEqual(mediafile.track, 2)
        self.assertEqual(mediafile.tracktotal, 3)
        self.assertEqual(mediafile.disc, 4)
        self.assertEqual(mediafile.disctotal, 5)

        mediafile.track = 10
        mediafile.tracktotal = None
        mediafile.disc = 10
        mediafile.disctotal = None
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.track, 10)
        self.assertEqual(mediafile.tracktotal, 0)
        self.assertEqual(mediafile.disc, 10)
        self.assertEqual(mediafile.disctotal, 0)


    def assertTags(self, mediafile, tags):
        __unittest = True
        errors = []
        for key, value in tags.items():
            try:
                value2 = getattr(mediafile, key)
            except AttributeError:
                errors.append('Tag %s does not exist' % key)
            else:
                if value2 != value:
                    errors.append('Tag %s: %s != %s' %
                            (key, value2, value))
        if any(errors):
            errors = ['Tags did not match'] + errors
            self.fail('\n  '.join(errors))

    def _mediafile_fixture(self, name):
        name = name + '.' + self.extension
        src = os.path.join(_common.RSRC, name)
        target = os.path.join(self.temp_dir, name)
        shutil.copy(src, target)
        return MediaFile(target)

    def _generate_tags(self, base=None):
        """Make a dict of tags with correct values and consitent dates.
        """
        tags = {}
        if base is None:
            base = self.empty_tags

        for key, value in base.items():
            if key == 'art':
                tags[key] = self.jpg_data
            elif isinstance(value, unicode):
                tags[key] = 'value %s' % key
            elif isinstance(value, int):
                tags[key] = 1
            elif isinstance(value, float):
                tags[key] = 1.0
            elif isinstance(value, bool):
                tags[key] = True

        date = datetime.date(2001, 4, 3)
        tags['date'] = date
        tags['year'] = date.year
        tags['month'] = date.month
        tags['day'] = date.day

        original_date = datetime.date(1999, 5, 6)
        tags['original_date'] = original_date
        tags['original_year'] = original_date.year
        tags['original_month'] = original_date.month
        tags['original_day'] = original_date.day
        return tags


class PartialTestMixin(object):
    tags_without_total = {
        'track':      2,
        'tracktotal': 0,
        'disc':       4,
        'disctotal':  0,
    }

    def test_read_track_without_total(self):
        mediafile = self._mediafile_fixture('partial')
        self.assertEqual(mediafile.track, 2)
        self.assertEqual(mediafile.tracktotal, 0)
        self.assertEqual(mediafile.disc, 4)
        self.assertEqual(mediafile.disctotal, 0)


class GenreListTestMixin(object):
    """Tests access to the ``genres`` property as a list.
    """

    def test_read_genre_list(self):
        mediafile = self._mediafile_fixture('full')
        self.assertEqual(mediafile.genres, ['the genre'])

    def test_write_genre_list(self):
        mediafile = self._mediafile_fixture('empty')
        mediafile.genres = ['one', 'two']
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.genres, ['one', 'two'])

    def test_write_genre_list_get_first(self):
        mediafile = self._mediafile_fixture('empty')
        mediafile.genres = ['one', 'two']
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.genre, 'one')

    def test_append_genre_list(self):
        mediafile = self._mediafile_fixture('full')
        self.assertEqual(mediafile.genre, 'the genre')
        mediafile.genres += ['another']
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.genres, ['the genre', 'another'])


class MP3Test(ReadWriteTestBase, PartialTestMixin,
              GenreListTestMixin, unittest.TestCase):
    extension = 'mp3'
    audio_properties = {
        'length': 1.0,
        'bitrate': 80000,
        'format': 'MP3',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    }
class MP4Test(ReadWriteTestBase, PartialTestMixin,
              GenreListTestMixin, unittest.TestCase):
    extension = 'm4a'
    audio_properties = {
        'length': 1.0,
        'bitrate': 64000,
        'format': 'AAC',
        'samplerate': 44100,
        'bitdepth': 16,
        'channels': 2,
    }
class AlacTest(ReadWriteTestBase, GenreListTestMixin, unittest.TestCase):
    extension = 'alac.m4a'
    audio_properties = {
        'length': 1.0,
        'bitrate': 55072,
        'format': 'ALAC',
        'samplerate': 0,
        'bitdepth': 0,
        'channels': 0,
    }
class MusepackTest(ReadWriteTestBase, GenreListTestMixin, unittest.TestCase):
    extension = 'mpc'
    audio_properties = {
        'length': 1.0,
        'bitrate': 23458,
        'format': 'Musepack',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 2,
    }
class WMATest(ReadWriteTestBase, unittest.TestCase):
    extension = 'wma'
    audio_properties = {
        'length': 1.0,
        'bitrate': 128000,
        'format': 'Windows Media',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    }
class OggTest(ReadWriteTestBase, GenreListTestMixin, unittest.TestCase):
    extension = 'ogg'
    audio_properties = {
        'length': 1.0,
        'bitrate': 48000,
        'format': 'OGG',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    }
class FlacTest(ReadWriteTestBase, PartialTestMixin,
               GenreListTestMixin, unittest.TestCase):
    extension = 'flac'
    audio_properties = {
        'length': 1.0,
        'bitrate': 175120,
        'format': 'FLAC',
        'samplerate': 44100,
        'bitdepth': 16,
        'channels': 1,
    }
class ApeTest(ReadWriteTestBase, GenreListTestMixin, unittest.TestCase):
    extension = 'ape'
    audio_properties = {
        'length': 1.0,
        'bitrate': 112040,
        'format': 'APE',
        'samplerate': 44100,
        'bitdepth': 16,
        'channels': 1,
    }
class WavpackTest(ReadWriteTestBase, GenreListTestMixin, unittest.TestCase):
    extension = 'wv'
    audio_properties = {
        'length': 1.0,
        'bitrate': 108744,
        'format': 'WavPack',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    }
class OpusTest(ReadWriteTestBase, GenreListTestMixin, unittest.TestCase):
    extension = 'opus'
    audio_properties = {
        'length': 1.0,
        'bitrate': 57984,
        'format': 'Opus',
        'samplerate': 48000,
        'bitdepth': 0,
        'channels': 1,
    }


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
