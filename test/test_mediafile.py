# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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
from __future__ import division, absolute_import, print_function

import os
import shutil
import tempfile
import datetime
import time

from test import _common
from test._common import unittest
from beets.mediafile import MediaFile, MediaField, Image, \
    MP3DescStorageStyle, StorageStyle, MP4StorageStyle, \
    ASFStorageStyle, ImageType, CoverArtField
from beets.library import Item
from beets.plugins import BeetsPlugin


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

    @property
    def tiff_data(self):
        if not self._jpg_data:
            with open(os.path.join(_common.RSRC, 'image-2x3.tiff'), 'rb') as f:
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

    def test_delete_art(self):
        mediafile = self._mediafile_fixture('empty')
        mediafile.art = self.jpg_data
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertIsNotNone(mediafile.art)

        del mediafile.art
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertIsNone(mediafile.art)


class ImageStructureTestMixin(ArtTestMixin):
    """Test reading and writing multiple image tags.

    The tests use the `image` media file fixture. The tags of these files
    include two images, on in the PNG format, the other in JPEG format. If
    the tag format supports it they also include additional metadata.
    """

    def test_read_image_structures(self):
        mediafile = self._mediafile_fixture('image')

        self.assertEqual(len(mediafile.images), 2)

        image = next(i for i in mediafile.images
                     if i.mime_type == 'image/png')
        self.assertEqual(image.data, self.png_data)
        self.assertExtendedImageAttributes(image, desc=u'album cover',
                                           type=ImageType.front)

        image = next(i for i in mediafile.images
                     if i.mime_type == 'image/jpeg')
        self.assertEqual(image.data, self.jpg_data)
        self.assertExtendedImageAttributes(image, desc=u'the artist',
                                           type=ImageType.artist)

    def test_set_image_structure(self):
        mediafile = self._mediafile_fixture('empty')
        image = Image(data=self.png_data, desc=u'album cover',
                      type=ImageType.front)
        mediafile.images = [image]
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(len(mediafile.images), 1)

        image = mediafile.images[0]
        self.assertEqual(image.data, self.png_data)
        self.assertEqual(image.mime_type, 'image/png')
        self.assertExtendedImageAttributes(image, desc=u'album cover',
                                           type=ImageType.front)

    def test_add_image_structure(self):
        mediafile = self._mediafile_fixture('image')
        self.assertEqual(len(mediafile.images), 2)

        image = Image(data=self.png_data, desc=u'the composer',
                      type=ImageType.composer)
        mediafile.images += [image]
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(len(mediafile.images), 3)

        images = (i for i in mediafile.images if i.desc == u'the composer')
        image = next(images, None)
        self.assertExtendedImageAttributes(
            image, desc=u'the composer', type=ImageType.composer
        )

    def test_delete_image_structures(self):
        mediafile = self._mediafile_fixture('image')
        self.assertEqual(len(mediafile.images), 2)

        del mediafile.images
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(len(mediafile.images), 0)

    def test_guess_cover(self):
        mediafile = self._mediafile_fixture('image')
        self.assertEqual(len(mediafile.images), 2)
        cover = CoverArtField.guess_cover_image(mediafile.images)
        self.assertEqual(cover.desc, u'album cover')
        self.assertEqual(mediafile.art, cover.data)

    def assertExtendedImageAttributes(self, image, **kwargs):  # noqa
        """Ignore extended image attributes in the base tests.
        """
        pass


class ExtendedImageStructureTestMixin(ImageStructureTestMixin):
    """Checks for additional attributes in the image structure."""

    def assertExtendedImageAttributes(self, image, desc=None, type=None):  # noqa
        self.assertEqual(image.desc, desc)
        self.assertEqual(image.type, type)

    def test_add_tiff_image(self):
        mediafile = self._mediafile_fixture('image')
        self.assertEqual(len(mediafile.images), 2)

        image = Image(data=self.tiff_data, desc=u'the composer',
                      type=ImageType.composer)
        mediafile.images += [image]
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(len(mediafile.images), 3)

        # WMA does not preserve the order, so we have to work around this
        image = filter(lambda i: i.mime_type == 'image/tiff',
                       mediafile.images)[0]
        self.assertExtendedImageAttributes(
            image, desc=u'the composer', type=ImageType.composer)


