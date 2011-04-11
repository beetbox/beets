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
import mutagen.oggvorbis
import mutagen.mp4
import mutagen.flac
import mutagen.monkeysaudio
import datetime
import re
from beets.util.enumeration import enum

__all__ = ['UnreadableFileError', 'FileTypeError', 'MediaFile']


# Exceptions.

# Raised for any file MediaFile can't read.
class UnreadableFileError(IOError):
    pass

# Raised for files that don't seem to have a type MediaFile supports.
class FileTypeError(UnreadableFileError):
    pass


# Constants.

# Human-readable type names.
TYPES = {
    'mp3':  'MP3',
    'mp4':  'AAC',
    'ogg':  'OGG',
    'flac': 'FLAC',
    'ape':  'APE',
    'wv':   'WavPack',
    'mpc':  'Musepack',
}


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
            val = re.match('[0-9]*', val.strip()).group(0)
            if not val:
                return 0
            else:
                return int(val)

    elif out_type == bool:
        if val is None:
            return False
        else:
            try:
                # Should work for strings, bools, ints:
                return bool(int(val)) 
            except ValueError:
                return False

    elif out_type == unicode:
        if val is None:
            return u''
        else:
            return unicode(val)

    else:
        return val


# Flags for encoding field behavior.

# Determine style of packing, if any.
packing = enum('SLASHED', # pair delimited by /
               'TUPLE',   # a python tuple of 2 items
               'DATE',    # YYYY-MM-DD
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
     - ID3 storage only: match against this 'desc' field as well
       as the key.
    """
    def __init__(self, key, list_elem = True, as_type = unicode,
                 packing = None, pack_pos = 0, id3_desc = None,
                 id3_frame_field = u'text'):
        self.key = key
        self.list_elem = list_elem
        self.as_type = as_type
        self.packing = packing
        self.pack_pos = pack_pos
        self.id3_desc = id3_desc
        self.id3_frame_field = id3_frame_field


# Dealing with packings.

class Packed(object):
    """Makes a packed list of values subscriptable. To access the packed
    output after making changes, use packed_thing.items.
    """
    
    def __init__(self, items, packstyle, none_val=0, out_type=int):
        """Create a Packed object for subscripting the packed values in
        items. The items are packed using packstyle, which is a value
        from the packing enum. none_val is returned from a request when
        no suitable value is found in the items. Vales are converted to
        out_type before they are returned.
        """
        self.items = items
        self.packstyle = packstyle
        self.none_val = none_val
        self.out_type = out_type
    
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
    
        try:
            out = seq[index]
        except:
            out = None
    
        if out is None or out == self.none_val or out == '':
            return _safe_cast(self.out_type, self.none_val)
        else:
            return _safe_cast(self.out_type, out)
    
    def __setitem__(self, index, value):
        if self.packstyle in (packing.SLASHED, packing.TUPLE):
            # SLASHED and TUPLE are always two-item packings
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
                elems.append( ('%0' + str(field_lengths[i]) + 'i') % item )
            self.items = '-'.join(elems)
        elif self.packstyle == packing.TUPLE:
            self.items = new_items
        

# The field itself.

class MediaField(object):
    """A descriptor providing access to a particular (abstract) metadata
    field. out_type is the type that users of MediaFile should see and
    can be unicode, int, or bool. id3, mp4, and flac are StorageStyle
    instances parameterizing the field's storage for each type.
    """
    
    def __init__(self, out_type = unicode, **kwargs):
        """Creates a new MediaField.
         - out_type: The field's semantic (exterior) type.
         - kwargs: A hash whose keys are 'mp3', 'mp4', and 'etc'
           and whose values are StorageStyle instances
           parameterizing the field's storage for each type.
        """
        self.out_type = out_type
        if not set(['mp3', 'mp4', 'etc']) == set(kwargs):
            raise TypeError('MediaField constructor must have keyword '
                            'arguments mp3, mp4, and etc')
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
                    if frame.desc == style.id3_desc:
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
        
        else: # Not MP3.
            try:
                entry = obj.mgfile[style.key]
            except KeyError:
                return None
        
        # possibly index the list
        if style.list_elem:
            if entry: # List must have at least one value.
                return entry[0]
            else:
                return None
        else:
            return entry
    
    def _storedata(self, obj, val, style):
        """Store val for this descriptor's field in the tag dictionary
        according to the provided StorageStyle. Store it as a
        single-item list if necessary.
        """
        # wrap as a list if necessary
        if style.list_elem: out = [val]
        else:               out = val
        
        if obj.type == 'mp3':
            # Try to match on "desc" field.
            if style.id3_desc is not None:
                frames = obj.mgfile.tags.getall(style.key)
                
                # try modifying in place
                found = False
                for frame in frames:
                    if frame.desc == style.id3_desc:
                        setattr(frame, style.id3_frame_field, out)
                        found = True
                        break
                
                # need to make a new frame?
                if not found:
                    frame = mutagen.id3.Frames[style.key](
                        encoding=3,
                        desc=style.id3_desc,
                        **{style.id3_frame_field: val}
                    )
                    obj.mgfile.tags.add(frame)
            
            # Try to match on "owner" field.
            #TODO reduce redundancy here
            elif style.key.startswith('UFID:'):
                owner = style.key.split(':', 1)[1]
                frames = obj.mgfile.tags.getall(style.key)
                
                for frame in frames:
                    # Replace existing frame data.
                    if frame.owner == owner:
                        setattr(frame, style.id3_frame_field, val)
                else:
                    # New frame.
                    frame = mutagen.id3.UFID(owner=owner, 
                        **{style.id3_frame_field: val})
                    obj.mgfile.tags.setall('UFID', [frame])
                    
            # Just replace based on key.
            else:
                frame = mutagen.id3.Frames[style.key](encoding = 3,
                    **{style.id3_frame_field: val})
                obj.mgfile.tags.setall(style.key, [frame])
        
        else: # Not MP3.
            obj.mgfile[style.key] = out
    
    def _styles(self, obj):
        if obj.type in ('mp3', 'mp4'):
            styles = self.styles[obj.type]
        else:
            styles = self.styles['etc'] # sane styles
            
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
        for style in styles:
            # Use the first style that returns a reasonable value.
            out = self._fetchdata(obj, style)
            if out:
                break
        
        if style.packing:
            out = Packed(out, style.packing)[style.pack_pos]
        
        return _safe_cast(self.out_type, out)
    
    def __set__(self, obj, val):
        """Set the value of this metadata field.
        """
        # Store using every StorageStyle available.
        styles = self._styles(obj)
        for style in styles:
        
            if style.packing:
                p = Packed(self._fetchdata(obj, style), style.packing)
                p[style.pack_pos] = val
                out = p.items
                
            else: # unicode, integer, or boolean scalar
                out = val
        
                # deal with Nones according to abstract type if present
                if out is None:
                    if self.out_type == int:
                        out = 0
                    elif self.out_type == bool:
                        out = False
                    elif self.out_type == unicode:
                        out = u''
                    # We trust that packed values are handled above.
        
                # convert to correct storage type (irrelevant for
                # packed values)
                if style.as_type == unicode:
                    if out is None:
                        out = u''
                    else:
                        if self.out_type == bool:
                            # store bools as 1,0 instead of True,False
                            out = unicode(int(out))
                        else:
                            out = unicode(out)
                elif style.as_type == int:
                    if out is None:
                        out = 0
                    else:
                        out = int(out)
                elif style.as_type in (bool, str):
                    out = style.as_type(out)
        
            # store the data
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
        except ValueError: # Out of range values.
            return datetime.date.min
    
    def __set__(self, obj, val):
        """Set the year, month, and day fields to match the components of
        the provided datetime.date object.
        """
        self.year_field.__set__(obj, val.year)
        self.month_field.__set__(obj, val.month)
        self.day_field.__set__(obj, val.day)


# The file (a collection of fields).

class MediaFile(object):
    """Represents a multimedia file on disk and provides access to its
    metadata.
    """
    
    def __init__(self, path):
        """Constructs a new MediaFile reflecting the file at path. May
        throw UnreadableFileError.
        """
        unreadable_exc = (
            mutagen.mp3.HeaderNotFoundError,
            mutagen.flac.FLACNoHeaderError,
            mutagen.monkeysaudio.MonkeysAudioHeaderError,
            mutagen.mp4.MP4StreamInfoError,
            mutagen.oggvorbis.OggVorbisHeaderError,
        )
        try:
            self.mgfile = mutagen.File(path)
        except unreadable_exc:
            raise UnreadableFileError('Mutagen could not read file')
        except IOError:
            raise UnreadableFileError('could not read file')

        if self.mgfile is None: # Mutagen couldn't guess the type
            raise FileTypeError('file type unsupported by Mutagen')
        elif type(self.mgfile).__name__ == 'M4A' or \
             type(self.mgfile).__name__ == 'MP4':
            self.type = 'mp4'
        elif type(self.mgfile).__name__ == 'ID3' or \
             type(self.mgfile).__name__ == 'MP3':
            self.type = 'mp3'
        elif type(self.mgfile).__name__ == 'FLAC':
            self.type = 'flac'
        elif type(self.mgfile).__name__ == 'OggVorbis':
            self.type = 'ogg'
        elif type(self.mgfile).__name__ == 'MonkeysAudio':
            self.type = 'ape'
        elif type(self.mgfile).__name__ == 'WavPack':
            self.type = 'wv'
        elif type(self.mgfile).__name__ == 'Musepack':
            self.type = 'mpc'
        else:
            raise FileTypeError('file type %s unsupported by MediaFile' %
                                type(self.mgfile).__name__)
        
        # add a set of tags if it's missing
        if self.mgfile.tags is None:
            self.mgfile.add_tags()
    
    def save(self):
        self.mgfile.save()
    
    
    #### field definitions ####
    
    title = MediaField(
                mp3 = StorageStyle('TIT2'),
                mp4 = StorageStyle("\xa9nam"), 
                etc = StorageStyle('title'),
            )
    artist = MediaField(
                mp3 = StorageStyle('TPE1'),
                mp4 = StorageStyle("\xa9ART"), 
                etc = StorageStyle('artist'),
            )     
    album = MediaField(
                mp3 = StorageStyle('TALB'),
                mp4 = StorageStyle("\xa9alb"), 
                etc = StorageStyle('album'),
            )
    genre = MediaField(
                mp3 = StorageStyle('TCON'),
                mp4 = StorageStyle("\xa9gen"), 
                etc = StorageStyle('genre'),
            )
    composer = MediaField(
                mp3 = StorageStyle('TCOM'),
                mp4 = StorageStyle("\xa9wrt"), 
                etc = StorageStyle('composer'),
            )
    grouping = MediaField(
                mp3 = StorageStyle('TIT1'),
                mp4 = StorageStyle("\xa9grp"), 
                etc = StorageStyle('grouping'),
            )
    year = MediaField(out_type=int,
                mp3 = StorageStyle('TDRC',
                                    packing = packing.DATE,
                                    pack_pos = 0),
                mp4 = StorageStyle("\xa9day",
                                    packing = packing.DATE,
                                    pack_pos = 0), 
                etc = [StorageStyle('date',
                                     packing = packing.DATE,
                                     pack_pos = 0),
                       StorageStyle('year')]
            )
    month = MediaField(out_type=int,
                mp3 = StorageStyle('TDRC',
                                    packing = packing.DATE,
                                    pack_pos = 1),
                mp4 = StorageStyle("\xa9day",
                                    packing = packing.DATE,
                                    pack_pos = 1), 
                etc = StorageStyle('date',
                                    packing = packing.DATE,
                                    pack_pos = 1)
            )
    day = MediaField(out_type=int,
                mp3 = StorageStyle('TDRC',
                                    packing = packing.DATE,
                                    pack_pos = 2),
                mp4 = StorageStyle("\xa9day",
                                    packing = packing.DATE,
                                    pack_pos = 2), 
                etc = StorageStyle('date',
                                    packing = packing.DATE,
                                    pack_pos = 2)
            )
    date = CompositeDateField(year, month, day)
    track = MediaField(out_type = int,
                mp3 = StorageStyle('TRCK',
                                    packing = packing.SLASHED,
                                    pack_pos = 0),
                mp4 = StorageStyle('trkn',
                                    packing = packing.TUPLE,
                                    pack_pos = 0),
                etc = [StorageStyle('track'),
                       StorageStyle('tracknumber')]
            )
    tracktotal = MediaField(out_type = int,
                mp3 = StorageStyle('TRCK',
                                    packing = packing.SLASHED,
                                    pack_pos = 1),
                mp4 = StorageStyle('trkn',
                                    packing = packing.TUPLE,
                                    pack_pos = 1),
                etc = [StorageStyle('tracktotal'),
                       StorageStyle('trackc'),
                       StorageStyle('totaltracks')]
            )
    disc = MediaField(out_type = int,
                mp3 = StorageStyle('TPOS',
                                    packing = packing.SLASHED,
                                    pack_pos = 0),
                mp4 = StorageStyle('disk',
                                    packing = packing.TUPLE,
                                    pack_pos = 0),
                etc = [StorageStyle('disc'),
                       StorageStyle('discnumber')]
            )
    disctotal = MediaField(out_type = int,
                mp3 = StorageStyle('TPOS',
                                    packing = packing.SLASHED,
                                    pack_pos = 1),
                mp4 = StorageStyle('disk',
                                    packing = packing.TUPLE,
                                    pack_pos = 1),
                etc = [StorageStyle('disctotal'),
                       StorageStyle('discc'),
                       StorageStyle('totaldiscs')]
            )
    lyrics = MediaField(
                mp3 = StorageStyle('USLT',
                                    list_elem = False,
                                    id3_desc = u''),
                mp4 = StorageStyle("\xa9lyr"), 
                etc = StorageStyle('lyrics')
            )
    comments = MediaField(
                mp3 = StorageStyle('COMM', id3_desc = u''),
                mp4 = StorageStyle("\xa9cmt"), 
                etc = [StorageStyle('description'),
                       StorageStyle('comment')]
            )
    bpm = MediaField(out_type = int,
                mp3 = StorageStyle('TBPM'),
                mp4 = StorageStyle('tmpo', as_type = int), 
                etc = StorageStyle('bpm')
            )
    comp = MediaField(out_type = bool,
                mp3 = StorageStyle('TCMP'),
                mp4 = StorageStyle('cpil',
                                    list_elem = False,
                                    as_type = bool), 
                etc = StorageStyle('compilation')
            )
    albumartist = MediaField(
                mp3 = StorageStyle('TXXX', id3_desc=u'Album Artist'),
                mp4 = StorageStyle(
                    '----:com.apple.iTunes:Album Artist',
                    as_type=str),
                etc = [StorageStyle('album artist'),
                       StorageStyle('albumartist')]
            )
    albumtype = MediaField(
                mp3 = StorageStyle('TXXX', id3_desc=u'MusicBrainz Album Type'),
                mp4 = StorageStyle(
                    '----:com.apple.iTunes:MusicBrainz Album Type',
                    as_type=str),
                etc = StorageStyle('musicbrainz_albumtype')
            )
    albumart = MediaField(
                mp3 = StorageStyle('APIC', id3_frame_field=u'data',
                                   as_type=str),
                mp4 = StorageStyle('covr', as_type=str),
                etc = StorageStyle('picture', as_type=str)
            )
    albumart_mime = MediaField(
                mp3 = StorageStyle('APIC', id3_desc=u'Cover',
                                   id3_frame_field=u'mime'),
                mp4 = None,
                etc = None
            )

    # MusicBrainz IDs.
    mb_trackid = MediaField(
                mp3 = StorageStyle('UFID:http://musicbrainz.org',
                                   list_elem = False,
                                   id3_frame_field = u'data'),
                mp4 = StorageStyle(
                    '----:com.apple.iTunes:MusicBrainz Track Id',
                    as_type=str),
                etc = StorageStyle('musicbrainz_trackid')
            )
    mb_albumid = MediaField(
                mp3 = StorageStyle('TXXX', id3_desc=u'MusicBrainz Album Id'),
                mp4 = StorageStyle(
                    '----:com.apple.iTunes:MusicBrainz Album Id',
                    as_type=str),
                etc = StorageStyle('musicbrainz_albumid')
            )
    mb_artistid = MediaField(
                mp3 = StorageStyle('TXXX', id3_desc=u'MusicBrainz Artist Id'),
                mp4 = StorageStyle(
                    '----:com.apple.iTunes:MusicBrainz Artist Id',
                    as_type=str),
                etc = StorageStyle('musicbrainz_artistid')
            )
    mb_albumartistid = MediaField(
                mp3 = StorageStyle('TXXX',
                                   id3_desc=u'MusicBrainz Album Artist Id'),
                mp4 = StorageStyle(
                    '----:com.apple.iTunes:MusicBrainz Album Artist Id',
                    as_type=str),
                etc = StorageStyle('musicbrainz_albumartistid')
            )

    @property
    def length(self):
        return self.mgfile.info.length

    @property
    def bitrate(self):
        if self.type in ('flac', 'ape'):
            if hasattr(self.mgfile.info, 'bits_per_sample'):
                # Simulate bitrate for lossless formats.
                #fixme: The utility of this guess is questionable.
                return self.mgfile.info.sample_rate * \
                       self.mgfile.info.bits_per_sample
            else:
                # Old APE file format.
                return 0
        elif self.type == 'wv':
            # Mutagen doesn't provide enough information.
            return 0
        else:
            return self.mgfile.info.bitrate

    @property
    def format(self):
        return TYPES[self.type]
