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

"""Handles low-level interfacing for files' tags. Wraps Mutagen to
automatically detect file types and provide a unified interface for a
useful subset of music files' tags.

Usage:

    >>> f = MediaFile('Lucy.mp3')
    >>> f.title
    u'Lucy in the Sky with Diamonds'
    >>> f.artist = 'The Beatles'
    >>> f.save()

A field will always return a reasonable value of the correct type, even
if no tag is present. If no value is available, the value will be false
(e.g., zero or the empty string).

Internally ``MediaFile`` uses ``MediaField`` descriptors to access the
data from the tags. In turn ``MediaField`` uses a number of
``StorageStyle`` strategies to handle format specific logic.
"""
from __future__ import division, absolute_import, print_function

import mutagen
import mutagen.id3
import mutagen.mp4
import mutagen.flac
import mutagen.asf

import codecs
import datetime
import re
import base64
import binascii
import math
import struct
import imghdr
import os
import traceback
import enum
import logging
import six


__all__ = ['UnreadableFileError', 'FileTypeError', 'MediaFile']

log = logging.getLogger(__name__)

# Human-readable type names.
TYPES = {
    'mp3':  'MP3',
    'aac':  'AAC',
    'alac':  'ALAC',
    'ogg':  'OGG',
    'opus': 'Opus',
    'flac': 'FLAC',
    'ape':  'APE',
    'wv':   'WavPack',
    'mpc':  'Musepack',
    'asf':  'Windows Media',
    'aiff': 'AIFF',
    'dsf':  'DSD Stream File',
}

PREFERRED_IMAGE_EXTENSIONS = {'jpeg': 'jpg'}


# Exceptions.

class UnreadableFileError(Exception):
    """Mutagen is not able to extract information from the file.
    """
    def __init__(self, path, msg):
        Exception.__init__(self, msg if msg else repr(path))


class FileTypeError(UnreadableFileError):
    """Reading this type of file is not supported.

    If passed the `mutagen_type` argument this indicates that the
    mutagen type is not supported by `Mediafile`.
    """
    def __init__(self, path, mutagen_type=None):
        if mutagen_type is None:
            msg = repr(path)
        else:
            msg = u'{0}: of mutagen type {1}'.format(repr(path), mutagen_type)
        Exception.__init__(self, msg)


class MutagenError(UnreadableFileError):
    """Raised when Mutagen fails unexpectedly---probably due to a bug.
    """
    def __init__(self, path, mutagen_exc):
        msg = u'{0}: {1}'.format(repr(path), mutagen_exc)
        Exception.__init__(self, msg)


# Interacting with Mutagen.

def mutagen_call(action, path, func, *args, **kwargs):
    """Call a Mutagen function with appropriate error handling.

    `action` is a string describing what the function is trying to do,
    and `path` is the relevant filename. The rest of the arguments
    describe the callable to invoke.

    We require at least Mutagen 1.33, where `IOError` is *never* used,
    neither for internal parsing errors *nor* for ordinary IO error
    conditions such as a bad filename. Mutagen-specific parsing errors and IO
    errors are reraised as `UnreadableFileError`. Other exceptions
    raised inside Mutagen---i.e., bugs---are reraised as `MutagenError`.
    """
    try:
        return func(*args, **kwargs)
    except mutagen.MutagenError as exc:
        log.debug(u'%s failed: %s', action, six.text_type(exc))
        raise UnreadableFileError(path, six.text_type(exc))
    except Exception as exc:
        # Isolate bugs in Mutagen.
        log.debug(u'%s', traceback.format_exc())
        log.error(u'uncaught Mutagen exception in %s: %s', action, exc)
        raise MutagenError(path, exc)


# Utility.

def _safe_cast(out_type, val):
    """Try to covert val to out_type but never raise an exception. If
    the value can't be converted, then a sensible default value is
    returned. out_type should be bool, int, or unicode; otherwise, the
    value is just passed through.
    """
    if val is None:
        return None

    if out_type == int:
        if isinstance(val, int) or isinstance(val, float):
            # Just a number.
            return int(val)
        else:
            # Process any other type as a string.
            if not isinstance(val, six.string_types):
                val = six.text_type(val)
            # Get a number from the front of the string.
            val = re.match(r'[0-9]*', val.strip()).group(0)
            if not val:
                return 0
            else:
                return int(val)

    elif out_type == bool:
        try:
            # Should work for strings, bools, ints:
            return bool(int(val))
        except ValueError:
            return False

    elif out_type == six.text_type:
        if isinstance(val, bytes):
            return val.decode('utf-8', 'ignore')
        elif isinstance(val, six.text_type):
            return val
        else:
            return six.text_type(val)

    elif out_type == float:
        if isinstance(val, int) or isinstance(val, float):
            return float(val)
        else:
            if isinstance(val, bytes):
                val = val.decode('utf-8', 'ignore')
            else:
                val = six.text_type(val)
            match = re.match(r'[\+-]?([0-9]+\.?[0-9]*|[0-9]*\.[0-9]+)',
                             val.strip())
            if match:
                val = match.group(0)
                if val:
                    return float(val)
            return 0.0

    else:
        return val


# Image coding for ASF/WMA.

def _unpack_asf_image(data):
    """Unpack image data from a WM/Picture tag. Return a tuple
    containing the MIME type, the raw image data, a type indicator, and
    the image's description.

    This function is treated as "untrusted" and could throw all manner
    of exceptions (out-of-bounds, etc.). We should clean this up
    sometime so that the failure modes are well-defined.
    """
    type, size = struct.unpack_from('<bi', data)
    pos = 5
    mime = b''
    while data[pos:pos + 2] != b'\x00\x00':
        mime += data[pos:pos + 2]
        pos += 2
    pos += 2
    description = b''
    while data[pos:pos + 2] != b'\x00\x00':
        description += data[pos:pos + 2]
        pos += 2
    pos += 2
    image_data = data[pos:pos + size]
    return (mime.decode("utf-16-le"), image_data, type,
            description.decode("utf-16-le"))


def _pack_asf_image(mime, data, type=3, description=""):
    """Pack image data for a WM/Picture tag.
    """
    tag_data = struct.pack('<bi', type, len(data))
    tag_data += mime.encode("utf-16-le") + b'\x00\x00'
    tag_data += description.encode("utf-16-le") + b'\x00\x00'
    tag_data += data
    return tag_data


# iTunes Sound Check encoding.

def _sc_decode(soundcheck):
    """Convert a Sound Check bytestring value to a (gain, peak) tuple as
    used by ReplayGain.
    """
    # We decode binary data. If one of the formats gives us a text
    # string, interpret it as UTF-8.
    if isinstance(soundcheck, six.text_type):
        soundcheck = soundcheck.encode('utf-8')

    # SoundCheck tags consist of 10 numbers, each represented by 8
    # characters of ASCII hex preceded by a space.
    try:
        soundcheck = codecs.decode(soundcheck.replace(b' ', b''), 'hex')
        soundcheck = struct.unpack('!iiiiiiiiii', soundcheck)
    except (struct.error, TypeError, binascii.Error):
        # SoundCheck isn't in the format we expect, so return default
        # values.
        return 0.0, 0.0

    # SoundCheck stores absolute calculated/measured RMS value in an
    # unknown unit. We need to find the ratio of this measurement
    # compared to a reference value of 1000 to get our gain in dB. We
    # play it safe by using the larger of the two values (i.e., the most
    # attenuation).
    maxgain = max(soundcheck[:2])
    if maxgain > 0:
        gain = math.log10(maxgain / 1000.0) * -10
    else:
        # Invalid gain value found.
        gain = 0.0

    # SoundCheck stores peak values as the actual value of the sample,
    # and again separately for the left and right channels. We need to
    # convert this to a percentage of full scale, which is 32768 for a
    # 16 bit sample. Once again, we play it safe by using the larger of
    # the two values.
    peak = max(soundcheck[6:8]) / 32768.0

    return round(gain, 2), round(peak, 6)