class LazySaveTestMixin(object):
    """Mediafile should only write changes when tags have changed
    """

    @unittest.skip(u'not yet implemented')
    def test_unmodified(self):
        mediafile = self._mediafile_fixture('full')
        mtime = self._set_past_mtime(mediafile.path)
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

        mediafile.save()
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

    @unittest.skip(u'not yet implemented')
    def test_same_tag_value(self):
        mediafile = self._mediafile_fixture('full')
        mtime = self._set_past_mtime(mediafile.path)
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

        mediafile.title = mediafile.title
        mediafile.save()
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

    def test_update_same_tag_value(self):
        mediafile = self._mediafile_fixture('full')
        mtime = self._set_past_mtime(mediafile.path)
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

        mediafile.update({'title': mediafile.title})
        mediafile.save()
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

    @unittest.skip(u'not yet implemented')
    def test_tag_value_change(self):
        mediafile = self._mediafile_fixture('full')
        mtime = self._set_past_mtime(mediafile.path)
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

        mediafile.title = mediafile.title
        mediafile.album = u'another'
        mediafile.save()
        self.assertNotEqual(os.stat(mediafile.path).st_mtime, mtime)

    def test_update_changed_tag_value(self):
        mediafile = self._mediafile_fixture('full')
        mtime = self._set_past_mtime(mediafile.path)
        self.assertEqual(os.stat(mediafile.path).st_mtime, mtime)

        mediafile.update({'title': mediafile.title, 'album': u'another'})
        mediafile.save()
        self.assertNotEqual(os.stat(mediafile.path).st_mtime, mtime)

    def _set_past_mtime(self, path):
        mtime = round(time.time() - 10000)
        os.utime(path, (mtime, mtime))
        return mtime


class GenreListTestMixin(object):
    """Tests access to the ``genres`` property as a list.
    """

    def test_read_genre_list(self):
        mediafile = self._mediafile_fixture('full')
        self.assertItemsEqual(mediafile.genres, ['the genre'])

    def test_write_genre_list(self):
        mediafile = self._mediafile_fixture('empty')
        mediafile.genres = [u'one', u'two']
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertItemsEqual(mediafile.genres, [u'one', u'two'])

    def test_write_genre_list_get_first(self):
        mediafile = self._mediafile_fixture('empty')
        mediafile.genres = [u'one', u'two']
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.genre, u'one')

    def test_append_genre_list(self):
        mediafile = self._mediafile_fixture('full')
        self.assertEqual(mediafile.genre, u'the genre')
        mediafile.genres += [u'another']
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertItemsEqual(mediafile.genres, [u'the genre', u'another'])


field_extension = MediaField(
    MP3DescStorageStyle(b'customtag'),
    MP4StorageStyle(b'----:com.apple.iTunes:customtag'),
    StorageStyle(b'customtag'),
    ASFStorageStyle(b'customtag'),
)


