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

MP4_TYPES = ('aac', 'alac')


# Utility.

def _safe_cast(out_type, val):
    """Tries to covert val to out_type but will never raise an
    exception. If the value can't be converted, then a sensible
    default value is returned. out_type should be bool, int, or
    unicode; otherwise, the value is just passed through.
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

class StorageStyle(object):
    """Parameterizes the storage behavior of a single field for a
    certain tag format.
     - key: The Mutagen key used to access the field's data.
     - list_elem: Store item as a single object or as first element
       of a list.
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

    For MP3 only:
      - id3_desc: match against this 'desc' field as well
        as the key.
      - id3_frame_field: store the data in this field of the frame
        object.
      - id3_lang: set the language field of the frame object.
    """
    def __init__(self, key, list_elem=True, as_type=unicode,
                 packing=None, pack_pos=0, pack_type=int,
                 id3_desc=None, id3_frame_field='text',
                 id3_lang=None, suffix=None, float_places=2):
        self.key = key
        self.list_elem = list_elem
        self.as_type = as_type
        self.packing = packing
        self.pack_pos = pack_pos
        self.pack_type = pack_type
        self.id3_desc = id3_desc
        self.id3_frame_field = id3_frame_field
        self.id3_lang = id3_lang
        self.suffix = suffix
        self.float_places = float_places

        # Convert suffix to correct string type.
        if self.suffix and self.as_type in (str, unicode):
            self.suffix = self.as_type(self.suffix)


# Dealing with packings.

class Packed(object):
    """Makes a packed list of values subscriptable. To access the packed
    output after making changes, use packed_thing.items.
    """
    def __init__(self, items, packstyle, out_type=int):
        """Create a Packed object for subscripting the packed values in
        items. The items are packed using packstyle, which is a value
        from the packing enum. Values are converted to out_type before
        they are returned.
        """
        self.items = items
        self.packstyle = packstyle
        self.out_type = out_type

        if out_type is int:
            self.none_val = 0
        elif out_type is float:
            self.none_val = 0.0
        else:
            self.none_val = None

    def __getitem__(self, index):
        if not isinstance(index, int):
            raise TypeError('index must be an integer')

        if self.items is None:
            return self.none_val

        items = self.items
        if self.packstyle == packing.DATE:
            # Remove time information from dates. Usually delimited by
            # a "T" or a space.
            items = re.sub(r'[Tt ].*$', '', unicode(items))

        # transform from a string packing into a list we can index into
        if self.packstyle == packing.SLASHED:
            seq = unicode(items).split('/')
        elif self.packstyle == packing.DATE:
            seq = unicode(items).split('-')
        elif self.packstyle == packing.TUPLE:
            seq = items # tuple: items is already indexable
        elif self.packstyle == packing.SC:
            seq = _sc_decode(items)

        try:
            out = seq[index]
        except:
            out = None

        if out is None or out == self.none_val or out == '':
            return _safe_cast(self.out_type, self.none_val)
        else:
            return _safe_cast(self.out_type, out)

    def __setitem__(self, index, value):
        # Interpret null values.
        if value is None:
            value = self.none_val

        if self.packstyle in (packing.SLASHED, packing.TUPLE, packing.SC):
            # SLASHED, TUPLE and SC are always two-item packings
            length = 2
        else:
            # DATE can have up to three fields
            length = 3

        # make a list of the items we'll pack
        new_items = []
        for i in range(length):
            if i == index:
                next_item = value
            else:
                next_item = self[i]
            new_items.append(next_item)

        if self.packstyle == packing.DATE:
            # Truncate the items wherever we reach an invalid (none)
            # entry. This prevents dates like 2008-00-05.
            for i, item in enumerate(new_items):
                if item == self.none_val or item is None:
                    del(new_items[i:]) # truncate
                    break

        if self.packstyle == packing.SLASHED:
            self.items = '/'.join(map(unicode, new_items))
        elif self.packstyle == packing.DATE:
            field_lengths = [4, 2, 2] # YYYY-MM-DD
            elems = []
            for i, item in enumerate(new_items):
                elems.append('{0:0{1}}'.format(int(item), field_lengths[i]))
            self.items = '-'.join(elems)
        elif self.packstyle == packing.TUPLE:
            self.items = new_items
        elif self.packstyle == packing.SC:
            self.items = _sc_encode(*new_items)


# The field itself.

class MediaField(object):
    """A descriptor providing access to a particular (abstract) metadata
    field. out_type is the type that users of MediaFile should see and
    can be unicode, int, or bool. id3, mp4, and flac are StorageStyle
    instances parameterizing the field's storage for each type.
    """
    def __init__(self, out_type=unicode, **kwargs):
        """Creates a new MediaField.
         - out_type: The field's semantic (exterior) type.
         - kwargs: A hash whose keys are 'mp3', 'mp4', 'asf', and 'etc'
           and whose values are StorageStyle instances
           parameterizing the field's storage for each type.
        """
        self.out_type = out_type
        if not set(['mp3', 'mp4', 'etc', 'asf']) == set(kwargs):
            raise TypeError('MediaField constructor must have keyword '
                            'arguments mp3, mp4, asf, and etc')
        self.styles = kwargs

    def _fetchdata(self, obj, style):
        """Get the value associated with this descriptor's field stored
        with the given StorageStyle. Unwraps from a list if necessary.
        """
        # fetch the value, which may be a scalar or a list
        if obj.type == 'mp3':
            if style.id3_desc is not None: # also match on 'desc' field
                frames = obj.mgfile.tags.getall(style.key)
                entry = None
                for frame in frames:
                    if frame.desc.lower() == style.id3_desc.lower():
                        entry = getattr(frame, style.id3_frame_field)
                        break
                if entry is None: # no desc match
                    return None
            else:
                # Get the metadata frame object.
                try:
                    frame = obj.mgfile[style.key]
                except KeyError:
                    return None

                entry = getattr(frame, style.id3_frame_field)

        else:  # Not MP3.
            try:
                entry = obj.mgfile[style.key]
            except KeyError:
                return None

        # Possibly index the list.
        if style.list_elem:
            if entry:  # List must have at least one value.
                # Handle Mutagen bugs when reading values (#356).
                try:
                    return entry[0]
                except:
                    log.error('Mutagen exception when reading field: %s' %
                              traceback.format_exc)
                    return None
            else:
                return None
        else:
            return entry

    def _storedata(self, obj, val, style):
        """Store val for this descriptor's field in the tag dictionary
        according to the provided StorageStyle. Store it as a
        single-item list if necessary.
        """
        # Wrap as a list if necessary.
        if style.list_elem:
            out = [val]
        else:
            out = val

        if obj.type == 'mp3':
            # Try to match on "desc" field.
            if style.id3_desc is not None:
                frames = obj.mgfile.tags.getall(style.key)

                # try modifying in place
                found = False
                for frame in frames:
                    if frame.desc.lower() == style.id3_desc.lower():
                        setattr(frame, style.id3_frame_field, out)
                        found = True
                        break

                # need to make a new frame?
                if not found:
                    assert isinstance(style.id3_frame_field, str)  # Keyword.
                    args = {
                        'encoding': 3,
                        'desc': style.id3_desc,
                        style.id3_frame_field: val,
                    }
                    if style.id3_lang:
                        args['lang'] = style.id3_lang
                    obj.mgfile.tags.add(mutagen.id3.Frames[style.key](**args))

            # Try to match on "owner" field.
            elif style.key.startswith('UFID:'):
                owner = style.key.split(':', 1)[1]
                frames = obj.mgfile.tags.getall(style.key)

                for frame in frames:
                    # Replace existing frame data.
                    if frame.owner == owner:
                        setattr(frame, style.id3_frame_field, val)
                else:
                    # New frame.
                    assert isinstance(style.id3_frame_field, str)  # Keyword.
                    frame = mutagen.id3.UFID(owner=owner,
                        **{style.id3_frame_field: val})
                    obj.mgfile.tags.setall('UFID', [frame])

            # Just replace based on key.
            else:
                assert isinstance(style.id3_frame_field, str)  # Keyword.
                frame = mutagen.id3.Frames[style.key](encoding=3,
                    **{style.id3_frame_field: val})
                obj.mgfile.tags.setall(style.key, [frame])

        else:  # Not MP3.
            obj.mgfile[style.key] = out

    def _styles(self, obj):
        if obj.type in ('mp3', 'asf'):
            styles = self.styles[obj.type]
        elif obj.type in MP4_TYPES:
            styles = self.styles['mp4']
        else:
            styles = self.styles['etc']  # Sane styles.

        # Make sure we always return a list of styles, even when given
        # a single style for convenience.
        if isinstance(styles, StorageStyle):
            return [styles]
        else:
            return styles

    def __get__(self, obj, owner):
        """Retrieve the value of this metadata field.
        """
        # Fetch the data using the various StorageStyles.
        styles = self._styles(obj)
        if styles is None:
            out = None
        else:
            for style in styles:
                # Use the first style that returns a reasonable value.
                out = self._fetchdata(obj, style)
                if out:
                    break

            if style.packing:
                p = Packed(out, style.packing, out_type=style.pack_type)
                out = p[style.pack_pos]

            # Remove suffix.
            if style.suffix and isinstance(out, (str, unicode)):
                if out.endswith(style.suffix):
                    out = out[:-len(style.suffix)]

            # MPEG-4 freeform frames are (should be?) encoded as UTF-8.
            if obj.type in MP4_TYPES and style.key.startswith('----:') and \
                    isinstance(out, str):
                out = out.decode('utf8')

        return _safe_cast(self.out_type, out)

    def __set__(self, obj, val):
        """Set the value of this metadata field.
        """
        # Store using every StorageStyle available.
        styles = self._styles(obj)
        if styles is None:
            return

        for style in styles:

            if style.packing:
                p = Packed(self._fetchdata(obj, style), style.packing,
                           out_type=style.pack_type)
                p[style.pack_pos] = val
                out = p.items

            else:  # Unicode, integer, boolean, or float scalar.
                out = val

                # deal with Nones according to abstract type if present
                if out is None:
                    if self.out_type == int:
                        out = 0
                    elif self.out_type == float:
                        out = 0.0
                    elif self.out_type == bool:
                        out = False
                    elif self.out_type == unicode:
                        out = u''
                    # We trust that packed values are handled above.

                # Convert to correct storage type (irrelevant for
                # packed values).
                if self.out_type == float and style.as_type in (str, unicode):
                    # Special case for float-valued data.
                    out = u'{0:.{1}f}'.format(out, style.float_places)
                    out = style.as_type(out)
                elif style.as_type == unicode:
                    if out is None:
                        out = u''
                    else:
                        if self.out_type == bool:
                            # Store bools as 1/0 instead of True/False.
                            out = unicode(int(bool(out)))
                        elif isinstance(out, str):
                            out = out.decode('utf8', 'ignore')
                        else:
                            out = unicode(out)
                elif style.as_type == int:
                    if out is None:
                        out = 0
                    else:
                        out = int(out)
                elif style.as_type in (bool, str):
                    out = style.as_type(out)

                # Add a suffix to string storage.
                if style.as_type in (str, unicode) and style.suffix:
                    out += style.suffix

            # MPEG-4 "freeform" (----) frames must be encoded as UTF-8
            # byte strings.
            if obj.type in MP4_TYPES and style.key.startswith('----:') and \
                    isinstance(out, unicode):
                out = out.encode('utf8')

            # Store the data.
            self._storedata(obj, out, style)

class CompositeDateField(object):
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

    def __get__(self, obj, owner):
        """Return a datetime.date object whose components indicating the
        smallest valid date whose components are at least as large as
        the three component fields (that is, if year == 1999, month == 0,
        and day == 0, then date == datetime.date(1999, 1, 1)). If the
        components indicate an invalid date (e.g., if month == 47),
        datetime.date.min is returned.
        """
        try:
            return datetime.date(
                max(self.year_field.__get__(obj, owner), datetime.MINYEAR),
                max(self.month_field.__get__(obj, owner), 1),
                max(self.day_field.__get__(obj, owner), 1)
            )
        except ValueError:  # Out of range values.
            return datetime.date.min

    def __set__(self, obj, val):
        """Set the year, month, and day fields to match the components of
        the provided datetime.date object.
        """
        self.year_field.__set__(obj, val.year)
        self.month_field.__set__(obj, val.month)
        self.day_field.__set__(obj, val.day)

class ImageField(object):
    """A descriptor providing access to a file's embedded album art.
    Holds a bytestring reflecting the image data. The image should
    either be a JPEG or a PNG for cross-format compatibility. It's
    probably a bad idea to use anything but these two formats.
    """
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

    @classmethod
    def _mp4kind(cls, data):
        """Return the MPEG-4 image type code of the data. If the image
        is not a PNG or JPEG, JPEG is assumed.
        """
        kind = imghdr.what(None, h=data)
        if kind == 'png':
            return mutagen.mp4.MP4Cover.FORMAT_PNG
        else:
            return mutagen.mp4.MP4Cover.FORMAT_JPEG

    def __get__(self, obj, owner):
        if obj.type == 'mp3':
            # Look for APIC frames.
            for frame in obj.mgfile.tags.values():
                if frame.FrameID == 'APIC':
                    picframe = frame
                    break
            else:
                # No APIC frame.
                return None

            return picframe.data

        elif obj.type in MP4_TYPES:
            if 'covr' in obj.mgfile:
                covers = obj.mgfile['covr']
                if covers:
                    cover = covers[0]
                    # cover is an MP4Cover, which is a subclass of str.
                    return cover

            # No cover found.
            return None

        elif obj.type == 'flac':
            pictures = obj.mgfile.pictures
            if pictures:
                return pictures[0].data or None
            else:
                return None

        elif obj.type == 'asf':
            if 'WM/Picture' in obj.mgfile:
                pictures = obj.mgfile['WM/Picture']
                if pictures:
                    data = pictures[0].value
                    try:
                        return _unpack_asf_image(data)[1]
                    except:
                        return None
            return None

        else:
            # Here we're assuming everything but MP3, MPEG-4, FLAC, and
            # ASF/WMA use the Xiph/Vorbis Comments standard. This may
            # not be valid. http://wiki.xiph.org/VorbisComment#Cover_art

            if 'metadata_block_picture' not in obj.mgfile:
                # Try legacy COVERART tags.
                if 'coverart' in obj.mgfile and obj.mgfile['coverart']:
                    return base64.b64decode(obj.mgfile['coverart'][0])
                return None

            for data in obj.mgfile["metadata_block_picture"]:
                try:
                    pic = mutagen.flac.Picture(base64.b64decode(data))
                    break
                except TypeError:
                    pass
            else:
                return None

            if not pic.data:
                return None

            return pic.data

    def __set__(self, obj, val):
        if val is not None:
            if not isinstance(val, str):
                raise ValueError('value must be a byte string or None')

        if obj.type == 'mp3':
            # Clear all APIC frames.
            obj.mgfile.tags.delall('APIC')
            if val is None:
                # If we're clearing the image, we're done.
                return

            picframe = mutagen.id3.APIC(
                encoding=3,
                mime=self._mime(val),
                type=3,  # Front cover.
                desc=u'',
                data=val,
            )
            obj.mgfile['APIC'] = picframe

        elif obj.type in MP4_TYPES:
            if val is None:
                if 'covr' in obj.mgfile:
                    del obj.mgfile['covr']
            else:
                cover = mutagen.mp4.MP4Cover(val, self._mp4kind(val))
                obj.mgfile['covr'] = [cover]

        elif obj.type == 'flac':
            obj.mgfile.clear_pictures()

            if val is not None:
                pic = mutagen.flac.Picture()
                pic.data = val
                pic.mime = self._mime(val)
                obj.mgfile.add_picture(pic)

        elif obj.type == 'asf':
            if 'WM/Picture' in obj.mgfile:
                del obj.mgfile['WM/Picture']

            if val is not None:
                pic = mutagen.asf.ASFByteArrayAttribute()
                pic.value = _pack_asf_image(self._mime(val), val)
                obj.mgfile['WM/Picture'] = [pic]

        else:
            # Again, assuming Vorbis Comments standard.

            # Strip all art, including legacy COVERART.
            if 'metadata_block_picture' in obj.mgfile:
                if 'metadata_block_picture' in obj.mgfile:
                    del obj.mgfile['metadata_block_picture']
                if 'coverart' in obj.mgfile:
                    del obj.mgfile['coverart']
                if 'coverartmime' in obj.mgfile:
                    del obj.mgfile['coverartmime']

            # Add new art if provided.
            if val is not None:
                pic = mutagen.flac.Picture()
                pic.data = val
                pic.mime = self._mime(val)
                obj.mgfile['metadata_block_picture'] = [
                    base64.b64encode(pic.write())
                ]


# The file (a collection of fields).

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
        mp3=StorageStyle('TIT2'),
        mp4=StorageStyle("\xa9nam"),
        etc=StorageStyle('TITLE'),
        asf=StorageStyle('Title'),
    )
    artist = MediaField(
        mp3=StorageStyle('TPE1'),
        mp4=StorageStyle("\xa9ART"),
        etc=StorageStyle('ARTIST'),
        asf=StorageStyle('Author'),
    )
    album = MediaField(
        mp3=StorageStyle('TALB'),
        mp4=StorageStyle("\xa9alb"),
        etc=StorageStyle('ALBUM'),
        asf=StorageStyle('WM/AlbumTitle'),
    )
    genre = MediaField(
        mp3=StorageStyle('TCON'),
        mp4=StorageStyle("\xa9gen"),
        etc=StorageStyle('GENRE'),
        asf=StorageStyle('WM/Genre'),
    )
    composer = MediaField(
        mp3=StorageStyle('TCOM'),
        mp4=StorageStyle("\xa9wrt"),
        etc=StorageStyle('COMPOSER'),
        asf=StorageStyle('WM/Composer'),
    )
    grouping = MediaField(
        mp3=StorageStyle('TIT1'),
        mp4=StorageStyle("\xa9grp"),
        etc=StorageStyle('GROUPING'),
        asf=StorageStyle('WM/ContentGroupDescription'),
    )
    track = MediaField(out_type=int,
        mp3=StorageStyle('TRCK', packing=packing.SLASHED, pack_pos=0),
        mp4=StorageStyle('trkn', packing=packing.TUPLE, pack_pos=0),
        etc=[StorageStyle('TRACK'),
             StorageStyle('TRACKNUMBER')],
        asf=StorageStyle('WM/TrackNumber'),
    )
    tracktotal = MediaField(out_type=int,
        mp3=StorageStyle('TRCK', packing=packing.SLASHED, pack_pos=1),
        mp4=StorageStyle('trkn', packing=packing.TUPLE, pack_pos=1),
        etc=[StorageStyle('TRACKTOTAL'),
             StorageStyle('TRACKC'),
             StorageStyle('TOTALTRACKS')],
        asf=StorageStyle('TotalTracks'),
    )
    disc = MediaField(out_type=int,
        mp3=StorageStyle('TPOS', packing=packing.SLASHED, pack_pos=0),
        mp4=StorageStyle('disk', packing=packing.TUPLE, pack_pos=0),
        etc=[StorageStyle('DISC'),
             StorageStyle('DISCNUMBER')],
        asf=StorageStyle('WM/PartOfSet'),
    )
    disctotal = MediaField(out_type=int,
        mp3=StorageStyle('TPOS', packing=packing.SLASHED, pack_pos=1),
        mp4=StorageStyle('disk', packing=packing.TUPLE, pack_pos=1),
        etc=[StorageStyle('DISCTOTAL'),
             StorageStyle('DISCC'),
             StorageStyle('TOTALDISCS')],
        asf=StorageStyle('TotalDiscs'),
    )
    lyrics = MediaField(
        mp3=StorageStyle('USLT', list_elem=False, id3_desc=u''),
        mp4=StorageStyle("\xa9lyr"),
        etc=StorageStyle('LYRICS'),
        asf=StorageStyle('WM/Lyrics'),
    )
    comments = MediaField(
        mp3=StorageStyle('COMM', id3_desc=u''),
        mp4=StorageStyle("\xa9cmt"),
        etc=[StorageStyle('DESCRIPTION'),
             StorageStyle('COMMENT')],
        asf=StorageStyle('WM/Comments'),
    )
    bpm = MediaField(
        out_type=int,
        mp3=StorageStyle('TBPM'),
        mp4=StorageStyle('tmpo', as_type=int),
        etc=StorageStyle('BPM'),
        asf=StorageStyle('WM/BeatsPerMinute'),
    )
    comp = MediaField(
        out_type=bool,
        mp3=StorageStyle('TCMP'),
        mp4=StorageStyle('cpil', list_elem=False, as_type=bool),
        etc=StorageStyle('COMPILATION'),
        asf=StorageStyle('WM/IsCompilation', as_type=bool),
    )
    albumartist = MediaField(
        mp3=StorageStyle('TPE2'),
        mp4=StorageStyle('aART'),
        etc=[StorageStyle('ALBUM ARTIST'),
             StorageStyle('ALBUMARTIST')],
        asf=StorageStyle('WM/AlbumArtist'),
    )
    albumtype = MediaField(
        mp3=StorageStyle('TXXX', id3_desc=u'MusicBrainz Album Type'),
        mp4=StorageStyle('----:com.apple.iTunes:MusicBrainz Album Type'),
        etc=StorageStyle('MUSICBRAINZ_ALBUMTYPE'),
        asf=StorageStyle('MusicBrainz/Album Type'),
    )
    label = MediaField(
        mp3=StorageStyle('TPUB'),
        mp4=[StorageStyle('----:com.apple.iTunes:Label'),
             StorageStyle('----:com.apple.iTunes:publisher')],
        etc=[StorageStyle('LABEL'),
             StorageStyle('PUBLISHER')],  # Traktor
        asf=StorageStyle('WM/Publisher'),
    )
    artist_sort = MediaField(
        mp3=StorageStyle('TSOP'),
        mp4=StorageStyle("soar"),
        etc=StorageStyle('ARTISTSORT'),
        asf=StorageStyle('WM/ArtistSortOrder'),
    )
    albumartist_sort = MediaField(
        mp3=StorageStyle('TXXX', id3_desc=u'ALBUMARTISTSORT'),
        mp4=StorageStyle("soaa"),
        etc=StorageStyle('ALBUMARTISTSORT'),
        asf=StorageStyle('WM/AlbumArtistSortOrder'),
    )
    asin = MediaField(
        mp3=StorageStyle('TXXX', id3_desc=u'ASIN'),
        mp4=StorageStyle("----:com.apple.iTunes:ASIN"),
        etc=StorageStyle('ASIN'),
        asf=StorageStyle('MusicBrainz/ASIN'),
    )
    catalognum = MediaField(
        mp3=StorageStyle('TXXX', id3_desc=u'CATALOGNUMBER'),
        mp4=StorageStyle("----:com.apple.iTunes:CATALOGNUMBER"),
        etc=StorageStyle('CATALOGNUMBER'),
        asf=StorageStyle('WM/CatalogNo'),
    )
    disctitle = MediaField(
        mp3=StorageStyle('TSST'),
        mp4=StorageStyle("----:com.apple.iTunes:DISCSUBTITLE"),
        etc=StorageStyle('DISCSUBTITLE'),
        asf=StorageStyle('WM/SetSubTitle'),
    )
    encoder = MediaField(
        mp3=StorageStyle('TENC'),
        mp4=StorageStyle("\xa9too"),
        etc=[StorageStyle('ENCODEDBY'),
             StorageStyle('ENCODER')],
        asf=StorageStyle('WM/EncodedBy'),
    )
    script = MediaField(
        mp3=StorageStyle('TXXX', id3_desc=u'Script'),
        mp4=StorageStyle("----:com.apple.iTunes:SCRIPT"),
        etc=StorageStyle('SCRIPT'),
        asf=StorageStyle('WM/Script'),
    )
    language = MediaField(
        mp3=StorageStyle('TLAN'),
        mp4=StorageStyle("----:com.apple.iTunes:LANGUAGE"),
        etc=StorageStyle('LANGUAGE'),
        asf=StorageStyle('WM/Language'),
    )
    country = MediaField(
        mp3=StorageStyle('TXXX', id3_desc='MusicBrainz Album Release Country'),
        mp4=StorageStyle("----:com.apple.iTunes:MusicBrainz Album "
                         "Release Country"),
        etc=StorageStyle('RELEASECOUNTRY'),
        asf=StorageStyle('MusicBrainz/Album Release Country'),
    )
    albumstatus = MediaField(
        mp3=StorageStyle('TXXX', id3_desc=u'MusicBrainz Album Status'),
        mp4=StorageStyle("----:com.apple.iTunes:MusicBrainz Album Status"),
        etc=StorageStyle('MUSICBRAINZ_ALBUMSTATUS'),
        asf=StorageStyle('MusicBrainz/Album Status'),
    )
    media = MediaField(
        mp3=StorageStyle('TMED'),
        mp4=StorageStyle("----:com.apple.iTunes:MEDIA"),
        etc=StorageStyle('MEDIA'),
        asf=StorageStyle('WM/Media'),
    )
    albumdisambig = MediaField(
        # This tag mapping was invented for beets (not used by Picard, etc).
        mp3=StorageStyle('TXXX', id3_desc=u'MusicBrainz Album Comment'),
        mp4=StorageStyle("----:com.apple.iTunes:MusicBrainz Album Comment"),
        etc=StorageStyle('MUSICBRAINZ_ALBUMCOMMENT'),
        asf=StorageStyle('MusicBrainz/Album Comment'),
    )

    # Release date.
    year = MediaField(
        out_type=int,
        mp3=StorageStyle('TDRC', packing=packing.DATE, pack_pos=0),
        mp4=StorageStyle("\xa9day", packing=packing.DATE, pack_pos=0),
        etc=[StorageStyle('DATE', packing=packing.DATE, pack_pos=0),
             StorageStyle('YEAR')],
        asf=StorageStyle('WM/Year', packing=packing.DATE, pack_pos=0),
    )
    month = MediaField(
        out_type=int,
        mp3=StorageStyle('TDRC', packing=packing.DATE, pack_pos=1),
        mp4=StorageStyle("\xa9day", packing=packing.DATE, pack_pos=1),
        etc=StorageStyle('DATE', packing=packing.DATE, pack_pos=1),
        asf=StorageStyle('WM/Year', packing=packing.DATE, pack_pos=1),
    )
    day = MediaField(
        out_type=int,
        mp3=StorageStyle('TDRC', packing=packing.DATE, pack_pos=2),
        mp4=StorageStyle("\xa9day", packing=packing.DATE, pack_pos=2),
        etc=StorageStyle('DATE', packing=packing.DATE, pack_pos=2),
        asf=StorageStyle('WM/Year', packing=packing.DATE, pack_pos=2),
    )
    date = CompositeDateField(year, month, day)

    # *Original* release date.
    original_year = MediaField(out_type=int,
        mp3=StorageStyle('TDOR', packing=packing.DATE, pack_pos=0),
        mp4=StorageStyle('----:com.apple.iTunes:ORIGINAL YEAR',
                         packing=packing.DATE, pack_pos=0),
        etc=StorageStyle('ORIGINALDATE', packing=packing.DATE, pack_pos=0),
        asf=StorageStyle('WM/OriginalReleaseYear', packing=packing.DATE,
                         pack_pos=0),
    )
    original_month = MediaField(out_type=int,
        mp3=StorageStyle('TDOR', packing=packing.DATE, pack_pos=1),
        mp4=StorageStyle('----:com.apple.iTunes:ORIGINAL YEAR',
                         packing=packing.DATE, pack_pos=1),
        etc=StorageStyle('ORIGINALDATE', packing=packing.DATE, pack_pos=1),
        asf=StorageStyle('WM/OriginalReleaseYear', packing=packing.DATE,
                         pack_pos=1),
    )
    original_day = MediaField(out_type=int,
        mp3=StorageStyle('TDOR', packing=packing.DATE, pack_pos=2),
        mp4=StorageStyle('----:com.apple.iTunes:ORIGINAL YEAR',
                         packing=packing.DATE, pack_pos=2),
        etc=StorageStyle('ORIGINALDATE', packing=packing.DATE, pack_pos=2),
        asf=StorageStyle('WM/OriginalReleaseYear', packing=packing.DATE,
                         pack_pos=2),
    )
    original_date = CompositeDateField(original_year, original_month,
                                       original_day)

    # Nonstandard metadata.
    artist_credit = MediaField(
        mp3=StorageStyle('TXXX', id3_desc=u'Artist Credit'),
        mp4=StorageStyle("----:com.apple.iTunes:Artist Credit"),
        etc=StorageStyle('ARTIST_CREDIT'),
        asf=StorageStyle('beets/Artist Credit'),
    )
    albumartist_credit = MediaField(
        mp3=StorageStyle('TXXX', id3_desc=u'Album Artist Credit'),
        mp4=StorageStyle("----:com.apple.iTunes:Album Artist Credit"),
        etc=StorageStyle('ALBUMARTIST_CREDIT'),
        asf=StorageStyle('beets/Album Artist Credit'),
    )

    # Album art.
    art = ImageField()

    # MusicBrainz IDs.
    mb_trackid = MediaField(
        mp3=StorageStyle('UFID:http://musicbrainz.org',
                          list_elem=False,
                          id3_frame_field='data'),
        mp4=StorageStyle('----:com.apple.iTunes:MusicBrainz Track Id',
                         as_type=str),
        etc=StorageStyle('MUSICBRAINZ_TRACKID'),
        asf=StorageStyle('MusicBrainz/Track Id'),
    )
    mb_albumid = MediaField(
        mp3=StorageStyle('TXXX', id3_desc=u'MusicBrainz Album Id'),
        mp4=StorageStyle('----:com.apple.iTunes:MusicBrainz Album Id',
                         as_type=str),
        etc=StorageStyle('MUSICBRAINZ_ALBUMID'),
        asf=StorageStyle('MusicBrainz/Album Id'),
    )
    mb_artistid = MediaField(
        mp3=StorageStyle('TXXX', id3_desc=u'MusicBrainz Artist Id'),
        mp4=StorageStyle('----:com.apple.iTunes:MusicBrainz Artist Id',
                         as_type=str),
        etc=StorageStyle('MUSICBRAINZ_ARTISTID'),
        asf=StorageStyle('MusicBrainz/Artist Id'),
    )
    mb_albumartistid = MediaField(
        mp3=StorageStyle('TXXX',
                          id3_desc=u'MusicBrainz Album Artist Id'),
        mp4=StorageStyle('----:com.apple.iTunes:MusicBrainz Album Artist Id',
                         as_type=str),
        etc=StorageStyle('MUSICBRAINZ_ALBUMARTISTID'),
        asf=StorageStyle('MusicBrainz/Album Artist Id'),
    )
    mb_releasegroupid = MediaField(
        mp3=StorageStyle('TXXX',
                          id3_desc=u'MusicBrainz Release Group Id'),
        mp4=StorageStyle('----:com.apple.iTunes:MusicBrainz Release Group Id',
                         as_type=str),
        etc=StorageStyle('MUSICBRAINZ_RELEASEGROUPID'),
        asf=StorageStyle('MusicBrainz/Release Group Id'),
    )

    # Acoustid fields.
    acoustid_fingerprint = MediaField(
        mp3=StorageStyle('TXXX',
                          id3_desc=u'Acoustid Fingerprint'),
        mp4=StorageStyle('----:com.apple.iTunes:Acoustid Fingerprint',
                         as_type=str),
        etc=StorageStyle('ACOUSTID_FINGERPRINT'),
        asf=StorageStyle('Acoustid/Fingerprint'),
    )
    acoustid_id = MediaField(
        mp3=StorageStyle('TXXX',
                         id3_desc=u'Acoustid Id'),
        mp4=StorageStyle('----:com.apple.iTunes:Acoustid Id',
                         as_type=str),
        etc=StorageStyle('ACOUSTID_ID'),
        asf=StorageStyle('Acoustid/Id'),
    )

    # ReplayGain fields.
    rg_track_gain = MediaField(out_type=float,
        mp3=[StorageStyle('TXXX', id3_desc=u'REPLAYGAIN_TRACK_GAIN',
                          float_places=2, suffix=u' dB'),
             StorageStyle('COMM', id3_desc=u'iTunNORM', id3_lang='eng',
                          packing=packing.SC, pack_pos=0, pack_type=float)],
        mp4=[StorageStyle('----:com.apple.iTunes:replaygain_track_gain',
                          as_type=str, float_places=2, suffix=b' dB'),
             StorageStyle('----:com.apple.iTunes:iTunNORM',
                          packing=packing.SC, pack_pos=0, pack_type=float)],
        etc=StorageStyle(u'REPLAYGAIN_TRACK_GAIN',
                         float_places=2, suffix=u' dB'),
        asf=StorageStyle(u'replaygain_track_gain',
                         float_places=2, suffix=u' dB'),
    )
    rg_album_gain = MediaField(out_type=float,
        mp3=StorageStyle('TXXX', id3_desc=u'REPLAYGAIN_ALBUM_GAIN',
                         float_places=2, suffix=u' dB'),
        mp4=StorageStyle('----:com.apple.iTunes:replaygain_album_gain',
                         as_type=str, float_places=2, suffix=b' dB'),
        etc=StorageStyle(u'REPLAYGAIN_ALBUM_GAIN',
                         float_places=2, suffix=u' dB'),
        asf=StorageStyle(u'replaygain_album_gain',
                         float_places=2, suffix=u' dB'),
    )
    rg_track_peak = MediaField(out_type=float,
        mp3=[StorageStyle('TXXX', id3_desc=u'REPLAYGAIN_TRACK_PEAK',
                          float_places=6),
             StorageStyle('COMM', id3_desc=u'iTunNORM', id3_lang='eng',
                          packing=packing.SC, pack_pos=1, pack_type=float)],
        mp4=[StorageStyle('----:com.apple.iTunes:replaygain_track_peak',
                          as_type=str, float_places=6),
             StorageStyle('----:com.apple.iTunes:iTunNORM',
                          packing=packing.SC, pack_pos=1, pack_type=float)],
        etc=StorageStyle(u'REPLAYGAIN_TRACK_PEAK',
                         float_places=6),
        asf=StorageStyle(u'replaygain_track_peak',
                         float_places=6),
    )
    rg_album_peak = MediaField(out_type=float,
        mp3=StorageStyle('TXXX', id3_desc=u'REPLAYGAIN_ALBUM_PEAK',
                         float_places=6),
        mp4=StorageStyle('----:com.apple.iTunes:replaygain_album_peak',
                         as_type=str, float_places=6),
        etc=StorageStyle(u'REPLAYGAIN_ALBUM_PEAK',
                         float_places=6),
        asf=StorageStyle(u'replaygain_album_peak',
                         float_places=6),
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