def _sc_encode(gain, peak):
    """Encode ReplayGain gain/peak values as a Sound Check string.
    """
    # SoundCheck stores the peak value as the actual value of the
    # sample, rather than the percentage of full scale that RG uses, so
    # we do a simple conversion assuming 16 bit samples.
    peak *= 32768.0

    # SoundCheck stores absolute RMS values in some unknown units rather
    # than the dB values RG uses. We can calculate these absolute values
    # from the gain ratio using a reference value of 1000 units. We also
    # enforce the maximum value here, which is equivalent to about
    # -18.2dB.
    g1 = int(min(round((10 ** (gain / -10)) * 1000), 65534))
    # Same as above, except our reference level is 2500 units.
    g2 = int(min(round((10 ** (gain / -10)) * 2500), 65534))

    # The purpose of these values are unknown, but they also seem to be
    # unused so we just use zero.
    uk = 0
    values = (g1, g1, g2, g2, uk, uk, int(peak), int(peak), uk, uk)
    return (u' %08X' * 10) % values


# Cover art and other images.
def _imghdr_what_wrapper(data):
    """A wrapper around imghdr.what to account for jpeg files that can only be
    identified as such using their magic bytes
    See #1545
    See https://github.com/file/file/blob/master/magic/Magdir/jpeg#L12
    """
    # imghdr.what returns none for jpegs with only the magic bytes, so
    # _wider_test_jpeg is run in that case. It still returns None if it didn't
    # match such a jpeg file.
    return imghdr.what(None, h=data) or _wider_test_jpeg(data)


def _wider_test_jpeg(data):
    """Test for a jpeg file following the UNIX file implementation which
    uses the magic bytes rather than just looking for the bytes that
    represent 'JFIF' or 'EXIF' at a fixed position.
    """
    if data[:2] == b'\xff\xd8':
        return 'jpeg'


def image_mime_type(data):
    """Return the MIME type of the image data (a bytestring).
    """
    # This checks for a jpeg file with only the magic bytes (unrecognized by
    # imghdr.what). imghdr.what returns none for that type of file, so
    # _wider_test_jpeg is run in that case. It still returns None if it didn't
    # match such a jpeg file.
    kind = _imghdr_what_wrapper(data)
    if kind in ['gif', 'jpeg', 'png', 'tiff', 'bmp']:
        return 'image/{0}'.format(kind)
    elif kind == 'pgm':
        return 'image/x-portable-graymap'
    elif kind == 'pbm':
        return 'image/x-portable-bitmap'
    elif kind == 'ppm':
        return 'image/x-portable-pixmap'
    elif kind == 'xbm':
        return 'image/x-xbitmap'
    else:
        return 'image/x-{0}'.format(kind)


def image_extension(data):
    ext = _imghdr_what_wrapper(data)
    return PREFERRED_IMAGE_EXTENSIONS.get(ext, ext)


class ImageType(enum.Enum):
    """Indicates the kind of an `Image` stored in a file's tag.
    """
    other = 0
    icon = 1
    other_icon = 2
    front = 3
    back = 4
    leaflet = 5
    media = 6
    lead_artist = 7
    artist = 8
    conductor = 9
    group = 10
    composer = 11
    lyricist = 12
    recording_location = 13
    recording_session = 14
    performance = 15
    screen_capture = 16
    fish = 17
    illustration = 18
    artist_logo = 19
    publisher_logo = 20


class Image(object):
    """Structure representing image data and metadata that can be
    stored and retrieved from tags.

    The structure has four properties.
    * ``data``  The binary data of the image
    * ``desc``  An optional description of the image
    * ``type``  An instance of `ImageType` indicating the kind of image
    * ``mime_type`` Read-only property that contains the mime type of
                    the binary data
    """
    def __init__(self, data, desc=None, type=None):
        assert isinstance(data, bytes)
        if desc is not None:
            assert isinstance(desc, six.text_type)
        self.data = data
        self.desc = desc
        if isinstance(type, int):
            try:
                type = list(ImageType)[type]
            except IndexError:
                log.debug(u"ignoring unknown image type index %s", type)
                type = ImageType.other
        self.type = type

    @property
    def mime_type(self):
        if self.data:
            return image_mime_type(self.data)

    @property
    def type_index(self):
        if self.type is None:
            # This method is used when a tag format requires the type
            # index to be set, so we return "other" as the default value.
            return 0
        return self.type.value


# StorageStyle classes describe strategies for accessing values in
# Mutagen file objects.

class StorageStyle(object):
    """A strategy for storing a value for a certain tag format (or set
    of tag formats). This basic StorageStyle describes simple 1:1
    mapping from raw values to keys in a Mutagen file object; subclasses
    describe more sophisticated translations or format-specific access
    strategies.

    MediaFile uses a StorageStyle via three methods: ``get()``,
    ``set()``, and ``delete()``. It passes a Mutagen file object to
    each.

    Internally, the StorageStyle implements ``get()`` and ``set()``
    using two steps that may be overridden by subtypes. To get a value,
    the StorageStyle first calls ``fetch()`` to retrieve the value
    corresponding to a key and then ``deserialize()`` to convert the raw
    Mutagen value to a consumable Python value. Similarly, to set a
    field, we call ``serialize()`` to encode the value and then
    ``store()`` to assign the result into the Mutagen object.

    Each StorageStyle type has a class-level `formats` attribute that is
    a list of strings indicating the formats that the style applies to.
    MediaFile only uses StorageStyles that apply to the correct type for
    a given audio file.
    """

    formats = ['FLAC', 'OggOpus', 'OggTheora', 'OggSpeex', 'OggVorbis',
               'OggFlac', 'APEv2File', 'WavPack', 'Musepack', 'MonkeysAudio']
    """List of mutagen classes the StorageStyle can handle.
    """

    def __init__(self, key, as_type=six.text_type, suffix=None,
                 float_places=2):
        """Create a basic storage strategy. Parameters:

        - `key`: The key on the Mutagen file object used to access the
          field's data.
        - `as_type`: The Python type that the value is stored as
          internally (`unicode`, `int`, `bool`, or `bytes`).
        - `suffix`: When `as_type` is a string type, append this before
          storing the value.
        - `float_places`: When the value is a floating-point number and
          encoded as a string, the number of digits to store after the
          decimal point.
        """
        self.key = key
        self.as_type = as_type
        self.suffix = suffix
        self.float_places = float_places

        # Convert suffix to correct string type.
        if self.suffix and self.as_type is six.text_type \
           and not isinstance(self.suffix, six.text_type):
            self.suffix = self.suffix.decode('utf-8')

    # Getter.

    def get(self, mutagen_file):
        """Get the value for the field using this style.
        """
        return self.deserialize(self.fetch(mutagen_file))

    def fetch(self, mutagen_file):
        """Retrieve the raw value of for this tag from the Mutagen file
        object.
        """
        try:
            return mutagen_file[self.key][0]
        except (KeyError, IndexError):
            return None

    def deserialize(self, mutagen_value):
        """Given a raw value stored on a Mutagen object, decode and
        return the represented value.
        """
        if self.suffix and isinstance(mutagen_value, six.text_type) \
           and mutagen_value.endswith(self.suffix):
            return mutagen_value[:-len(self.suffix)]
        else:
            return mutagen_value

    # Setter.

    def set(self, mutagen_file, value):
        """Assign the value for the field using this style.
        """
        self.store(mutagen_file, self.serialize(value))

    def store(self, mutagen_file, value):
        """Store a serialized value in the Mutagen file object.
        """
        mutagen_file[self.key] = [value]

    def serialize(self, value):
        """Convert the external Python value to a type that is suitable for
        storing in a Mutagen file object.
        """
        if isinstance(value, float) and self.as_type is six.text_type:
            value = u'{0:.{1}f}'.format(value, self.float_places)
            value = self.as_type(value)
        elif self.as_type is six.text_type:
            if isinstance(value, bool):
                # Store bools as 1/0 instead of True/False.
                value = six.text_type(int(bool(value)))
            elif isinstance(value, bytes):
                value = value.decode('utf-8', 'ignore')
            else:
                value = six.text_type(value)
        else:
            value = self.as_type(value)

        if self.suffix:
            value += self.suffix

        return value

    def delete(self, mutagen_file):
        """Remove the tag from the file.
        """
        if self.key in mutagen_file:
            del mutagen_file[self.key]