class ExtendedFieldTestMixin(object):

    def test_extended_field_write(self):
        plugin = BeetsPlugin()
        plugin.add_media_field('customtag', field_extension)

        mediafile = self._mediafile_fixture('empty')
        mediafile.customtag = u'F#'
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.customtag, u'F#')
        delattr(MediaFile, 'customtag')
        Item._media_fields.remove('customtag')

    def test_write_extended_tag_from_item(self):
        plugin = BeetsPlugin()
        plugin.add_media_field('customtag', field_extension)

        mediafile = self._mediafile_fixture('empty')
        self.assertIsNone(mediafile.customtag)

        item = Item(path=mediafile.path, customtag=u'Gb')
        item.write()
        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.customtag, u'Gb')

        delattr(MediaFile, 'customtag')
        Item._media_fields.remove('customtag')

    def test_read_flexible_attribute_from_file(self):
        plugin = BeetsPlugin()
        plugin.add_media_field('customtag', field_extension)

        mediafile = self._mediafile_fixture('empty')
        mediafile.update({'customtag': u'F#'})
        mediafile.save()

        item = Item.from_path(mediafile.path)
        self.assertEqual(item['customtag'], u'F#')

        delattr(MediaFile, 'customtag')
        Item._media_fields.remove('customtag')

    def test_invalid_descriptor(self):
        with self.assertRaises(ValueError) as cm:
            MediaFile.add_field('somekey', True)
        self.assertIn(u'must be an instance of MediaField',
                      unicode(cm.exception))

    def test_overwrite_property(self):
        with self.assertRaises(ValueError) as cm:
            MediaFile.add_field('artist', MediaField())
        self.assertIn(u'property "artist" already exists',
                      unicode(cm.exception))


