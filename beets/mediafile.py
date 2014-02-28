# This file is part of beets.
# Copyright 2014, Adrian Sampson.
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
"""
import mutagen
import mutagen.mp3
import mutagen.oggopus
import mutagen.oggvorbis
import mutagen.mp4
import mutagen.flac
import mutagen.monkeysaudio
import mutagen.asf
import datetime
import re
import base64
import math
import struct
import imghdr
import os
import logging
import traceback
from beets.util.enumeration import enum

__all__ = ['UnreadableFileError', 'FileTypeError', 'MediaFile']



# Logger.
log = logging.getLogger('beets')



# Exceptions.

# Raised for any file MediaFile can't read.
class UnreadableFileError(Exception):
    pass

# Raised for files that don't seem to have a type MediaFile supports.
class FileTypeError(UnreadableFileError):
    pass



# Constants.

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
}



# Utility.

def _safe_cast(out_type, val):
    """Try to covert val to out_type but never raise an exception. If
    the value can't be converted, then a sensible default value is
    returned. out_type should be bool, int, or unicode; otherwise, the
    value is just passed through.
    """
    if out_type == int:
        if val is None:
            return 0
        elif isinstance(val, int) or isinstance(val, float):
            # Just a number.
            return int(val)
        else:
            # Process any other type as a string.
            if not isinstance(val, basestring):
                val = unicode(val)
            # Get a number from the front of the string.
            val = re.match(r'[0-9]*', val.strip()).group(0)
            if not val:
                return 0
            else:
                return int(val)

    elif out_type == bool:
        if val is None:
            return False
        else:
            try:
                if isinstance(val, mutagen.asf.ASFBoolAttribute):
                    return val.value
                else:
                    # Should work for strings, bools, ints:
                    return bool(int(val))
            except ValueError:
                return False

    elif out_type == unicode:
        if val is None:
            return u''
        else:
            if isinstance(val, str):
                return val.decode('utf8', 'ignore')
            elif isinstance(val, unicode):
                return val
            else:
                return unicode(val)

    elif out_type == float:
        if val is None:
            return 0.0
        elif isinstance(val, int) or isinstance(val, float):
            return float(val)
        else:
            if not isinstance(val, basestring):
                val = unicode(val)
            val = re.match(r'[\+-]?[0-9\.]*', val.strip()).group(0)
            if not val:
                return 0.0
            else:
                return float(val)

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
    type, size = struct.unpack_from("<bi", data)
    pos = 5
    mime = ""
    while data[pos:pos + 2] != "\x00\x00":
        mime += data[pos:pos + 2]
        pos += 2
    pos += 2
    description = ""
    while data[pos:pos + 2] != "\x00\x00":
        description += data[pos:pos + 2]
        pos += 2
    pos += 2
    image_data = data[pos:pos + size]
    return (mime.decode("utf-16-le"), image_data, type,
            description.decode("utf-16-le"))

def _pack_asf_image(mime, data, type=3, description=""):
    """Pack image data for a WM/Picture tag.
    """
    tag_data = struct.pack("<bi", type, len(data))
    tag_data += mime.encode("utf-16-le") + "\x00\x00"
    tag_data += description.encode("utf-16-le") + "\x00\x00"
    tag_data += data
    return tag_data



# iTunes Sound Check encoding.

def _sc_decode(soundcheck):
    """Convert a Sound Check string value to a (gain, peak) tuple as
    used by ReplayGain.
    """
    # SoundCheck tags consist of 10 numbers, each represented by 8
    # characters of ASCII hex preceded by a space.
    try:
        soundcheck = soundcheck.replace(' ', '').decode('hex')
        soundcheck = struct.unpack('!iiiiiiiiii', soundcheck)
    except (struct.error, TypeError):
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
    g1 = min(round((10 ** (gain / -10)) * 1000), 65534)
    # Same as above, except our reference level is 2500 units.
    g2 = min(round((10 ** (gain / -10)) * 2500), 65534)

    # The purpose of these values are unknown, but they also seem to be
    # unused so we just use zero.
    uk = 0
    values = (g1, g1, g2, g2, uk, uk, peak, peak, uk, uk)
    return (u' %08X' * 10) % values



# Flags for encoding field behavior.

# Determine style of packing, if any.
packing = enum('SLASHED',   # pair delimited by /
               'TUPLE',     # a python tuple of 2 items
               'DATE',      # YYYY-MM-DD
               'SC',        # Sound Check gain/peak encoding
               name='packing')



# StorageStyle classes describe strategies for accessing values in
# Mutagen file objects.

class StorageStyle(object):
    """Parameterizes the storage behavior of a single field for a
    certain tag format.
     - key: The Mutagen key used to access the field's data.
     - as_type: Which type the value is stored as (unicode, int,
       bool, or str).
     - packing: If this value is packed in a multiple-value storage
       unit, which type of packing (in the packing enum). Otherwise,
       None. (Makes as_type irrelevant).
     - pack_pos: If the value is packed, in which position it is
       stored.
     - suffix: When `as_type` is a string type, append this before
       storing the value.
     - float_places: When the value is a floating-point number and
       encoded as a string, the number of digits to store after the
       point.
    """

    formats = ['flac', 'opus', 'ogg', 'ape', 'wv', 'mpc']

    def __init__(self, key, as_type=unicode, packing=None, pack_pos=0,
                 suffix=None, float_places=2, formats=None):
        self.key = key
        self.as_type = as_type
        self.packing = packing
        self.pack_pos = pack_pos
        self.suffix = suffix
        self.float_places = float_places
        if formats:
            self.formats = formats

        # Convert suffix to correct string type.
        if self.suffix and self.as_type == unicode:
            self.suffix = self.as_type(self.suffix)

    def fetch(self, mutagen_file):
        """Retrieve the first raw value of this tag from the mediafile."""
        try:
            return mutagen_file[self.key][0]
        except KeyError:
            return None

    def get(self, mutagen_file):
        """Retrieve the unpacked value of this field from the mediafile."""
        data = self.fetch(mutagen_file)
        if self.packing:
            try:
                data = self.unpack(data)[self.pack_pos]
            except IndexError:
                data = None

        data = self._strip_possible_suffix(data)
        return data

    def unpack(self, data):
        """Splits raw data from a tag into a list of values."""
        if self.packing == packing.DATE:
            packing_length = 3
        else:
            packing_length = 2

        if data is None:
            return [None] * packing_length

        if self.packing == packing.DATE:
            # Remove time information from dates. Usually delimited by
            # a "T" or a space.
            data = re.sub(r'[Tt ].*$', '', unicode(data))
            items = unicode(data).split('-')
        elif self.packing == packing.SLASHED:
            items = unicode(data).split('/')
        elif self.packing == packing.TUPLE:
            items = data # tuple: items is already indexable
        elif self.packing == packing.SC:
            items = _sc_decode(data)

        return list(items) + [None] * (packing_length - len(items))

    def store(self, mutagen_file, value):
        """Stores a serialized value in the mediafile."""
        mutagen_file[self.key] = [value]

    def set(self, mutagen_file, value):
        """Packs, serializes and stores the value in the mediafile."""
        if value is None:
            value = self._none_value()

        if self.packing:
            data = self.fetch(mutagen_file)
            value = self.pack(data, value)

        value = self.serialize(value)
        self.store(mutagen_file, value)

    def pack(self, data, value):
        """Pack value into data.

        It unpacks ``data`` into a list, updates the value at ``self.pack_pos``
        and returns the updated list.
        """
        items = list(self.unpack(data))
        for i in range(len(items)):
            if not items[i]:
                items[i] = self._none_value()

        items[self.pack_pos] = value

        if self.packing == packing.DATE:
            # Truncate the items wherever we reach an invalid (none)
            # entry. This prevents dates like 2008-00-05.
            for i, item in enumerate(items):
                if item == self._none_value() or item is None:
                    del(items[i:]) # truncate
                    break

        if self.packing == packing.SLASHED:
            data = '/'.join(map(unicode, items))
        elif self.packing == packing.DATE:
            field_lengths = [4, 2, 2] # YYYY-MM-DD
            elems = []
            for i, item in enumerate(items):
                elems.append('{0:0{1}}'.format(int(item), field_lengths[i]))
            data = '-'.join(elems)
        elif self.packing == packing.SC:
            data = _sc_encode(*items)
        else:
            data = tuple(items)

        return data

    def serialize(self, value):
        """Convert value to a type that is suitable for storing in a tag."""
        if value is None:
            value = self._none_value()

        if isinstance(value, float) and self.as_type is unicode:
            value = u'{0:.{1}f}'.format(value, self.float_places)
            value = self.as_type(value)
        elif self.as_type is unicode:
            if isinstance(value, bool):
                # Store bools as 1/0 instead of True/False.
                value = unicode(int(bool(value)))
            elif isinstance(value, str):
                value = value.decode('utf8', 'ignore')
            else:
                value = unicode(value)
        else:
            value = self.as_type(value)

        if self.suffix:
            value += self.suffix

        return value

    def _none_value(self):
        """The value that ``None`` atains when serializing and packing."""
        if self.out_type == int:
            return 0
        elif self.out_type == float:
            return 0.0
        elif self.out_type == bool:
            return False
        elif self.out_type == unicode:
            return u''

    def _strip_possible_suffix(self, data):
        if self.suffix and isinstance(data, unicode) \
                       and data.endswith(self.suffix):
            return data[:-len(self.suffix)]
        else:
            return data


class ListStorageStyle(StorageStyle):
    """Abstract class that provides access to lists.

    Subclasses may overwrite ``fetch`` and ``store``.  ``fetch`` must
    return a (possibly empty) list and ``store`` receives a serialized
    list of values as the second argument.

    This class does not support packing. A call to the packing methods
    raises an error.
    """

    def get(self, mutagen_file):
        try:
            return self.get_list(mutagen_file)[0]
        except IndexError:
            return None

    def get_list(self, mutagen_file):
        data = self.fetch(mutagen_file)
        return [self._strip_possible_suffix(item) for item in data]

    def fetch(self, mutagen_file):
        try:
            return mutagen_file[self.key]
        except KeyError:
            return []

    def set(self, mutagen_file, value):
        self.set_list(mutagen_file, [value])

    def set_list(self, mutagen_file, values):
        self.store(mutagen_file, [self.serialize(value) for value in values])

    def store(self, mutagen_file, values):
        mutagen_file[self.key] = values

    def pack(self, data, value):
        raise NotImplementedError('packing is not implemented for lists')

    def unpack(self, data):
        raise NotImplementedError('packing is not implemented for lists')


class ASFStorageStyle(StorageStyle):
    formats = ['asf']


class MP4StorageStyle(StorageStyle):

    formats = ['aac', 'alac']

    def fetch(self, mutagen_file):
        try:
            return mutagen_file[self.key][0]
        except KeyError:
            return None

    def store(self, mutagen_file, value):
        mutagen_file[self.key] = [value]

    def serialize(self, value):
        if self.packing != packing.TUPLE:
            value = super(MP4StorageStyle, self).serialize(value)
        if self.key.startswith('----:') and isinstance(value, unicode):
            value = value.encode('utf8')
        return value

    def pack(self, data, value):
        value = super(MP4StorageStyle, self).pack(data, value)
        if self.key.startswith('----:') and isinstance(value, unicode):
            value = value.encode('utf8')
        return value


class MP4ListStorageStyle(ListStorageStyle, MP4StorageStyle):
    pass


class MP4BoolStorageStyle(MP4StorageStyle):

    def get(self, mutagen_file):
        try:
            return mutagen_file[self.key]
        except KeyError:
            return None

    def get_list(self, mutagen_file):
        raise NotImplementedError('MP4 bool storage does not support lists')

    def set(self, mutagen_file, value):
        mutagen_file[self.key] = value

    def set_list(self, mutagen_file, values):
        raise NotImplementedError('MP4 bool storage does not support lists')


class MP4ImageStorageStyle(MP4ListStorageStyle):

    def __init__(self, **kwargs):
        super(MP4ImageStorageStyle, self).__init__(key='covr', **kwargs)
        self.as_type = str

    def store(self, mutagen_file, images):
        covers = [self._mp4_cover(image) for image in images]
        mutagen_file['covr'] = covers

    @classmethod
    def _mp4_cover(cls, data):
        """Make ``MP4Cover`` tag from image data.

        Returns instance of ``mutagen.mp4.MP4Cover`` with correct cover
        format.
        """
        kind = imghdr.what(None, h=data)
        if kind == 'png':
            kind = mutagen.mp4.MP4Cover.FORMAT_PNG
        elif kind == 'jpeg':
            kind = mutagen.mp4.MP4Cover.FORMAT_JPEG
        else:
            raise ValueError('MP4 only supports PNG and JPEG images')

        return mutagen.mp4.MP4Cover(data, kind)


class MP3StorageStyle(StorageStyle):

    formats = ['mp3']

    def __init__(self, key, id3_lang=None, **kwargs):
        self.id3_lang = id3_lang
        super(MP3StorageStyle, self).__init__(key, **kwargs)

    def fetch(self, mutagen_file):
        try:
            return mutagen_file[self.key].text[0]
        except KeyError:
            return None

    def store(self, mutagen_file, value):
        frame = mutagen.id3.Frames[self.key](encoding=3, text=[value])
        mutagen_file.tags.setall(self.key, [frame])


class MP3ListStorageStyle(ListStorageStyle, MP3StorageStyle):

    def fetch(self, mutagen_file):
        try:
            return mutagen_file[self.key].text
        except KeyError:
            return []

    def store(self, mutagen_file, values):
        frame = mutagen.id3.Frames[self.key](encoding=3, text=values)
        mutagen_file.tags.setall(self.key, [frame])


class MP3UFIDStorageStyle(MP3StorageStyle):

    def __init__(self, owner, **kwargs):
        self.owner = owner
        super(MP3UFIDStorageStyle, self).__init__('UFID:' + owner, **kwargs)

    def fetch(self, mutagen_file):
        try:
            return mutagen_file[self.key].data
        except KeyError:
            return None

    def store(self, mutagen_file, value):
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

    def __init__(self, desc=u'', key='TXXX', **kwargs):
        self.description = desc
        super(MP3DescStorageStyle, self).__init__(key=key, **kwargs)

    def store(self, mutagen_file, value):
        frames = mutagen_file.tags.getall(self.key)
        if self.key != 'USLT':
            value = [value]

        # try modifying in place
        found = False
        for frame in frames:
            if frame.desc.lower() == self.description.lower():
                frame.text = value
                found = True

        # need to make a new frame?
        if not found:
            frame = mutagen.id3.Frames[self.key](
                    desc=str(self.description), text=value, encoding=3)
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


class MP3ImageStorageStyle(ListStorageStyle, MP3StorageStyle):

    def __init__(self):
        super(MP3ImageStorageStyle, self).__init__(key='APIC')
        self.as_type = str

    def fetch(self, mutagen_file):
        try:
            frames = mutagen_file.tags.getall(self.key)
            return [frame.data for frame in frames]
        except IndexError:
            return None

    def store(self, mutagen_file, images):
        image = images[0]
        frame = mutagen.id3.APIC(
            encoding=3,
            type=3,  # FrontCover
            mime=ImageField._mime(image),
            desc=u'',
            data=image
        )
        mutagen_file.tags.setall(self.key, [frame])


class ASFImageStorageStyle(ListStorageStyle):

    formats = ['asf']

    def __init__(self):
        super(ASFImageStorageStyle, self).__init__(key='WM/Picture')
        self.as_type = str

    def fetch(self, mutagen_file):
        if 'WM/Picture' not in mutagen_file:
            return []

        pictures = []
        for picture in mutagen_file['WM/Picture']:
            try:
                pictures.append(_unpack_asf_image(picture.value)[1])
            except:
                pass
        return pictures

    def store(self, mutagen_file, images):
        if 'WM/Picture' in mutagen_file:
            del mutagen_file['WM/Picture']

        for image in images:
            pic = mutagen.asf.ASFByteArrayAttribute()
            pic.value = _pack_asf_image(ImageField._mime(image), image)
            mutagen_file['WM/Picture'] = [pic]


class VorbisImageStorageStyle(ListStorageStyle):

    formats = ['opus', 'ogg', 'ape', 'wv', 'mpc']

    def __init__(self):
        super(VorbisImageStorageStyle, self).__init__(key='')
        self.as_type = str

    def fetch(self, mutagen_file):
        if 'metadata_block_picture' not in mutagen_file:
            # Try legacy COVERART tags.
            if 'coverart' in mutagen_file and mutagen_file['coverart']:
                return base64.b64decode(mutagen_file['coverart'][0])
            return []

        pics = []
        for data in mutagen_file["metadata_block_picture"]:
            try:
                pics.append(mutagen.flac.Picture(base64.b64decode(data)).data)
            except (TypeError, AttributeError):
                pass
        return pics

    def store(self, mutagen_file, image_data):
        # Strip all art, including legacy COVERART.
        if 'metadata_block_picture' in mutagen_file:
            if 'metadata_block_picture' in mutagen_file:
                del mutagen_file['metadata_block_picture']
            if 'coverart' in mutagen_file:
                del mutagen_file['coverart']
            if 'coverartmime' in mutagen_file:
                del mutagen_file['coverartmime']

        image_data = image_data[0]
        # Add new art if provided.
        if image_data is not None:
            pic = mutagen.flac.Picture()
            pic.data = image_data
            pic.mime = ImageField._mime(image_data)
            mutagen_file['metadata_block_picture'] = [
                base64.b64encode(pic.write())
            ]


class FlacImageStorageStyle(ListStorageStyle):

    formats = ['flac']

    def __init__(self):
        super(FlacImageStorageStyle, self).__init__(key='')
        self.as_type = str

    def fetch(self, mutagen_file):
        pictures = mutagen_file.pictures
        if pictures:
            return [picture.data or None for picture in pictures]
        else:
            return []

    def store(self, mutagen_file, images):
        mutagen_file.clear_pictures()

        for image in images:
            pic = mutagen.flac.Picture()
            pic.data = image
            pic.type = 3  # front cover
            pic.mime = ImageField._mime(image)
            mutagen_file.add_picture(pic)



# MediaField is a descriptor that represents a single logical field. It
# aggregates several StorageStyles describing how to access the data for
# each file type.

class MediaField(object):
    """A descriptor providing access to a particular (abstract) metadata
    field.
    """
    def __init__(self, *styles, **kwargs):
        """Creates a new MediaField.

         - styles: A list of ``StorageStyle``s that perform the actual
           storing of tags depending on the media file format.
         - kwargs: ``out_type`` is the type of the value that should be
           returned when getting this property
        """
        self.out_type = kwargs.get('out_type', unicode)
        self._styles = styles
        for style in styles:
            style.out_type = self.out_type

    def styles(self, mediafile):
        """Yields the list of storage styles of this field that can
        handle the mediafile's format.
        """
        for style in self._styles:
            if mediafile.type in style.formats:
                yield style

    def __get__(self, mediafile, owner):
        for style in self.styles(mediafile):
            out = style.get(mediafile.mgfile)
            if out:
                break
        return _safe_cast(self.out_type, out)


    def __set__(self, mediafile, value):
        for style in self.styles(mediafile):
            style.set(mediafile.mgfile, value)


class ListMediaField(MediaField):
    """Property descriptor that retrieves a list from a tag.

    Uses ``get_list`` and set_list`` methods of its ``StorageStyle``
    strategies to do the actual work.
    """

    def __get__(self, mediafile, _):
        values = []
        for style in self.styles(mediafile):
            values.extend(style.get_list(mediafile.mgfile))
        return [_safe_cast(self.out_type, value) for value in values]

    def __set__(self, mediafile, values):
        for style in self.styles(mediafile):
            style.set_list(mediafile.mgfile, values)

    def single_field(self):
        """Returns a ``MediaField`` descriptor that gets and sets the
        first item.
        """
        options = {'out_type': self.out_type}
        return MediaField(*self._styles, **options)


class CompositeDateField(MediaField):
    """A MediaFile field for conveniently accessing the year, month, and
    day fields as a datetime.date object. Allows both getting and
    setting of the component fields.
    """
    def __init__(self, year_field, month_field, day_field):
        """Create a new date field from the indicated MediaFields for
        the component values.
        """
        self.year_field = year_field
        self.month_field = month_field
        self.day_field = day_field

    def __get__(self, mediafile, owner):
        """Return a datetime.date object whose components indicating the
        smallest valid date whose components are at least as large as
        the three component fields (that is, if year == 1999, month == 0,
        and day == 0, then date == datetime.date(1999, 1, 1)). If the
        components indicate an invalid date (e.g., if month == 47),
        datetime.date.min is returned.
        """
        try:
            return datetime.date(
                max(self.year_field.__get__(mediafile, owner), datetime.MINYEAR),
                max(self.month_field.__get__(mediafile, owner), 1),
                max(self.day_field.__get__(mediafile, owner), 1)
            )
        except ValueError:  # Out of range values.
            return datetime.date.min

    def __set__(self, mediafile, date):
        """Set the year, month, and day fields to match the components of
        the provided datetime.date object.
        """
        self.year_field.__set__(mediafile, date.year)
        self.month_field.__set__(mediafile, date.month)
        self.day_field.__set__(mediafile, date.day)


class ImageField(MediaField):
    """A descriptor providing access to a file's embedded album art.
    Holds a bytestring reflecting the image data. The image should
    either be a JPEG or a PNG for cross-format compatibility. It's
    probably a bad idea to use anything but these two formats.
    """

    def __init__(self):
        super(ImageField, self).__init__(
            MP3ImageStorageStyle(),
            MP4ImageStorageStyle(),
            ASFImageStorageStyle(),
            VorbisImageStorageStyle(),
            FlacImageStorageStyle(),
            out_type=str,
        )

    @classmethod
    def _mime(cls, data):
        """Return the MIME type (either image/png or image/jpeg) of the
        image data (a bytestring).
        """
        kind = imghdr.what(None, h=data)
        if kind == 'png':
            return 'image/png'
        else:
            # Currently just fall back to JPEG.
            return 'image/jpeg'

    def __get__(self, mediafile, _):
        for style in self.styles(mediafile):
            return style.get(mediafile.mgfile)

    def __set__(self, mediafile, data):
        if data is not None:
            if not isinstance(data, str):
                raise ValueError('value must be a byte string or None')
        for style in self.styles(mediafile):
            style.set(mediafile.mgfile, data)



# MediaFile is a collection of fields.

class MediaFile(object):
    """Represents a multimedia file on disk and provides access to its
    metadata.
    """
    def __init__(self, path):
        """Constructs a new MediaFile reflecting the file at path. May
        throw UnreadableFileError.
        """
        self.path = path

        unreadable_exc = (
            mutagen.mp3.error,
            mutagen.id3.error,
            mutagen.flac.error,
            mutagen.monkeysaudio.MonkeysAudioHeaderError,
            mutagen.mp4.error,
            mutagen.oggopus.error,
            mutagen.oggvorbis.error,
            mutagen.ogg.error,
            mutagen.asf.error,
            mutagen.apev2.error,
        )
        try:
            self.mgfile = mutagen.File(path)
        except unreadable_exc as exc:
            log.debug(u'header parsing failed: {0}'.format(unicode(exc)))
            raise UnreadableFileError('Mutagen could not read file')
        except IOError as exc:
            if type(exc) == IOError:
                # This is a base IOError, not a subclass from Mutagen or
                # anywhere else.
                raise
            else:
                log.debug(traceback.format_exc())
                raise UnreadableFileError('Mutagen raised an exception')
        except Exception as exc:
            # Hide bugs in Mutagen.
            log.debug(traceback.format_exc())
            log.error('uncaught Mutagen exception: {0}'.format(exc))
            raise UnreadableFileError('Mutagen raised an exception')

        if self.mgfile is None: # Mutagen couldn't guess the type
            raise FileTypeError('file type unsupported by Mutagen')
        elif type(self.mgfile).__name__ == 'M4A' or \
             type(self.mgfile).__name__ == 'MP4':
            # This hack differentiates AAC and ALAC until we find a more
            # deterministic approach. Mutagen only sets the sample rate
            # for AAC files. See:
            # https://github.com/sampsyo/beets/pull/295
            if hasattr(self.mgfile.info, 'sample_rate') and \
               self.mgfile.info.sample_rate > 0:
                self.type = 'aac'
            else:
                self.type = 'alac'
        elif type(self.mgfile).__name__ == 'ID3' or \
             type(self.mgfile).__name__ == 'MP3':
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
        else:
            raise FileTypeError('file type %s unsupported by MediaFile' %
                                type(self.mgfile).__name__)

        # add a set of tags if it's missing
        if self.mgfile.tags is None:
            self.mgfile.add_tags()

    def save(self, id3v23=False):
        """Write the object's tags back to the file.

        By default, MP3 files are saved with ID3v2.4 tags. You can use
        the older ID3v2.3 standard by specifying the `id3v23` option.
        """
        if id3v23 and self.type == 'mp3':
            id3 = self.mgfile
            if hasattr(id3, 'tags'):
                # In case this is an MP3 object, not an ID3 object.
                id3 = id3.tags
            id3.update_to_v23()
            self.mgfile.save(v2_version=3)
        else:
            self.mgfile.save()

    def delete(self):
        """Remove the current metadata tag from the file.
        """
        try:
            self.mgfile.delete()
        except NotImplementedError:
            # For Mutagen types that don't support deletion (notably,
            # ASF), just delete each tag individually.
            for tag in self.mgfile.keys():
                del self.mgfile[tag]


    # Field definitions.

    title = MediaField(
        MP3StorageStyle('TIT2'),
        MP4StorageStyle("\xa9nam"),
        StorageStyle('TITLE'),
        ASFStorageStyle('Title'),
    )
    artist = MediaField(
        MP3StorageStyle('TPE1'),
        MP4StorageStyle("\xa9ART"),
        StorageStyle('ARTIST'),
        ASFStorageStyle('Author'),
    )
    album = MediaField(
        MP3StorageStyle('TALB'),
        MP4StorageStyle("\xa9alb"),
        StorageStyle('ALBUM'),
        ASFStorageStyle('WM/AlbumTitle'),
    )
    genres = ListMediaField(
        MP3ListStorageStyle('TCON'),
        MP4ListStorageStyle("\xa9gen"),
        ListStorageStyle('GENRE'),
        ASFStorageStyle('WM/Genre'),
    )
    genre = genres.single_field()

    composer = MediaField(
        MP3StorageStyle('TCOM'),
        MP4StorageStyle("\xa9wrt"),
        StorageStyle('COMPOSER'),
        ASFStorageStyle('WM/Composer'),
    )
    grouping = MediaField(
        MP3StorageStyle('TIT1'),
        MP4StorageStyle("\xa9grp"),
        StorageStyle('GROUPING'),
        ASFStorageStyle('WM/ContentGroupDescription'),
    )
    track = MediaField(
        MP3StorageStyle('TRCK', packing=packing.SLASHED, pack_pos=0),
        MP4StorageStyle('trkn', packing=packing.TUPLE, pack_pos=0),
        StorageStyle('TRACK'),
        StorageStyle('TRACKNUMBER'),
        ASFStorageStyle('WM/TrackNumber'),
        out_type=int,
    )
    tracktotal = MediaField(
        MP3StorageStyle('TRCK', packing=packing.SLASHED, pack_pos=1),
        MP4StorageStyle('trkn', packing=packing.TUPLE, pack_pos=1),
        StorageStyle('TRACKTOTAL'),
        StorageStyle('TRACKC'),
        StorageStyle('TOTALTRACKS'),
        ASFStorageStyle('TotalTracks'),
        out_type=int,
    )
    disc = MediaField(
        MP3StorageStyle('TPOS', packing=packing.SLASHED, pack_pos=0),
        MP4StorageStyle('disk', packing=packing.TUPLE, pack_pos=0),
        StorageStyle('DISC'),
        StorageStyle('DISCNUMBER'),
        ASFStorageStyle('WM/PartOfSet'),
        out_type=int,
    )
    disctotal = MediaField(
        MP3StorageStyle('TPOS', packing=packing.SLASHED, pack_pos=1),
        MP4StorageStyle('disk', packing=packing.TUPLE, pack_pos=1),
        StorageStyle('DISCTOTAL'),
        StorageStyle('DISCC'),
        StorageStyle('TOTALDISCS'),
        ASFStorageStyle('TotalDiscs'),
        out_type=int,
    )
    lyrics = MediaField(
        MP3DescStorageStyle(key='USLT'),
        MP4StorageStyle("\xa9lyr"),
        StorageStyle('LYRICS'),
        ASFStorageStyle('WM/Lyrics'),
    )
    comments = MediaField(
        MP3DescStorageStyle(key='COMM'),
        MP4StorageStyle("\xa9cmt"),
        StorageStyle('DESCRIPTION'),
        StorageStyle('COMMENT'),
        ASFStorageStyle('WM/Comments'),
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
        MP4StorageStyle("soar"),
        StorageStyle('ARTISTSORT'),
        ASFStorageStyle('WM/ArtistSortOrder'),
    )
    albumartist_sort = MediaField(
        MP3DescStorageStyle(u'ALBUMARTISTSORT'),
        MP4StorageStyle("soaa"),
        StorageStyle('ALBUMARTISTSORT'),
        ASFStorageStyle('WM/AlbumArtistSortOrder'),
    )
    asin = MediaField(
        MP3DescStorageStyle(u'ASIN'),
        MP4StorageStyle("----:com.apple.iTunes:ASIN"),
        StorageStyle('ASIN'),
        ASFStorageStyle('MusicBrainz/ASIN'),
    )
    catalognum = MediaField(
        MP3DescStorageStyle(u'CATALOGNUMBER'),
        MP4StorageStyle("----:com.apple.iTunes:CATALOGNUMBER"),
        StorageStyle('CATALOGNUMBER'),
        ASFStorageStyle('WM/CatalogNo'),
    )
    disctitle = MediaField(
        MP3StorageStyle('TSST'),
        MP4StorageStyle("----:com.apple.iTunes:DISCSUBTITLE"),
        StorageStyle('DISCSUBTITLE'),
        ASFStorageStyle('WM/SetSubTitle'),
    )
    encoder = MediaField(
        MP3StorageStyle('TENC'),
        MP4StorageStyle("\xa9too"),
        StorageStyle('ENCODEDBY'),
        StorageStyle('ENCODER'),
        ASFStorageStyle('WM/EncodedBy'),
    )
    script = MediaField(
        MP3DescStorageStyle(u'Script'),
        MP4StorageStyle("----:com.apple.iTunes:SCRIPT"),
        StorageStyle('SCRIPT'),
        ASFStorageStyle('WM/Script'),
    )
    language = MediaField(
        MP3StorageStyle('TLAN'),
        MP4StorageStyle("----:com.apple.iTunes:LANGUAGE"),
        StorageStyle('LANGUAGE'),
        ASFStorageStyle('WM/Language'),
    )
    country = MediaField(
        MP3DescStorageStyle('MusicBrainz Album Release Country'),
        MP4StorageStyle("----:com.apple.iTunes:MusicBrainz Album "
                         "Release Country"),
        StorageStyle('RELEASECOUNTRY'),
        ASFStorageStyle('MusicBrainz/Album Release Country'),
    )
    albumstatus = MediaField(
        MP3DescStorageStyle(u'MusicBrainz Album Status'),
        MP4StorageStyle("----:com.apple.iTunes:MusicBrainz Album Status"),
        StorageStyle('MUSICBRAINZ_ALBUMSTATUS'),
        ASFStorageStyle('MusicBrainz/Album Status'),
    )
    media = MediaField(
        MP3StorageStyle('TMED'),
        MP4StorageStyle("----:com.apple.iTunes:MEDIA"),
        StorageStyle('MEDIA'),
        ASFStorageStyle('WM/Media'),
    )
    albumdisambig = MediaField(
        # This tag mapping was invented for beets (not used by Picard, etc).
        MP3DescStorageStyle(u'MusicBrainz Album Comment'),
        MP4StorageStyle("----:com.apple.iTunes:MusicBrainz Album Comment"),
        StorageStyle('MUSICBRAINZ_ALBUMCOMMENT'),
        ASFStorageStyle('MusicBrainz/Album Comment'),
    )

    # Release date.
    year = MediaField(
        MP3StorageStyle('TDRC', packing=packing.DATE, pack_pos=0),
        MP4StorageStyle("\xa9day", packing=packing.DATE, pack_pos=0),
        StorageStyle('DATE', packing=packing.DATE, pack_pos=0),
        StorageStyle('YEAR'),
        ASFStorageStyle('WM/Year', packing=packing.DATE, pack_pos=0),
        out_type=int,
    )
    month = MediaField(
        MP3StorageStyle('TDRC', packing=packing.DATE, pack_pos=1),
        MP4StorageStyle("\xa9day", packing=packing.DATE, pack_pos=1),
        StorageStyle('DATE', packing=packing.DATE, pack_pos=1),
        ASFStorageStyle('WM/Year', packing=packing.DATE, pack_pos=1),
        out_type=int,
    )
    day = MediaField(
        MP3StorageStyle('TDRC', packing=packing.DATE, pack_pos=2),
        MP4StorageStyle("\xa9day", packing=packing.DATE, pack_pos=2),
        StorageStyle('DATE', packing=packing.DATE, pack_pos=2),
        ASFStorageStyle('WM/Year', packing=packing.DATE, pack_pos=2),
        out_type=int,
    )
    date = CompositeDateField(year, month, day)

    # *Original* release date.
    original_year = MediaField(
        MP3StorageStyle('TDOR', packing=packing.DATE, pack_pos=0),
        MP4StorageStyle('----:com.apple.iTunes:ORIGINAL YEAR',
                         packing=packing.DATE, pack_pos=0),
        StorageStyle('ORIGINALDATE', packing=packing.DATE, pack_pos=0),
        ASFStorageStyle('WM/OriginalReleaseYear', packing=packing.DATE,
                         pack_pos=0),
        out_type=int,
    )
    original_month = MediaField(
        MP3StorageStyle('TDOR', packing=packing.DATE, pack_pos=1),
        MP4StorageStyle('----:com.apple.iTunes:ORIGINAL YEAR',
                         packing=packing.DATE, pack_pos=1),
        StorageStyle('ORIGINALDATE', packing=packing.DATE, pack_pos=1),
        ASFStorageStyle('WM/OriginalReleaseYear', packing=packing.DATE,
                         pack_pos=1),
        out_type=int,
    )
    original_day = MediaField(
        MP3StorageStyle('TDOR', packing=packing.DATE, pack_pos=2),
        MP4StorageStyle('----:com.apple.iTunes:ORIGINAL YEAR',
                         packing=packing.DATE, pack_pos=2),
        StorageStyle('ORIGINALDATE', packing=packing.DATE, pack_pos=2),
        ASFStorageStyle('WM/OriginalReleaseYear', packing=packing.DATE,
                         pack_pos=2),
        out_type=int,
    )
    original_date = CompositeDateField(original_year, original_month,
                                       original_day)

    # Nonstandard metadata.
    artist_credit = MediaField(
        MP3DescStorageStyle(u'Artist Credit'),
        MP4StorageStyle("----:com.apple.iTunes:Artist Credit"),
        StorageStyle('ARTIST_CREDIT'),
        ASFStorageStyle('beets/Artist Credit'),
    )
    albumartist_credit = MediaField(
        MP3DescStorageStyle(u'Album Artist Credit'),
        MP4StorageStyle("----:com.apple.iTunes:Album Artist Credit"),
        StorageStyle('ALBUMARTIST_CREDIT'),
        ASFStorageStyle('beets/Album Artist Credit'),
    )

    # Album art.
    art = ImageField()

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
        MP3DescStorageStyle(u'REPLAYGAIN_TRACK_GAIN',
                     float_places=2, suffix=u' dB'),
        MP3DescStorageStyle(u'replaygain_track_gain',
                     float_places=2, suffix=u' dB'),
        MP3DescStorageStyle(key='COMM', desc=u'iTunNORM', id3_lang='eng',
                     packing=packing.SC, pack_pos=0),
        MP4StorageStyle('----:com.apple.iTunes:replaygain_track_gain',
                     float_places=2, suffix=b' dB'),
        MP4StorageStyle('----:com.apple.iTunes:iTunNORM',
                     packing=packing.SC, pack_pos=0),
        StorageStyle(u'REPLAYGAIN_TRACK_GAIN',
                         float_places=2, suffix=u' dB'),
        ASFStorageStyle(u'replaygain_track_gain',
                         float_places=2, suffix=u' dB'),
        out_type=float
    )
    rg_album_gain = MediaField(
        MP3DescStorageStyle(u'REPLAYGAIN_ALBUM_GAIN',
                     float_places=2, suffix=u' dB'),
        MP3DescStorageStyle(u'replaygain_album_gain',
                     float_places=2, suffix=u' dB'),
        MP4StorageStyle('----:com.apple.iTunes:replaygain_album_gain',
                         float_places=2, suffix=b' dB'),
        StorageStyle(u'REPLAYGAIN_ALBUM_GAIN',
                         float_places=2, suffix=u' dB'),
        ASFStorageStyle(u'replaygain_album_gain',
                         float_places=2, suffix=u' dB'),
        out_type=float
    )
    rg_track_peak = MediaField(
        MP3DescStorageStyle(u'REPLAYGAIN_TRACK_PEAK',
                     float_places=6),
        MP3DescStorageStyle(u'replaygain_track_peak',
                     float_places=6),
        MP3DescStorageStyle(key='COMM', desc=u'iTunNORM', id3_lang='eng',
                     packing=packing.SC, pack_pos=1),
        MP4StorageStyle('----:com.apple.iTunes:replaygain_track_peak',
                     float_places=6),
        MP4StorageStyle('----:com.apple.iTunes:iTunNORM',
                     packing=packing.SC, pack_pos=1),
        StorageStyle(u'REPLAYGAIN_TRACK_PEAK',
                         float_places=6),
        ASFStorageStyle(u'replaygain_track_peak',
                         float_places=6),
        out_type=float,
    )
    rg_album_peak = MediaField(
        MP3DescStorageStyle(u'REPLAYGAIN_ALBUM_PEAK',
                     float_places=6),
        MP3DescStorageStyle(u'replaygain_album_peak',
                     float_places=6),
        MP4StorageStyle('----:com.apple.iTunes:replaygain_album_peak',
                         float_places=6),
        StorageStyle(u'REPLAYGAIN_ALBUM_PEAK',
                         float_places=6),
        ASFStorageStyle(u'replaygain_album_peak',
                         float_places=6),
        out_type=float,
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
        if isinstance(self.mgfile.info, mutagen.mp3.MPEGInfo):
            return {
                mutagen.mp3.STEREO: 2,
                mutagen.mp3.JOINTSTEREO: 2,
                mutagen.mp3.DUALCHANNEL: 2,
                mutagen.mp3.MONO: 1,
            }[self.mgfile.info.mode]
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