class ListStorageStyle(StorageStyle):
    """Abstract storage style that provides access to lists.

    The ListMediaField descriptor uses a ListStorageStyle via two
    methods: ``get_list()`` and ``set_list()``. It passes a Mutagen file
    object to each.

    Subclasses may overwrite ``fetch`` and ``store``.  ``fetch`` must
    return a (possibly empty) list and ``store`` receives a serialized
    list of values as the second argument.

    The `serialize` and `deserialize` methods (from the base
    `StorageStyle`) are still called with individual values. This class
    handles packing and unpacking the values into lists.
    """
    def get(self, mutagen_file):
        """Get the first value in the field's value list.
        """
        try:
            return self.get_list(mutagen_file)[0]
        except IndexError:
            return None

    def get_list(self, mutagen_file):
        """Get a list of all values for the field using this style.
        """
        return [self.deserialize(item) for item in self.fetch(mutagen_file)]

    def fetch(self, mutagen_file):
        """Get the list of raw (serialized) values.
        """
        try:
            return mutagen_file[self.key]
        except KeyError:
            return []

    def set(self, mutagen_file, value):
        """Set an individual value as the only value for the field using
        this style.
        """
        self.set_list(mutagen_file, [value])

    def set_list(self, mutagen_file, values):
        """Set all values for the field using this style. `values`
        should be an iterable.
        """
        self.store(mutagen_file, [self.serialize(value) for value in values])

    def store(self, mutagen_file, values):
        """Set the list of all raw (serialized) values for this field.
        """
        mutagen_file[self.key] = values


class SoundCheckStorageStyleMixin(object):
    """A mixin for storage styles that read and write iTunes SoundCheck
    analysis values. The object must have an `index` field that
    indicates which half of the gain/peak pair---0 or 1---the field
    represents.
    """
    def get(self, mutagen_file):
        data = self.fetch(mutagen_file)
        if data is not None:
            return _sc_decode(data)[self.index]

    def set(self, mutagen_file, value):
        data = self.fetch(mutagen_file)
        if data is None:
            gain_peak = [0, 0]
        else:
            gain_peak = list(_sc_decode(data))
        gain_peak[self.index] = value or 0
        data = self.serialize(_sc_encode(*gain_peak))
        self.store(mutagen_file, data)


class ASFStorageStyle(ListStorageStyle):
    """A general storage style for Windows Media/ASF files.
    """
    formats = ['ASF']

    def deserialize(self, data):
        if isinstance(data, mutagen.asf.ASFBaseAttribute):
            data = data.value
        return data


class MP4StorageStyle(StorageStyle):
    """A general storage style for MPEG-4 tags.
    """
    formats = ['MP4']

    def serialize(self, value):
        value = super(MP4StorageStyle, self).serialize(value)
        if self.key.startswith('----:') and isinstance(value, six.text_type):
            value = value.encode('utf-8')
        return value


class MP4TupleStorageStyle(MP4StorageStyle):
    """A style for storing values as part of a pair of numbers in an
    MPEG-4 file.
    """
    def __init__(self, key, index=0, **kwargs):
        super(MP4TupleStorageStyle, self).__init__(key, **kwargs)
        self.index = index

    def deserialize(self, mutagen_value):
        items = mutagen_value or []
        packing_length = 2
        return list(items) + [0] * (packing_length - len(items))

    def get(self, mutagen_file):
        value = super(MP4TupleStorageStyle, self).get(mutagen_file)[self.index]
        if value == 0:
            # The values are always present and saved as integers. So we
            # assume that "0" indicates it is not set.
            return None
        else:
            return value

    def set(self, mutagen_file, value):
        if value is None:
            value = 0
        items = self.deserialize(self.fetch(mutagen_file))
        items[self.index] = int(value)
        self.store(mutagen_file, items)

    def delete(self, mutagen_file):
        if self.index == 0:
            super(MP4TupleStorageStyle, self).delete(mutagen_file)
        else:
            self.set(mutagen_file, None)


class MP4ListStorageStyle(ListStorageStyle, MP4StorageStyle):
    pass


class MP4SoundCheckStorageStyle(SoundCheckStorageStyleMixin, MP4StorageStyle):
    def __init__(self, key, index=0, **kwargs):
        super(MP4SoundCheckStorageStyle, self).__init__(key, **kwargs)
        self.index = index


class MP4BoolStorageStyle(MP4StorageStyle):
    """A style for booleans in MPEG-4 files. (MPEG-4 has an atom type
    specifically for representing booleans.)
    """
    def get(self, mutagen_file):
        try:
            return mutagen_file[self.key]
        except KeyError:
            return None

    def get_list(self, mutagen_file):
        raise NotImplementedError(u'MP4 bool storage does not support lists')

    def set(self, mutagen_file, value):
        mutagen_file[self.key] = value

    def set_list(self, mutagen_file, values):
        raise NotImplementedError(u'MP4 bool storage does not support lists')


class MP4ImageStorageStyle(MP4ListStorageStyle):
    """Store images as MPEG-4 image atoms. Values are `Image` objects.
    """
    def __init__(self, **kwargs):
        super(MP4ImageStorageStyle, self).__init__(key='covr', **kwargs)

    def deserialize(self, data):
        return Image(data)

    def serialize(self, image):
        if image.mime_type == 'image/png':
            kind = mutagen.mp4.MP4Cover.FORMAT_PNG
        elif image.mime_type == 'image/jpeg':
            kind = mutagen.mp4.MP4Cover.FORMAT_JPEG
        else:
            raise ValueError(u'MP4 files only supports PNG and JPEG images')
        return mutagen.mp4.MP4Cover(image.data, kind)


class MP3StorageStyle(StorageStyle):
    """Store data in ID3 frames.
    """
    formats = ['MP3', 'AIFF', 'DSF']

    def __init__(self, key, id3_lang=None, **kwargs):
        """Create a new ID3 storage style. `id3_lang` is the value for
        the language field of newly created frames.
        """
        self.id3_lang = id3_lang
        super(MP3StorageStyle, self).__init__(key, **kwargs)

    def fetch(self, mutagen_file):
        try:
            return mutagen_file[self.key].text[0]
        except (KeyError, IndexError):
            return None

    def store(self, mutagen_file, value):
        frame = mutagen.id3.Frames[self.key](encoding=3, text=[value])
        mutagen_file.tags.setall(self.key, [frame])


class MP3PeopleStorageStyle(MP3StorageStyle):
    """Store list of people in ID3 frames.
    """
    def __init__(self, key, involvement='', **kwargs):
        self.involvement = involvement
        super(MP3PeopleStorageStyle, self).__init__(key, **kwargs)

    def store(self, mutagen_file, value):
        frames = mutagen_file.tags.getall(self.key)

        # Try modifying in place.
        found = False
        for frame in frames:
            if frame.encoding == mutagen.id3.Encoding.UTF8:
                for pair in frame.people:
                    if pair[0].lower() == self.involvement.lower():
                        pair[1] = value
                        found = True

        # Try creating a new frame.
        if not found:
            frame = mutagen.id3.Frames[self.key](
                encoding=mutagen.id3.Encoding.UTF8,
                people=[[self.involvement, value]]
            )
            mutagen_file.tags.add(frame)

    def fetch(self, mutagen_file):
        for frame in mutagen_file.tags.getall(self.key):
            for pair in frame.people:
                if pair[0].lower() == self.involvement.lower():
                    try:
                        return pair[1]
                    except IndexError:
                        return None


class MP3ListStorageStyle(ListStorageStyle, MP3StorageStyle):
    """Store lists of data in multiple ID3 frames.
    """
    def fetch(self, mutagen_file):
        try:
            return mutagen_file[self.key].text
        except KeyError:
            return []

    def store(self, mutagen_file, values):
        frame = mutagen.id3.Frames[self.key](encoding=3, text=values)
        mutagen_file.tags.setall(self.key, [frame])


class MP3UFIDStorageStyle(MP3StorageStyle):
    """Store string data in a UFID ID3 frame with a particular owner.
    """
    def __init__(self, owner, **kwargs):
        self.owner = owner
        super(MP3UFIDStorageStyle, self).__init__('UFID:' + owner, **kwargs)

    def fetch(self, mutagen_file):
        try:
            return mutagen_file[self.key].data
        except KeyError:
            return None

    def store(self, mutagen_file, value):
        # This field type stores text data as encoded data.
        assert isinstance(value, six.text_type)
        value = value.encode('utf-8')

        frames = mutagen_file.tags.getall(self.key)
        for frame in frames:
            # Replace existing frame data.
            if frame.owner == self.owner:
                frame.data = value
        else:
            # New frame.
            frame = mutagen.id3.UFID(owner=self.owner, data=value)
            mutagen_file.tags.setall(self.key, [frame])