class ReadWriteTestBase(ArtTestMixin, GenreListTestMixin,
                        ExtendedFieldTestMixin):
    """Test writing and reading tags. Subclasses must set ``extension`` and
    ``audio_properties``.
    """

    full_initial_tags = {
        'title':       u'full',
        'artist':      u'the artist',
        'album':       u'the album',
        'genre':       u'the genre',
        'composer':    u'the composer',
        'grouping':    u'the grouping',
        'year':        2001,
        'month':       None,
        'day':         None,
        'date':        datetime.date(2001, 1, 1),
        'track':       2,
        'tracktotal':  3,
        'disc':        4,
        'disctotal':   5,
        'lyrics':      u'the lyrics',
        'comments':    u'the comments',
        'bpm':         6,
        'comp':        True,
        'mb_trackid':  '8b882575-08a5-4452-a7a7-cbb8a1531f9e',
        'mb_albumid':  '9e873859-8aa4-4790-b985-5a953e8ef628',
        'mb_artistid': '7cf0ea9d-86b9-4dad-ba9e-2355a64899ea',
        'art':         None,
        'label':       u'the label',
    }

    tag_fields = [
        'title',
        'artist',
        'album',
        'genre',
        'composer',
        'grouping',
        'year',
        'month',
        'day',
        'date',
        'track',
        'tracktotal',
        'disc',
        'disctotal',
        'lyrics',
        'comments',
        'bpm',
        'comp',
        'mb_trackid',
        'mb_albumid',
        'mb_artistid',
        'art',
        'label',
        'rg_track_peak',
        'rg_track_gain',
        'rg_album_peak',
        'rg_album_gain',
        'albumartist',
        'mb_albumartistid',
        'artist_sort',
        'albumartist_sort',
        'acoustid_fingerprint',
        'acoustid_id',
        'mb_releasegroupid',
        'asin',
        'catalognum',
        'disctitle',
        'script',
        'language',
        'country',
        'albumstatus',
        'media',
        'albumdisambig',
        'artist_credit',
        'albumartist_credit',
        'original_year',
        'original_month',
        'original_day',
        'original_date',
        'initial_key',
    ]

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_read_audio_properties(self):
        mediafile = self._mediafile_fixture('full')
        for key, value in self.audio_properties.items():
            if isinstance(value, float):
                self.assertAlmostEqual(getattr(mediafile, key), value,
                                       delta=0.1)
            else:
                self.assertEqual(getattr(mediafile, key), value)

    def test_read_full(self):
        mediafile = self._mediafile_fixture('full')
        self.assertTags(mediafile, self.full_initial_tags)

    def test_read_empty(self):
        mediafile = self._mediafile_fixture('empty')
        for field in self.tag_fields:
            self.assertIsNone(getattr(mediafile, field))

    def test_write_empty(self):
        mediafile = self._mediafile_fixture('empty')
        tags = self._generate_tags()

        for key, value in tags.items():
            setattr(mediafile, key, value)
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertTags(mediafile, tags)

    def test_update_empty(self):
        mediafile = self._mediafile_fixture('empty')
        tags = self._generate_tags()

        mediafile.update(tags)
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

    def test_update_full(self):
        mediafile = self._mediafile_fixture('full')
        tags = self._generate_tags()

        mediafile.update(tags)
        mediafile.save()
        # Make sure the tags are already set when writing a second time
        mediafile.update(tags)
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
        self.assertEqual(mediafile.date, datetime.date(2001, 1, 2))
        self.assertEqual(mediafile.original_year, 1999)
        self.assertEqual(mediafile.original_month, 12)
        self.assertEqual(mediafile.original_day, 30)
        self.assertEqual(mediafile.original_date, datetime.date(1999, 12, 30))

    def test_write_incomplete_date_components(self):
        mediafile = self._mediafile_fixture('empty')
        mediafile.year = 2001
        mediafile.month = None
        mediafile.day = 2
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.year, 2001)
        self.assertIsNone(mediafile.month)
        self.assertIsNone(mediafile.day)
        self.assertEqual(mediafile.date, datetime.date(2001, 1, 1))

    def test_write_dates(self):
        mediafile = self._mediafile_fixture('full')
        mediafile.date = datetime.date(2001, 1, 2)
        mediafile.original_date = datetime.date(1999, 12, 30)
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.year, 2001)
        self.assertEqual(mediafile.month, 1)
        self.assertEqual(mediafile.day, 2)
        self.assertEqual(mediafile.date, datetime.date(2001, 1, 2))
        self.assertEqual(mediafile.original_year, 1999)
        self.assertEqual(mediafile.original_month, 12)
        self.assertEqual(mediafile.original_day, 30)
        self.assertEqual(mediafile.original_date, datetime.date(1999, 12, 30))

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
        delattr(mediafile, 'tracktotal')
        mediafile.disc = 10
        delattr(mediafile, 'disctotal')
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.track, 10)
        self.assertEqual(mediafile.tracktotal, None)
        self.assertEqual(mediafile.disc, 10)
        self.assertEqual(mediafile.disctotal, None)

    def test_unparseable_date(self):
        mediafile = self._mediafile_fixture('unparseable')

        self.assertIsNone(mediafile.date)
        self.assertIsNone(mediafile.year)
        self.assertIsNone(mediafile.month)
        self.assertIsNone(mediafile.day)

    def test_delete_tag(self):
        mediafile = self._mediafile_fixture('full')

        keys = self.full_initial_tags.keys()
        for key in set(keys) - set(['art', 'month', 'day']):
            self.assertIsNotNone(getattr(mediafile, key))
        for key in keys:
            delattr(mediafile, key)
        mediafile.save()
        mediafile = MediaFile(mediafile.path)

        for key in keys:
            self.assertIsNone(getattr(mediafile, key))

    def test_delete_packed_total(self):
        mediafile = self._mediafile_fixture('full')

        delattr(mediafile, 'tracktotal')
        delattr(mediafile, 'disctotal')

        mediafile.save()
        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.track, self.full_initial_tags['track'])
        self.assertEqual(mediafile.disc, self.full_initial_tags['disc'])

    def test_delete_partial_date(self):
        mediafile = self._mediafile_fixture('empty')

        mediafile.date = datetime.date(2001, 12, 3)
        mediafile.save()
        mediafile = MediaFile(mediafile.path)
        self.assertIsNotNone(mediafile.date)
        self.assertIsNotNone(mediafile.year)
        self.assertIsNotNone(mediafile.month)
        self.assertIsNotNone(mediafile.day)

        delattr(mediafile, 'month')
        mediafile.save()
        mediafile = MediaFile(mediafile.path)
        self.assertIsNotNone(mediafile.date)
        self.assertIsNotNone(mediafile.year)
        self.assertIsNone(mediafile.month)
        self.assertIsNone(mediafile.day)

    def test_delete_year(self):
        mediafile = self._mediafile_fixture('full')

        self.assertIsNotNone(mediafile.date)
        self.assertIsNotNone(mediafile.year)

        delattr(mediafile, 'year')
        mediafile.save()
        mediafile = MediaFile(mediafile.path)
        self.assertIsNone(mediafile.date)
        self.assertIsNone(mediafile.year)

    def assertTags(self, mediafile, tags):  # noqa
        errors = []
        for key, value in tags.items():
            try:
                value2 = getattr(mediafile, key)
            except AttributeError:
                errors.append(u'Tag %s does not exist' % key)
            else:
                if value2 != value:
                    errors.append(u'Tag %s: %r != %r' % (key, value2, value))
        if any(errors):
            errors = [u'Tags did not match'] + errors
            self.fail('\n  '.join(errors))

    def _mediafile_fixture(self, name):
        name = name + '.' + self.extension
        src = os.path.join(_common.RSRC, name)
        target = os.path.join(self.temp_dir, name)
        shutil.copy(src, target)
        return MediaFile(target)

    def _generate_tags(self, base=None):
        """Return dictionary of tags, mapping tag names to values.
        """
        tags = {}

        for key in self.tag_fields:
            if key.startswith('rg_'):
                # ReplayGain is float
                tags[key] = 1.0
            else:
                tags[key] = b'value\u2010%s' % key

        for key in ['disc', 'disctotal', 'track', 'tracktotal', 'bpm']:
            tags[key] = 1

        tags['art'] = self.jpg_data
        tags['comp'] = True

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
        self.assertIsNone(mediafile.tracktotal)
        self.assertEqual(mediafile.disc, 4)
        self.assertIsNone(mediafile.disctotal)


