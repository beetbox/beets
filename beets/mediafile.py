# This file is part of beets.
# Copyright 2009, Adrian Sampson.
# 
# Beets is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Beets is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with beets.  If not, see <http://www.gnu.org/licenses/>.

"""Handles low-level interfacing for files' tags. Wraps Mutagen to
automatically detect file types and provide a unified interface for a useful
subset of music files' tags.

Usage:

    >>> f = MediaFile('Lucy.mp3')
    >>> f.title
    u'Lucy in the Sky with Diamonds'
    >>> f.artist = 'The Beatles'
    >>> f.save()

A field will always return a reasonable value of the correct type, even if no
tag is present. If no value is available, the value will be false (e.g., zero
or the empty string).
"""

import mutagen
import datetime
import re

__all__ = ['FileTypeError', 'MediaFile']

# Currently allowed values for type:
# mp3, mp4
class FileTypeError(IOError):
    pass





#### flags used to define fields' behavior ####

class Enumeration(object):
    def __init__(self, *values):
        for value, equiv in zip(values, range(1, len(values)+1)):
            setattr(self, value, equiv)
# determine style of packing if any
packing = Enumeration('SLASHED', # pair delimited by /
                      'TUPLE',   # a python tuple of 2 items
                      'DATE'     # YYYY-MM-DD
                     )

class StorageStyle(object):
    """Parameterizes the storage behavior of a single field for a certain tag
    format.
    """
    def __init__(self,
                 # The Mutagen key used to access the data for this field.
                 key,
                 # Store item as a single object or as first element of a list.
                 list_elem = True,
                 # Which type the value is stored as (unicode, int, or bool).
                 as_type = unicode,
                 # If this value is packed in a multiple-value storage unit,
                 # which type of packing (in the packing enum). Otherwise,
                 # None. (Makes as_type irrelevant).
                 packing = None,
                 # If the value is packed, in which position it is stored.
                 pack_pos = 0,
                 # ID3 storage only: match against this 'desc' field as well
                 # as the key.
                 id3_desc = None):
        self.key = key
        self.list_elem = list_elem
        self.as_type = as_type
        self.packing = packing
        self.pack_pos = pack_pos
        self.id3_desc = id3_desc




#### dealing with packings ####