class MP3DescStorageStyle(MP3StorageStyle):
    """Store data in a TXXX (or similar) ID3 frame. The frame is
    selected based its ``desc`` field.
    """
    def __init__(self, desc=u'', key='TXXX', **kwargs):
        assert isinstance(desc, six.text_type)
        self.description = desc
        super(MP3DescStorageStyle, self).__init__(key=key, **kwargs)

    def store(self, mutagen_file, value):
        frames = mutagen_file.tags.getall(self.key)
        if self.key != 'USLT':
            value = [value]

        # Try modifying in place.
        found = False
        for frame in frames:
            if frame.desc.lower() == self.description.lower():
                frame.text = value
                frame.encoding = mutagen.id3.Encoding.UTF8
                found = True

        # Try creating a new frame.
        if not found:
            frame = mutagen.id3.Frames[self.key](
                desc=self.description,
                text=value,
                encoding=mutagen.id3.Encoding.UTF8,
            )
            if self.id3_lang:
                frame.lang = self.id3_lang
            mutagen_file.tags.add(frame)

    def fetch(self, mutagen_file):
        for frame in mutagen_file.tags.getall(self.key):
            if frame.desc.lower() == self.description.lower():
                if self.key == 'USLT':
                    return frame.text
                try:
                    return frame.text[0]
                except IndexError:
                    return None

    def delete(self, mutagen_file):
        found_frame = None
        for frame in mutagen_file.tags.getall(self.key):
            if frame.desc.lower() == self.description.lower():
                found_frame = frame
                break
        if found_frame is not None:
            del mutagen_file[frame.HashKey]


class MP3SlashPackStorageStyle(MP3StorageStyle):
    """Store value as part of pair that is serialized as a slash-
    separated string.
    """
    def __init__(self, key, pack_pos=0, **kwargs):
        super(MP3SlashPackStorageStyle, self).__init__(key, **kwargs)
        self.pack_pos = pack_pos

    def _fetch_unpacked(self, mutagen_file):
        data = self.fetch(mutagen_file)
        if data:
            items = six.text_type(data).split('/')
        else:
            items = []
        packing_length = 2
        return list(items) + [None] * (packing_length - len(items))

    def get(self, mutagen_file):
        return self._fetch_unpacked(mutagen_file)[self.pack_pos]

    def set(self, mutagen_file, value):
        items = self._fetch_unpacked(mutagen_file)
        items[self.pack_pos] = value
        if items[0] is None:
            items[0] = ''
        if items[1] is None:
            items.pop()  # Do not store last value
        self.store(mutagen_file, '/'.join(map(six.text_type, items)))

    def delete(self, mutagen_file):
        if self.pack_pos == 0:
            super(MP3SlashPackStorageStyle, self).delete(mutagen_file)
        else:
            self.set(mutagen_file, None)


class MP3ImageStorageStyle(ListStorageStyle, MP3StorageStyle):
    """Converts between APIC frames and ``Image`` instances.

    The `get_list` method inherited from ``ListStorageStyle`` returns a
    list of ``Image``s. Similarly, the `set_list` method accepts a
    list of ``Image``s as its ``values`` argument.
    """
    def __init__(self):
        super(MP3ImageStorageStyle, self).__init__(key='APIC')
        self.as_type = bytes

    def deserialize(self, apic_frame):
        """Convert APIC frame into Image."""
        return Image(data=apic_frame.data, desc=apic_frame.desc,
                     type=apic_frame.type)

    def fetch(self, mutagen_file):
        return mutagen_file.tags.getall(self.key)

    def store(self, mutagen_file, frames):
        mutagen_file.tags.setall(self.key, frames)

    def delete(self, mutagen_file):
        mutagen_file.tags.delall(self.key)

    def serialize(self, image):
        """Return an APIC frame populated with data from ``image``.
        """
        assert isinstance(image, Image)
        frame = mutagen.id3.Frames[self.key]()
        frame.data = image.data
        frame.mime = image.mime_type
        frame.desc = image.desc or u''

        # For compatibility with OS X/iTunes prefer latin-1 if possible.
        # See issue #899
        try:
            frame.desc.encode("latin-1")
        except UnicodeEncodeError:
            frame.encoding = mutagen.id3.Encoding.UTF16
        else:
            frame.encoding = mutagen.id3.Encoding.LATIN1

        frame.type = image.type_index
        return frame


class MP3SoundCheckStorageStyle(SoundCheckStorageStyleMixin,
                                MP3DescStorageStyle):
    def __init__(self, index=0, **kwargs):
        super(MP3SoundCheckStorageStyle, self).__init__(**kwargs)
        self.index = index


class ASFImageStorageStyle(ListStorageStyle):
    """Store images packed into Windows Media/ASF byte array attributes.
    Values are `Image` objects.
    """
    formats = ['ASF']

    def __init__(self):
        super(ASFImageStorageStyle, self).__init__(key='WM/Picture')

    def deserialize(self, asf_picture):
        mime, data, type, desc = _unpack_asf_image(asf_picture.value)
        return Image(data, desc=desc, type=type)

    def serialize(self, image):
        pic = mutagen.asf.ASFByteArrayAttribute()
        pic.value = _pack_asf_image(image.mime_type, image.data,
                                    type=image.type_index,
                                    description=image.desc or u'')
        return pic


class VorbisImageStorageStyle(ListStorageStyle):
    """Store images in Vorbis comments. Both legacy COVERART fields and
    modern METADATA_BLOCK_PICTURE tags are supported. Data is
    base64-encoded. Values are `Image` objects.
    """
    formats = ['OggOpus', 'OggTheora', 'OggSpeex', 'OggVorbis',
               'OggFlac']

    def __init__(self):
        super(VorbisImageStorageStyle, self).__init__(
            key='metadata_block_picture'
        )
        self.as_type = bytes

    def fetch(self, mutagen_file):
        images = []
        if 'metadata_block_picture' not in mutagen_file:
            # Try legacy COVERART tags.
            if 'coverart' in mutagen_file:
                for data in mutagen_file['coverart']:
                    images.append(Image(base64.b64decode(data)))
            return images
        for data in mutagen_file["metadata_block_picture"]:
            try:
                pic = mutagen.flac.Picture(base64.b64decode(data))
            except (TypeError, AttributeError):
                continue
            images.append(Image(data=pic.data, desc=pic.desc,
                                type=pic.type))
        return images

    def store(self, mutagen_file, image_data):
        # Strip all art, including legacy COVERART.
        if 'coverart' in mutagen_file:
            del mutagen_file['coverart']
        if 'coverartmime' in mutagen_file:
            del mutagen_file['coverartmime']
        super(VorbisImageStorageStyle, self).store(mutagen_file, image_data)

    def serialize(self, image):
        """Turn a Image into a base64 encoded FLAC picture block.
        """
        pic = mutagen.flac.Picture()
        pic.data = image.data
        pic.type = image.type_index
        pic.mime = image.mime_type
        pic.desc = image.desc or u''

        # Encoding with base64 returns bytes on both Python 2 and 3.
        # Mutagen requires the data to be a Unicode string, so we decode
        # it before passing it along.
        return base64.b64encode(pic.write()).decode('ascii')


class FlacImageStorageStyle(ListStorageStyle):
    """Converts between ``mutagen.flac.Picture`` and ``Image`` instances.
    """
    formats = ['FLAC']

    def __init__(self):
        super(FlacImageStorageStyle, self).__init__(key='')

    def fetch(self, mutagen_file):
        return mutagen_file.pictures

    def deserialize(self, flac_picture):
        return Image(data=flac_picture.data, desc=flac_picture.desc,
                     type=flac_picture.type)

    def store(self, mutagen_file, pictures):
        """``pictures`` is a list of mutagen.flac.Picture instances.
        """
        mutagen_file.clear_pictures()
        for pic in pictures:
            mutagen_file.add_picture(pic)

    def serialize(self, image):
        """Turn a Image into a mutagen.flac.Picture.
        """
        pic = mutagen.flac.Picture()
        pic.data = image.data
        pic.type = image.type_index
        pic.mime = image.mime_type
        pic.desc = image.desc or u''
        return pic

    def delete(self, mutagen_file):
        """Remove all images from the file.
        """
        mutagen_file.clear_pictures()