class MP3Test(ReadWriteTestBase, PartialTestMixin,
              ExtendedImageStructureTestMixin,
              unittest.TestCase):
    extension = 'mp3'
    audio_properties = {
        'length': 1.0,
        'bitrate': 80000,
        'format': 'MP3',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    }

    def test_unknown_apic_type(self):
        mediafile = self._mediafile_fixture('image_unknown_type')
        self.assertEqual(mediafile.images[0].type, ImageType.other)


class MP4Test(ReadWriteTestBase, PartialTestMixin,
              ImageStructureTestMixin, unittest.TestCase):
    extension = 'm4a'
    audio_properties = {
        'length': 1.0,
        'bitrate': 64000,
        'format': 'AAC',
        'samplerate': 44100,
        'bitdepth': 16,
        'channels': 2,
    }

    def test_add_tiff_image_fails(self):
        mediafile = self._mediafile_fixture('empty')
        with self.assertRaises(ValueError):
            mediafile.images = [Image(data=self.tiff_data)]

    def test_guess_cover(self):
        # There is no metadata associated with images, we pick one at random
        pass


class AlacTest(ReadWriteTestBase, unittest.TestCase):
    extension = 'alac.m4a'
    audio_properties = {
        'length': 1.0,
        'bitrate': 21830,
        # 'format': 'ALAC',
        'samplerate': 44100,
        'bitdepth': 16,
        'channels': 1,
    }


class MusepackTest(ReadWriteTestBase, unittest.TestCase):
    extension = 'mpc'
    audio_properties = {
        'length': 1.0,
        'bitrate': 23458,
        'format': u'Musepack',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 2,
    }


class WMATest(ReadWriteTestBase, ExtendedImageStructureTestMixin,
              unittest.TestCase):
    extension = 'wma'
    audio_properties = {
        'length': 1.0,
        'bitrate': 128000,
        'format': u'Windows Media',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    }

    def test_write_genre_list_get_first(self):
        # WMA does not preserve list order
        mediafile = self._mediafile_fixture('empty')
        mediafile.genres = [u'one', u'two']
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertIn(mediafile.genre, [u'one', u'two'])

    def test_read_pure_tags(self):
        mediafile = self._mediafile_fixture('pure')
        self.assertEqual(mediafile.comments, u'the comments')
        self.assertEqual(mediafile.title, u'the title')
        self.assertEqual(mediafile.artist, u'the artist')