class Packed(object):
    """Makes a packed list of values subscriptable. To access the packed output
    after making changes, use packed_thing.items.
    """
    
    def __init__(self, items, packstyle, none_val=0, out_type=int):
        """Create a Packed object for subscripting the packed values in items.
        The items are packed using packstyle, which is a value from the
        packing enum. none_val is returned from a request when no suitable
        value is found in the items. Vales are converted to out_type before
        they are returned.
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
            return self.out_type(self.none_val)
        else:
            return self.out_type(out)
    
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
            # Truncate the items wherever we reach an invalid (none) entry.
            # This prevents dates like 2008-00-05.
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
        


class MediaField(object):
    """A descriptor providing access to a particular (abstract) metadata
    field. out_type is the type that users of MediaFile should see and can
    be unicode, int, or bool. id3, mp4, and flac are StorageStyle instances
    parameterizing the field's storage for each type.
    """
    
    def __init__(self,
            # The field's semantic (exterior) type.
            out_type = unicode,
            # A hash whose keys are 'mp3', 'mp4', and 'flac' and whose values
            # are StorageStyle instances parameterizing the field's storage for
            # each type.
            **kwargs
            ):
            
        self.out_type = out_type
        if not set(['mp3', 'mp4', 'flac']) == set(kwargs):
            raise TypeError('MediaField constructor must have keyword '
                            'arguments mp3, mp4, and flac only')
        self.styles = kwargs
    
    def _fetchdata(self, obj):
        """Get the value associated with this descriptor's key (and id3_desc if
        present) from the mutagen tag dict. Unwraps from a list if
        necessary.
        """
        style = self._style(obj)
        
        try:
            # fetch the value, which may be a scalar or a list
            if obj.type == 'mp3':
                if style.id3_desc is not None: # also match on 'desc' field
                    frames = obj.mgfile.tags.getall(style.key)
                    entry = None
                    for frame in frames:
                        if frame.desc == style.id3_desc:
                            entry = frame.text
                            break
                    if entry is None: # no desc match
                        return None
                else:
                    entry = obj.mgfile[style.key].text
            else:
                entry = obj.mgfile[style.key]
            
            # possibly index the list
            if style.list_elem:
                if entry: # List must have at least one value.
                    return entry[0]
                else:
                    return None
            else:
                return entry

        except KeyError: # the tag isn't present
            return None
    
    def _storedata(self, obj, val):
        """Store val for this descriptor's key in the tag dictionary. Store it
        as a single-item list if necessary. Uses id3_desc if present.
        """
        style = self._style(obj)
        
        # wrap as a list if necessary
        if style.list_elem: out = [val]
        else:               out = val
        
        if obj.type == 'mp3':
            if style.id3_desc is not None: # match on desc field
                frames = obj.mgfile.tags.getall(style.key)
                
                # try modifying in place
                found = False
                for frame in frames:
                    if frame.desc == style.id3_desc:
                        frame.text = out
                        found = True
                        break
                
                # need to make a new frame?
                if not found:
                    frame = mutagen.id3.Frames[style.key](
                                encoding=3, desc=style.id3_desc, text=val)
                    obj.mgfile.tags.add(frame)
            
            else: # no match on desc; just replace based on key
                frame = mutagen.id3.Frames[style.key](encoding=3, text=val)
                obj.mgfile.tags.setall(style.key, [frame])
        else:
            obj.mgfile[style.key] = out
    
    def _style(self, obj): return self.styles[obj.type]
    
    def __get__(self, obj, owner):
        """Retrieve the value of this metadata field.
        """
        style = self._style(obj)
        out = self._fetchdata(obj)
        
        if style.packing:
            out = Packed(out, style.packing)[style.pack_pos]
        
        # return the appropriate type
        if self.out_type == int:
            if out is None:
                return 0
            else:
                try:
                    return int(out)
                except: # in case out is not convertible directly to an int
                    return int(unicode(out))
        elif self.out_type == bool:
            if out is None:
                return False
            else:
                return bool(int(out)) # should work for strings, bools, ints
        elif self.out_type == unicode:
            if out is None:
                return u''
            else:
                return unicode(out)
        else:
            return out
    
    def __set__(self, obj, val):
        """Set the value of this metadata field.
        """
        style = self._style(obj)
        
        if style.packing:
            p = Packed(self._fetchdata(obj), style.packing)
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
        
            # convert to correct storage type (irrelevant for packed values)
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
            elif style.as_type == bool:
                out = bool(out)
        
        # store the data
        self._storedata(obj, out)

class CompositeDateField(object):
    """A MediaFile field for conveniently accessing the year, month, and day
    fields as a datetime.date object. Allows both getting and setting of the
    component fields.
    """
    def __init__(self, year_field, month_field, day_field):
        """Create a new date field from the indicated MediaFields for the
        component values.
        """
        self.year_field = year_field
        self.month_field = month_field
        self.day_field = day_field
        
    def __get__(self, obj, owner):
        """Return a datetime.date object whose components indicating the
        smallest valid date whose components are at least as large as the
        three component fields (that is, if year == 1999, month == 0, and
        day == 0, then date == datetime.date(1999, 1, 1)). If the components
        indicate an invalid date (e.g., if month == 47), datetime.date.min is
        returned.
        """
        try:
            return datetime.date(max(self.year_field.__get__(obj, owner),
                                     datetime.MINYEAR),
                                 max(self.month_field.__get__(obj, owner), 1),
                                 max(self.day_field.__get__(obj, owner), 1)
                                )
        except ValueError: # Out of range values.
            return datetime.date.min
    
    def __set__(self, obj, val):
        """Set the year, month, and day fields to match the components of the
        provided datetime.date object.
        """
        self.year_field.__set__(obj, val.year)
        self.month_field.__set__(obj, val.month)
        self.day_field.__set__(obj, val.day)



class MediaFile(object):
    """Represents a multimedia file on disk and provides access to its
    metadata.
    """
    
    def __init__(self, path):
        try:
            self.mgfile = mutagen.File(path)
        except mutagen.mp3.HeaderNotFoundError:
            raise FileTypeError('Mutagen could not read file')

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
        else:
            raise FileTypeError('file type unsupported by MediaFile')
        
        # add a set of tags if it's missing
        if not self.mgfile.tags:
            self.mgfile.add_tags()
    
    def save(self):
        self.mgfile.save()
    
    
    #### field definitions ####
    
    title = MediaField(
                mp3  = StorageStyle('TIT2'),
                mp4  = StorageStyle("\xa9nam"), 
                flac = StorageStyle('title')
            )
    artist = MediaField(
                mp3  = StorageStyle('TPE1'),
                mp4  = StorageStyle("\xa9ART"), 
                flac = StorageStyle('artist')
            )     
    album = MediaField(
                mp3  = StorageStyle('TALB'),
                mp4  = StorageStyle("\xa9alb"), 
                flac = StorageStyle('album')
            )
    genre = MediaField(
                mp3  = StorageStyle('TCON'),
                mp4  = StorageStyle("\xa9gen"), 
                flac = StorageStyle('genre')
            )
    composer = MediaField(
                mp3  = StorageStyle('TCOM'),
                mp4  = StorageStyle("\xa9wrt"), 
                flac = StorageStyle('composer')
            )
    grouping = MediaField(
                mp3  = StorageStyle('TIT1'),
                mp4  = StorageStyle("\xa9grp"), 
                flac = StorageStyle('grouping')
            )
    year = MediaField(out_type=int,
                mp3  = StorageStyle('TDRC',
                                    packing = packing.DATE,
                                    pack_pos = 0),
                mp4  = StorageStyle("\xa9day",
                                    packing = packing.DATE,
                                    pack_pos = 0), 
                flac = StorageStyle('date',
                                    packing = packing.DATE,
                                    pack_pos = 0)
            )
    month = MediaField(out_type=int,
                mp3  = StorageStyle('TDRC',
                                    packing = packing.DATE,
                                    pack_pos = 1),
                mp4  = StorageStyle("\xa9day",
                                    packing = packing.DATE,
                                    pack_pos = 1), 
                flac = StorageStyle('date',
                                    packing = packing.DATE,
                                    pack_pos = 1)
            )
    day = MediaField(out_type=int,
                mp3  = StorageStyle('TDRC',
                                    packing = packing.DATE,
                                    pack_pos = 2),
                mp4  = StorageStyle("\xa9day",
                                    packing = packing.DATE,
                                    pack_pos = 2), 
                flac = StorageStyle('date',
                                    packing = packing.DATE,
                                    pack_pos = 2)
            )
    date = CompositeDateField(year, month, day)
    track = MediaField(out_type = int,
                mp3  = StorageStyle('TRCK',
                                    packing = packing.SLASHED,
                                    pack_pos = 0),
                mp4  = StorageStyle('trkn',
                                    packing = packing.TUPLE,
                                    pack_pos = 0),
                flac = StorageStyle('tracknumber')
            )
    tracktotal = MediaField(out_type = int,
                mp3  = StorageStyle('TRCK',
                                    packing = packing.SLASHED,
                                    pack_pos = 1),
                mp4  = StorageStyle('trkn',
                                    packing = packing.TUPLE,
                                    pack_pos = 1),
                flac = StorageStyle('tracktotal')
            )
    disc = MediaField(out_type = int,
                mp3  = StorageStyle('TPOS',
                                    packing = packing.SLASHED,
                                    pack_pos = 0),
                mp4  = StorageStyle('disk',
                                    packing = packing.TUPLE,
                                    pack_pos = 0),
                flac = StorageStyle('disc')
            )
    disctotal = MediaField(out_type = int,
                mp3  = StorageStyle('TPOS',
                                    packing = packing.SLASHED,
                                    pack_pos = 1),
                mp4  = StorageStyle('disk',
                                    packing = packing.TUPLE,
                                    pack_pos = 1),
                flac = StorageStyle('disctotal')
            )
    lyrics = MediaField(
                mp3  = StorageStyle('USLT',
                                    list_elem = False,
                                    id3_desc = u''),
                mp4  = StorageStyle("\xa9lyr"), 
                flac = StorageStyle('lyrics')
            )
    comments = MediaField(
                mp3  = StorageStyle('COMM', id3_desc = u''),
                mp4  = StorageStyle("\xa9cmt"), 
                flac = StorageStyle('description')
            )
    bpm = MediaField(out_type = int,
                mp3  = StorageStyle('TBPM'),
                mp4  = StorageStyle('tmpo', as_type = int), 
                flac = StorageStyle('bpm')
            )
    comp = MediaField(out_type = bool,
                mp3  = StorageStyle('TCMP'),
                mp4  = StorageStyle('cpil',
                                    list_elem = False,
                                    as_type = bool), 
                flac = StorageStyle('compilation')
            )

    @property
    def length(self):
        return self.mgfile.info.length

    @property
    def bitrate(self):
        if self.type == 'flac':
            return self.mgfile.info.sample_rate * \
                   self.mgfile.info.bits_per_sample
        else:
            return self.mgfile.info.bitrate