class APEv2ImageStorageStyle(ListStorageStyle):
    """Store images in APEv2 tags. Values are `Image` objects.
    """
    formats = ['APEv2File', 'WavPack', 'Musepack', 'MonkeysAudio', 'OptimFROG']

    TAG_NAMES = {
        ImageType.other: 'Cover Art (other)',
        ImageType.icon: 'Cover Art (icon)',
        ImageType.other_icon: 'Cover Art (other icon)',
        ImageType.front: 'Cover Art (front)',
        ImageType.back: 'Cover Art (back)',
        ImageType.leaflet: 'Cover Art (leaflet)',
        ImageType.media: 'Cover Art (media)',
        ImageType.lead_artist: 'Cover Art (lead)',
        ImageType.artist: 'Cover Art (artist)',
        ImageType.conductor: 'Cover Art (conductor)',
        ImageType.group: 'Cover Art (band)',
        ImageType.composer: 'Cover Art (composer)',
        ImageType.lyricist: 'Cover Art (lyricist)',
        ImageType.recording_location: 'Cover Art (studio)',
        ImageType.recording_session: 'Cover Art (recording)',
        ImageType.performance: 'Cover Art (performance)',
        ImageType.screen_capture: 'Cover Art (movie scene)',
        ImageType.fish: 'Cover Art (colored fish)',
        ImageType.illustration: 'Cover Art (illustration)',
        ImageType.artist_logo: 'Cover Art (band logo)',
        ImageType.publisher_logo: 'Cover Art (publisher logo)',
    }

    def __init__(self):
        super(APEv2ImageStorageStyle, self).__init__(key='')

    def fetch(self, mutagen_file):
        images = []
        for cover_type, cover_tag in self.TAG_NAMES.items():
            try:
                frame = mutagen_file[cover_tag]
                text_delimiter_index = frame.value.find(b'\x00')
                if text_delimiter_index > 0:
                    comment = frame.value[0:text_delimiter_index]
                    comment = comment.decode('utf-8', 'replace')
                else:
                    comment = None
                image_data = frame.value[text_delimiter_index + 1:]
                images.append(Image(data=image_data, type=cover_type,
                                    desc=comment))
            except KeyError:
                pass

        return images

    def set_list(self, mutagen_file, values):
        self.delete(mutagen_file)

        for image in values:
            image_type = image.type or ImageType.other
            comment = image.desc or ''
            image_data = comment.encode('utf-8') + b'\x00' + image.data
            cover_tag = self.TAG_NAMES[image_type]
            mutagen_file[cover_tag] = image_data

    def delete(self, mutagen_file):
        """Remove all images from the file.
        """
        for cover_tag in self.TAG_NAMES.values():
            try:
                del mutagen_file[cover_tag]
            except KeyError:
                pass


# MediaField is a descriptor that represents a single logical field. It
# aggregates several StorageStyles describing how to access the data for
# each file type.

class MediaField(object):
    """A descriptor providing access to a particular (abstract) metadata
    field.
    """
    def __init__(self, *styles, **kwargs):
        """Creates a new MediaField.

        :param styles: `StorageStyle` instances that describe the strategy
                       for reading and writing the field in particular
                       formats. There must be at least one style for
                       each possible file format.

        :param out_type: the type of the value that should be returned when
                         getting this property.

        """
        self.out_type = kwargs.get('out_type', six.text_type)
        self._styles = styles

    def styles(self, mutagen_file):
        """Yields the list of storage styles of this field that can
        handle the MediaFile's format.
        """
        for style in self._styles:
            if mutagen_file.__class__.__name__ in style.formats:
                yield style

    def __get__(self, mediafile, owner=None):
        out = None
        for style in self.styles(mediafile.mgfile):
            out = style.get(mediafile.mgfile)
            if out:
                break
        return _safe_cast(self.out_type, out)

    def __set__(self, mediafile, value):
        if value is None:
            value = self._none_value()
        for style in self.styles(mediafile.mgfile):
            style.set(mediafile.mgfile, value)

    def __delete__(self, mediafile):
        for style in self.styles(mediafile.mgfile):
            style.delete(mediafile.mgfile)

    def _none_value(self):
        """Get an appropriate "null" value for this field's type. This
        is used internally when setting the field to None.
        """
        if self.out_type == int:
            return 0
        elif self.out_type == float:
            return 0.0
        elif self.out_type == bool:
            return False
        elif self.out_type == six.text_type:
            return u''


class ListMediaField(MediaField):
    """Property descriptor that retrieves a list of multiple values from
    a tag.

    Uses ``get_list`` and set_list`` methods of its ``StorageStyle``
    strategies to do the actual work.
    """
    def __get__(self, mediafile, _):
        values = []
        for style in self.styles(mediafile.mgfile):
            values.extend(style.get_list(mediafile.mgfile))
        return [_safe_cast(self.out_type, value) for value in values]

    def __set__(self, mediafile, values):
        for style in self.styles(mediafile.mgfile):
            style.set_list(mediafile.mgfile, values)

    def single_field(self):
        """Returns a ``MediaField`` descriptor that gets and sets the
        first item.
        """
        options = {'out_type': self.out_type}
        return MediaField(*self._styles, **options)


class DateField(MediaField):
    """Descriptor that handles serializing and deserializing dates

    The getter parses value from tags into a ``datetime.date`` instance
    and setter serializes such an instance into a string.

    For granular access to year, month, and day, use the ``*_field``
    methods to create corresponding `DateItemField`s.
    """
    def __init__(self, *date_styles, **kwargs):
        """``date_styles`` is a list of ``StorageStyle``s to store and
        retrieve the whole date from. The ``year`` option is an
        additional list of fallback styles for the year. The year is
        always set on this style, but is only retrieved if the main
        storage styles do not return a value.
        """
        super(DateField, self).__init__(*date_styles)
        year_style = kwargs.get('year', None)
        if year_style:
            self._year_field = MediaField(*year_style)

    def __get__(self, mediafile, owner=None):
        year, month, day = self._get_date_tuple(mediafile)
        if not year:
            return None
        try:
            return datetime.date(
                year,
                month or 1,
                day or 1
            )
        except ValueError:  # Out of range values.
            return None

    def __set__(self, mediafile, date):
        if date is None:
            self._set_date_tuple(mediafile, None, None, None)
        else:
            self._set_date_tuple(mediafile, date.year, date.month, date.day)

    def __delete__(self, mediafile):
        super(DateField, self).__delete__(mediafile)
        if hasattr(self, '_year_field'):
            self._year_field.__delete__(mediafile)

    def _get_date_tuple(self, mediafile):
        """Get a 3-item sequence representing the date consisting of a
        year, month, and day number. Each number is either an integer or
        None.
        """
        # Get the underlying data and split on hyphens and slashes.
        datestring = super(DateField, self).__get__(mediafile, None)
        if isinstance(datestring, six.string_types):
            datestring = re.sub(r'[Tt ].*$', '', six.text_type(datestring))
            items = re.split('[-/]', six.text_type(datestring))
        else:
            items = []

        # Ensure that we have exactly 3 components, possibly by
        # truncating or padding.
        items = items[:3]
        if len(items) < 3:
            items += [None] * (3 - len(items))

        # Use year field if year is missing.
        if not items[0] and hasattr(self, '_year_field'):
            items[0] = self._year_field.__get__(mediafile)

        # Convert each component to an integer if possible.
        items_ = []
        for item in items:
            try:
                items_.append(int(item))
            except (TypeError, ValueError):
                items_.append(None)
        return items_

    def _set_date_tuple(self, mediafile, year, month=None, day=None):
        """Set the value of the field given a year, month, and day
        number. Each number can be an integer or None to indicate an
        unset component.
        """
        if year is None:
            self.__delete__(mediafile)
            return

        date = [u'{0:04d}'.format(int(year))]
        if month:
            date.append(u'{0:02d}'.format(int(month)))
        if month and day:
            date.append(u'{0:02d}'.format(int(day)))
        date = map(six.text_type, date)
        super(DateField, self).__set__(mediafile, u'-'.join(date))

        if hasattr(self, '_year_field'):
            self._year_field.__set__(mediafile, year)

    def year_field(self):
        return DateItemField(self, 0)

    def month_field(self):
        return DateItemField(self, 1)

    def day_field(self):
        return DateItemField(self, 2)


class DateItemField(MediaField):
    """Descriptor that gets and sets constituent parts of a `DateField`:
    the month, day, or year.
    """
    def __init__(self, date_field, item_pos):
        self.date_field = date_field
        self.item_pos = item_pos

    def __get__(self, mediafile, _):
        return self.date_field._get_date_tuple(mediafile)[self.item_pos]

    def __set__(self, mediafile, value):
        items = self.date_field._get_date_tuple(mediafile)
        items[self.item_pos] = value
        self.date_field._set_date_tuple(mediafile, *items)

    def __delete__(self, mediafile):
        self.__set__(mediafile, None)