class OggTest(ReadWriteTestBase, ExtendedImageStructureTestMixin,
              unittest.TestCase):
    extension = 'ogg'
    audio_properties = {
        'length': 1.0,
        'bitrate': 48000,
        'format': u'OGG',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    }

    def test_read_date_from_year_tag(self):
        mediafile = self._mediafile_fixture('year')
        self.assertEqual(mediafile.year, 2000)
        self.assertEqual(mediafile.date, datetime.date(2000, 1, 1))

    def test_write_date_to_year_tag(self):
        mediafile = self._mediafile_fixture('empty')
        mediafile.year = 2000
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertEqual(mediafile.mgfile['YEAR'], [u'2000'])

    def test_legacy_coverart_tag(self):
        mediafile = self._mediafile_fixture('coverart')
        self.assertTrue('coverart' in mediafile.mgfile)
        self.assertEqual(mediafile.art, self.png_data)

        mediafile.art = self.png_data
        mediafile.save()

        mediafile = MediaFile(mediafile.path)
        self.assertFalse('coverart' in mediafile.mgfile)

    def test_date_tag_with_slashes(self):
        mediafile = self._mediafile_fixture('date_with_slashes')
        self.assertEqual(mediafile.year, 2005)
        self.assertEqual(mediafile.month, 6)
        self.assertEqual(mediafile.day, 5)


class FlacTest(ReadWriteTestBase, PartialTestMixin,
               ExtendedImageStructureTestMixin,
               unittest.TestCase):
    extension = 'flac'
    audio_properties = {
        'length': 1.0,
        'bitrate': 175120,
        'format': u'FLAC',
        'samplerate': 44100,
        'bitdepth': 16,
        'channels': 1,
    }


class ApeTest(ReadWriteTestBase, ExtendedImageStructureTestMixin,
              unittest.TestCase):
    extension = 'ape'
    audio_properties = {
        'length': 1.0,
        'bitrate': 112040,
        'format': u'APE',
        'samplerate': 44100,
        'bitdepth': 16,
        'channels': 1,
    }


class WavpackTest(ReadWriteTestBase, unittest.TestCase):
    extension = 'wv'
    audio_properties = {
        'length': 1.0,
        'bitrate': 108744,
        'format': u'WavPack',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    }


class OpusTest(ReadWriteTestBase, unittest.TestCase):
    extension = 'opus'
    audio_properties = {
        'length': 1.0,
        'bitrate': 57984,
        'format': u'Opus',
        'samplerate': 48000,
        'bitdepth': 0,
        'channels': 1,
    }


class AIFFTest(ReadWriteTestBase, unittest.TestCase):
    extension = 'aiff'
    audio_properties = {
        'length': 1.0,
        'bitrate': 705600,
        'format': u'AIFF',
        'samplerate': 44100,
        'bitdepth': 0,
        'channels': 1,
    }


class MediaFieldTest(unittest.TestCase):

    def test_properties_from_fields(self):
        path = os.path.join(_common.RSRC, 'full.mp3')
        mediafile = MediaFile(path)
        for field in MediaFile.fields():
            self.assertTrue(hasattr(mediafile, field))

    def test_properties_from_readable_fields(self):
        path = os.path.join(_common.RSRC, 'full.mp3')
        mediafile = MediaFile(path)
        for field in MediaFile.readable_fields():
            self.assertTrue(hasattr(mediafile, field))

    def test_known_fields(self):
        fields = list(ReadWriteTestBase.tag_fields)
        fields.extend(('encoder', 'images', 'genres', 'albumtype'))
        self.assertItemsEqual(MediaFile.fields(), fields)

    def test_fields_in_readable_fields(self):
        readable = MediaFile.readable_fields()
        for field in MediaFile.fields():
            self.assertIn(field, readable)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