class CoverArtField(MediaField):
    """A descriptor that provides access to the *raw image data* for the
    cover image on a file. This is used for backwards compatibility: the
    full `ImageListField` provides richer `Image` objects.

    When there are multiple images we try to pick the most likely to be a front
    cover.
    """
    def __init__(self):
        pass

    def __get__(self, mediafile, _):
        candidates = mediafile.images
        if candidates:
            return self.guess_cover_image(candidates).data
        else:
            return None

    @staticmethod
    def guess_cover_image(candidates):
        if len(candidates) == 1:
            return candidates[0]
        try:
            return next(c for c in candidates if c.type == ImageType.front)
        except StopIteration:
            return candidates[0]

    def __set__(self, mediafile, data):
        if data:
            mediafile.images = [Image(data=data)]
        else:
            mediafile.images = []

    def __delete__(self, mediafile):
        delattr(mediafile, 'images')


class ImageListField(ListMediaField):
    """Descriptor to access the list of images embedded in tags.

    The getter returns a list of `Image` instances obtained from
    the tags. The setter accepts a list of `Image` instances to be
    written to the tags.
    """
    def __init__(self):
        # The storage styles used here must implement the
        # `ListStorageStyle` interface and get and set lists of
        # `Image`s.
        super(ImageListField, self).__init__(
            MP3ImageStorageStyle(),
            MP4ImageStorageStyle(),
            ASFImageStorageStyle(),
            VorbisImageStorageStyle(),
            FlacImageStorageStyle(),
            APEv2ImageStorageStyle(),
            out_type=Image,
        )


# MediaFile is a collection of fields.

class MediaFile(object):
    """Represents a multimedia file on disk and provides access to its
    metadata.
    """
    def __init__(self, path, id3v23=False):
        """Constructs a new `MediaFile` reflecting the file at path. May
        throw `UnreadableFileError`.

        By default, MP3 files are saved with ID3v2.4 tags. You can use
        the older ID3v2.3 standard by specifying the `id3v23` option.
        """
        self.path = path

        self.mgfile = mutagen_call('open', path, mutagen.File, path)

        if self.mgfile is None:
            # Mutagen couldn't guess the type
            raise FileTypeError(path)
        elif (type(self.mgfile).__name__ == 'M4A' or
              type(self.mgfile).__name__ == 'MP4'):
            info = self.mgfile.info
            if info.codec and info.codec.startswith('alac'):
                self.type = 'alac'
            else:
                self.type = 'aac'
        elif (type(self.mgfile).__name__ == 'ID3' or
              type(self.mgfile).__name__ == 'MP3'):
            self.type = 'mp3'
        elif type(self.mgfile).__name__ == 'FLAC':
            self.type = 'flac'
        elif type(self.mgfile).__name__ == 'OggOpus':
            self.type = 'opus'
        elif type(self.mgfile).__name__ == 'OggVorbis':
            self.type = 'ogg'
        elif type(self.mgfile).__name__ == 'MonkeysAudio':
            self.type = 'ape'
        elif type(self.mgfile).__name__ == 'WavPack':
            self.type = 'wv'
        elif type(self.mgfile).__name__ == 'Musepack':
            self.type = 'mpc'
        elif type(self.mgfile).__name__ == 'ASF':
            self.type = 'asf'
        elif type(self.mgfile).__name__ == 'AIFF':
            self.type = 'aiff'
        elif type(self.mgfile).__name__ == 'DSF':
            self.type = 'dsf'
        else:
            raise FileTypeError(path, type(self.mgfile).__name__)

        # Add a set of tags if it's missing.
        if self.mgfile.tags is None:
            self.mgfile.add_tags()

        # Set the ID3v2.3 flag only for MP3s.
        self.id3v23 = id3v23 and self.type == 'mp3'

    def save(self):
        """Write the object's tags back to the file. May
        throw `UnreadableFileError`.
        """
        # Possibly save the tags to ID3v2.3.
        kwargs = {}
        if self.id3v23:
            id3 = self.mgfile
            if hasattr(id3, 'tags'):
                # In case this is an MP3 object, not an ID3 object.
                id3 = id3.tags
            id3.update_to_v23()
            kwargs['v2_version'] = 3

        mutagen_call('save', self.path, self.mgfile.save, **kwargs)

    def delete(self):
        """Remove the current metadata tag from the file. May
        throw `UnreadableFileError`.
        """
        mutagen_call('delete', self.path, self.mgfile.delete)

    # Convenient access to the set of available fields.

    @classmethod
    def fields(cls):
        """Get the names of all writable properties that reflect
        metadata tags (i.e., those that are instances of
        :class:`MediaField`).
        """
        for property, descriptor in cls.__dict__.items():
            if isinstance(descriptor, MediaField):
                if isinstance(property, bytes):
                    # On Python 2, class field names are bytes. This method
                    # produces text strings.
                    yield property.decode('utf8', 'ignore')
                else:
                    yield property

    @classmethod
    def _field_sort_name(cls, name):
        """Get a sort key for a field name that determines the order
        fields should be written in.

        Fields names are kept unchanged, unless they are instances of
        :class:`DateItemField`, in which case `year`, `month`, and `day`
        are replaced by `date0`, `date1`, and `date2`, respectively, to
        make them appear in that order.
        """
        if isinstance(cls.__dict__[name], DateItemField):
            name = re.sub('year',  'date0', name)
            name = re.sub('month', 'date1', name)
            name = re.sub('day',   'date2', name)
        return name

    @classmethod
    def sorted_fields(cls):
        """Get the names of all writable metadata fields, sorted in the
        order that they should be written.

        This is a lexicographic order, except for instances of
        :class:`DateItemField`, which are sorted in year-month-day
        order.
        """
        for property in sorted(cls.fields(), key=cls._field_sort_name):
            yield property

    @classmethod
    def readable_fields(cls):
        """Get all metadata fields: the writable ones from
        :meth:`fields` and also other audio properties.
        """
        for property in cls.fields():
            yield property
        for property in ('length', 'samplerate', 'bitdepth', 'bitrate',
                         'channels', 'format'):
            yield property

    @classmethod
    def add_field(cls, name, descriptor):
        """Add a field to store custom tags.

        :param name: the name of the property the field is accessed
                     through. It must not already exist on this class.

        :param descriptor: an instance of :class:`MediaField`.
        """
        if not isinstance(descriptor, MediaField):
            raise ValueError(
                u'{0} must be an instance of MediaField'.format(descriptor))
        if name in cls.__dict__:
            raise ValueError(
                u'property "{0}" already exists on MediaField'.format(name))
        setattr(cls, name, descriptor)

    def update(self, dict):
        """Set all field values from a dictionary.

        For any key in `dict` that is also a field to store tags the
        method retrieves the corresponding value from `dict` and updates
        the `MediaFile`. If a key has the value `None`, the
        corresponding property is deleted from the `MediaFile`.
        """
        for field in self.sorted_fields():
            if field in dict:
                if dict[field] is None:
                    delattr(self, field)
                else:
                    setattr(self, field, dict[field])

    # Field definitions.

    title = MediaField(
        MP3StorageStyle('TIT2'),
        MP4StorageStyle('\xa9nam'),
        StorageStyle('TITLE'),
        ASFStorageStyle('Title'),
    )
    artist = MediaField(
        MP3StorageStyle('TPE1'),
        MP4StorageStyle('\xa9ART'),
        StorageStyle('ARTIST'),
        ASFStorageStyle('Author'),
    )
    album = MediaField(
        MP3StorageStyle('TALB'),
        MP4StorageStyle('\xa9alb'),
        StorageStyle('ALBUM'),
        ASFStorageStyle('WM/AlbumTitle'),
    )
    genres = ListMediaField(
        MP3ListStorageStyle('TCON'),
        MP4ListStorageStyle('\xa9gen'),
        ListStorageStyle('GENRE'),
        ASFStorageStyle('WM/Genre'),
    )
    genre = genres.single_field()

    lyricist = MediaField(
        MP3StorageStyle('TEXT'),
        MP4StorageStyle('----:com.apple.iTunes:LYRICIST'),
        StorageStyle('LYRICIST'),
        ASFStorageStyle('WM/Writer'),
    )
    composer = MediaField(
        MP3StorageStyle('TCOM'),
        MP4StorageStyle('\xa9wrt'),
        StorageStyle('COMPOSER'),
        ASFStorageStyle('WM/Composer'),
    )
    composer_sort = MediaField(
        MP3StorageStyle('TSOC'),
        MP4StorageStyle('soco'),
        StorageStyle('COMPOSERSORT'),
        ASFStorageStyle('WM/Composersortorder'),
    )
    arranger = MediaField(
        MP3PeopleStorageStyle('TIPL', involvement='arranger'),
        MP4StorageStyle('----:com.apple.iTunes:Arranger'),
        StorageStyle('ARRANGER'),
        ASFStorageStyle('beets/Arranger'),
    )

    grouping = MediaField(
        MP3StorageStyle('TIT1'),
        MP4StorageStyle('\xa9grp'),
        StorageStyle('GROUPING'),
        ASFStorageStyle('WM/ContentGroupDescription'),
    )
    track = MediaField(
        MP3SlashPackStorageStyle('TRCK', pack_pos=0),
        MP4TupleStorageStyle('trkn', index=0),
        StorageStyle('TRACK'),
        StorageStyle('TRACKNUMBER'),
        ASFStorageStyle('WM/TrackNumber'),
        out_type=int,
    )
    tracktotal = MediaField(
        MP3SlashPackStorageStyle('TRCK', pack_pos=1),
        MP4TupleStorageStyle('trkn', index=1),
        StorageStyle('TRACKTOTAL'),
        StorageStyle('TRACKC'),
        StorageStyle('TOTALTRACKS'),
        ASFStorageStyle('TotalTracks'),
        out_type=int,
    )
    disc = MediaField(
        MP3SlashPackStorageStyle('TPOS', pack_pos=0),
        MP4TupleStorageStyle('disk', index=0),
        StorageStyle('DISC'),
        StorageStyle('DISCNUMBER'),
        ASFStorageStyle('WM/PartOfSet'),
        out_type=int,
    )
    disctotal = MediaField(
        MP3SlashPackStorageStyle('TPOS', pack_pos=1),
        MP4TupleStorageStyle('disk', index=1),
        StorageStyle('DISCTOTAL'),
        StorageStyle('DISCC'),
        StorageStyle('TOTALDISCS'),
        ASFStorageStyle('TotalDiscs'),
        out_type=int,
    )
    lyrics = MediaField(
        MP3DescStorageStyle(key='USLT'),
        MP4StorageStyle('\xa9lyr'),
        StorageStyle('LYRICS'),
        ASFStorageStyle('WM/Lyrics'),
    )
    comments = MediaField(
        MP3DescStorageStyle(key='COMM'),
        MP4StorageStyle('\xa9cmt'),
        StorageStyle('DESCRIPTION'),
        StorageStyle('COMMENT'),
        ASFStorageStyle('WM/Comments'),
        ASFStorageStyle('Description')
    )
    bpm = MediaField(
        MP3StorageStyle('TBPM'),
        MP4StorageStyle('tmpo', as_type=int),
        StorageStyle('BPM'),
        ASFStorageStyle('WM/BeatsPerMinute'),
        out_type=int,
    )
    comp = MediaField(
        MP3StorageStyle('TCMP'),
        MP4BoolStorageStyle('cpil'),
        StorageStyle('COMPILATION'),
        ASFStorageStyle('WM/IsCompilation', as_type=bool),
        out_type=bool,
    )
    albumartist = MediaField(
        MP3StorageStyle('TPE2'),
        MP4StorageStyle('aART'),
        StorageStyle('ALBUM ARTIST'),
        StorageStyle('ALBUMARTIST'),
        ASFStorageStyle('WM/AlbumArtist'),
    )
    albumtype = MediaField(
        MP3DescStorageStyle(u'MusicBrainz Album Type'),
        MP4StorageStyle('----:com.apple.iTunes:MusicBrainz Album Type'),
        StorageStyle('MUSICBRAINZ_ALBUMTYPE'),
        ASFStorageStyle('MusicBrainz/Album Type'),
    )
    label = MediaField(
        MP3StorageStyle('TPUB'),
        MP4StorageStyle('----:com.apple.iTunes:Label'),
        MP4StorageStyle('----:com.apple.iTunes:publisher'),
        StorageStyle('LABEL'),
        StorageStyle('PUBLISHER'),  # Traktor
        ASFStorageStyle('WM/Publisher'),
    )
    artist_sort = MediaField(
        MP3StorageStyle('TSOP'),
        MP4StorageStyle('soar'),
        StorageStyle('ARTISTSORT'),
        ASFStorageStyle('WM/ArtistSortOrder'),
    )
    albumartist_sort = MediaField(
        MP3DescStorageStyle(u'ALBUMARTISTSORT'),
        MP4StorageStyle('soaa'),
        StorageStyle('ALBUMARTISTSORT'),
        ASFStorageStyle('WM/AlbumArtistSortOrder'),
    )
    asin = MediaField(
        MP3DescStorageStyle(u'ASIN'),
        MP4StorageStyle('----:com.apple.iTunes:ASIN'),
        StorageStyle('ASIN'),
        ASFStorageStyle('MusicBrainz/ASIN'),
    )
    catalognum = MediaField(
        MP3DescStorageStyle(u'CATALOGNUMBER'),
        MP4StorageStyle('----:com.apple.iTunes:CATALOGNUMBER'),
        StorageStyle('CATALOGNUMBER'),
        ASFStorageStyle('WM/CatalogNo'),
    )
    disctitle = MediaField(
        MP3StorageStyle('TSST'),
        MP4StorageStyle('----:com.apple.iTunes:DISCSUBTITLE'),
        StorageStyle('DISCSUBTITLE'),
        ASFStorageStyle('WM/SetSubTitle'),
    )
    encoder = MediaField(
        MP3StorageStyle('TENC'),
        MP4StorageStyle('\xa9too'),
        StorageStyle('ENCODEDBY'),
        StorageStyle('ENCODER'),
        ASFStorageStyle('WM/EncodedBy'),
    )
    script = MediaField(
        MP3DescStorageStyle(u'Script'),
        MP4StorageStyle('----:com.apple.iTunes:SCRIPT'),
        StorageStyle('SCRIPT'),
        ASFStorageStyle('WM/Script'),
    )
    language = MediaField(
        MP3StorageStyle('TLAN'),
        MP4StorageStyle('----:com.apple.iTunes:LANGUAGE'),
        StorageStyle('LANGUAGE'),
        ASFStorageStyle('WM/Language'),
    )
    country = MediaField(
        MP3DescStorageStyle(u'MusicBrainz Album Release Country'),
        MP4StorageStyle('----:com.apple.iTunes:MusicBrainz '
                        'Album Release Country'),
        StorageStyle('RELEASECOUNTRY'),
        ASFStorageStyle('MusicBrainz/Album Release Country'),
    )
    albumstatus = MediaField(
        MP3DescStorageStyle(u'MusicBrainz Album Status'),
        MP4StorageStyle('----:com.apple.iTunes:MusicBrainz Album Status'),
        StorageStyle('MUSICBRAINZ_ALBUMSTATUS'),
        ASFStorageStyle('MusicBrainz/Album Status'),
    )
    media = MediaField(
        MP3StorageStyle('TMED'),
        MP4StorageStyle('----:com.apple.iTunes:MEDIA'),
        StorageStyle('MEDIA'),
        ASFStorageStyle('WM/Media'),
    )
    albumdisambig = MediaField(
        # This tag mapping was invented for beets (not used by Picard, etc).
        MP3DescStorageStyle(u'MusicBrainz Album Comment'),
        MP4StorageStyle('----:com.apple.iTunes:MusicBrainz Album Comment'),
        StorageStyle('MUSICBRAINZ_ALBUMCOMMENT'),
        ASFStorageStyle('MusicBrainz/Album Comment'),
    )

    # Release date.
    date = DateField(
        MP3StorageStyle('TDRC'),
        MP4StorageStyle('\xa9day'),
        StorageStyle('DATE'),
        ASFStorageStyle('WM/Year'),
        year=(StorageStyle('YEAR'),))

    year = date.year_field()
    month = date.month_field()
    day = date.day_field()

    # *Original* release date.
    original_date = DateField(
        MP3StorageStyle('TDOR'),
        MP4StorageStyle('----:com.apple.iTunes:ORIGINAL YEAR'),
        StorageStyle('ORIGINALDATE'),
        ASFStorageStyle('WM/OriginalReleaseYear'))

    original_year = original_date.year_field()
    original_month = original_date.month_field()
    original_day = original_date.day_field()

    # Nonstandard metadata.
    artist_credit = MediaField(
        MP3DescStorageStyle(u'Artist Credit'),
        MP4StorageStyle('----:com.apple.iTunes:Artist Credit'),
        StorageStyle('ARTIST_CREDIT'),
        ASFStorageStyle('beets/Artist Credit'),
    )
    albumartist_credit = MediaField(
        MP3DescStorageStyle(u'Album Artist Credit'),
        MP4StorageStyle('----:com.apple.iTunes:Album Artist Credit'),
        StorageStyle('ALBUMARTIST_CREDIT'),
        ASFStorageStyle('beets/Album Artist Credit'),
    )

    # Legacy album art field
    art = CoverArtField()

    # Image list
    images = ImageListField()

    # MusicBrainz IDs.
    mb_trackid = MediaField(
        MP3UFIDStorageStyle(owner='http://musicbrainz.org'),
        MP4StorageStyle('----:com.apple.iTunes:MusicBrainz Track Id'),
        StorageStyle('MUSICBRAINZ_TRACKID'),
        ASFStorageStyle('MusicBrainz/Track Id'),
    )
    mb_albumid = MediaField(
        MP3DescStorageStyle(u'MusicBrainz Album Id'),
        MP4StorageStyle('----:com.apple.iTunes:MusicBrainz Album Id'),
        StorageStyle('MUSICBRAINZ_ALBUMID'),
        ASFStorageStyle('MusicBrainz/Album Id'),
    )
    mb_artistid = MediaField(
        MP3DescStorageStyle(u'MusicBrainz Artist Id'),
        MP4StorageStyle('----:com.apple.iTunes:MusicBrainz Artist Id'),
        StorageStyle('MUSICBRAINZ_ARTISTID'),
        ASFStorageStyle('MusicBrainz/Artist Id'),
    )
    mb_albumartistid = MediaField(
        MP3DescStorageStyle(u'MusicBrainz Album Artist Id'),
        MP4StorageStyle('----:com.apple.iTunes:MusicBrainz Album Artist Id'),
        StorageStyle('MUSICBRAINZ_ALBUMARTISTID'),
        ASFStorageStyle('MusicBrainz/Album Artist Id'),
    )
    mb_releasegroupid = MediaField(
        MP3DescStorageStyle(u'MusicBrainz Release Group Id'),
        MP4StorageStyle('----:com.apple.iTunes:MusicBrainz Release Group Id'),
        StorageStyle('MUSICBRAINZ_RELEASEGROUPID'),
        ASFStorageStyle('MusicBrainz/Release Group Id'),
    )

    # Acoustid fields.
    acoustid_fingerprint = MediaField(
        MP3DescStorageStyle(u'Acoustid Fingerprint'),
        MP4StorageStyle('----:com.apple.iTunes:Acoustid Fingerprint'),
        StorageStyle('ACOUSTID_FINGERPRINT'),
        ASFStorageStyle('Acoustid/Fingerprint'),
    )
    acoustid_id = MediaField(
        MP3DescStorageStyle(u'Acoustid Id'),
        MP4StorageStyle('----:com.apple.iTunes:Acoustid Id'),
        StorageStyle('ACOUSTID_ID'),
        ASFStorageStyle('Acoustid/Id'),
    )

    # ReplayGain fields.
    rg_track_gain = MediaField(
        MP3DescStorageStyle(
            u'REPLAYGAIN_TRACK_GAIN',
            float_places=2, suffix=u' dB'
        ),
        MP3DescStorageStyle(
            u'replaygain_track_gain',
            float_places=2, suffix=u' dB'
        ),
        MP3SoundCheckStorageStyle(
            key='COMM',
            index=0, desc=u'iTunNORM',
            id3_lang='eng'
        ),
        MP4StorageStyle(
            '----:com.apple.iTunes:replaygain_track_gain',
            float_places=2, suffix=' dB'
        ),
        MP4SoundCheckStorageStyle(
            '----:com.apple.iTunes:iTunNORM',
            index=0
        ),
        StorageStyle(
            u'REPLAYGAIN_TRACK_GAIN',
            float_places=2, suffix=u' dB'
        ),
        ASFStorageStyle(
            u'replaygain_track_gain',
            float_places=2, suffix=u' dB'
        ),
        out_type=float
    )
    rg_album_gain = MediaField(
        MP3DescStorageStyle(
            u'REPLAYGAIN_ALBUM_GAIN',
            float_places=2, suffix=u' dB'
        ),
        MP3DescStorageStyle(
            u'replaygain_album_gain',
            float_places=2, suffix=u' dB'
        ),
        MP4StorageStyle(
            '----:com.apple.iTunes:replaygain_album_gain',
            float_places=2, suffix=' dB'
        ),
        StorageStyle(
            u'REPLAYGAIN_ALBUM_GAIN',
            float_places=2, suffix=u' dB'
        ),
        ASFStorageStyle(
            u'replaygain_album_gain',
            float_places=2, suffix=u' dB'
        ),
        out_type=float
    )
    rg_track_peak = MediaField(
        MP3DescStorageStyle(
            u'REPLAYGAIN_TRACK_PEAK',
            float_places=6
        ),
        MP3DescStorageStyle(
            u'replaygain_track_peak',
            float_places=6
        ),
        MP3SoundCheckStorageStyle(
            key=u'COMM',
            index=1, desc=u'iTunNORM',
            id3_lang='eng'
        ),
        MP4StorageStyle(
            '----:com.apple.iTunes:replaygain_track_peak',
            float_places=6
        ),
        MP4SoundCheckStorageStyle(
            '----:com.apple.iTunes:iTunNORM',
            index=1
        ),
        StorageStyle(u'REPLAYGAIN_TRACK_PEAK', float_places=6),
        ASFStorageStyle(u'replaygain_track_peak', float_places=6),
        out_type=float,
    )
    rg_album_peak = MediaField(
        MP3DescStorageStyle(
            u'REPLAYGAIN_ALBUM_PEAK',
            float_places=6
        ),
        MP3DescStorageStyle(
            u'replaygain_album_peak',
            float_places=6
        ),
        MP4StorageStyle(
            '----:com.apple.iTunes:replaygain_album_peak',
            float_places=6
        ),
        StorageStyle(u'REPLAYGAIN_ALBUM_PEAK', float_places=6),
        ASFStorageStyle(u'replaygain_album_peak', float_places=6),
        out_type=float,
    )

    initial_key = MediaField(
        MP3StorageStyle('TKEY'),
        MP4StorageStyle('----:com.apple.iTunes:initialkey'),
        StorageStyle('INITIALKEY'),
        ASFStorageStyle('INITIALKEY'),
    )

    @property
    def length(self):
        """The duration of the audio in seconds (a float)."""
        return self.mgfile.info.length

    @property
    def samplerate(self):
        """The audio's sample rate (an int)."""
        if hasattr(self.mgfile.info, 'sample_rate'):
            return self.mgfile.info.sample_rate
        elif self.type == 'opus':
            # Opus is always 48kHz internally.
            return 48000
        return 0

    @property
    def bitdepth(self):
        """The number of bits per sample in the audio encoding (an int).
        Only available for certain file formats (zero where
        unavailable).
        """
        if hasattr(self.mgfile.info, 'bits_per_sample'):
            return self.mgfile.info.bits_per_sample
        return 0

    @property
    def channels(self):
        """The number of channels in the audio (an int)."""
        if hasattr(self.mgfile.info, 'channels'):
            return self.mgfile.info.channels
        return 0

    @property
    def bitrate(self):
        """The number of bits per seconds used in the audio coding (an
        int). If this is provided explicitly by the compressed file
        format, this is a precise reflection of the encoding. Otherwise,
        it is estimated from the on-disk file size. In this case, some
        imprecision is possible because the file header is incorporated
        in the file size.
        """
        if hasattr(self.mgfile.info, 'bitrate') and self.mgfile.info.bitrate:
            # Many formats provide it explicitly.
            return self.mgfile.info.bitrate
        else:
            # Otherwise, we calculate bitrate from the file size. (This
            # is the case for all of the lossless formats.)
            if not self.length:
                # Avoid division by zero if length is not available.
                return 0
            size = os.path.getsize(self.path)
            return int(size * 8 / self.length)

    @property
    def format(self):
        """A string describing the file format/codec."""
        return TYPES[self.type]
