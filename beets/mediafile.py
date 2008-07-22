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
or the empty string)."""

import mutagen
import os.path

__all__ = ['FileTypeError', 'MediaFile']

# Currently allowed values for type:
# mp3, mp4
class FileTypeError(IOError):
    pass



#### utility functions ####

def fromslashed(slashed, sep=u'/'):
    """Extract a pair of items from a slashed string. If only one
    value is present, it is assumed to be the left-hand value."""
    
    if slashed is None:
        return (None, None)
    
    items = slashed.split(sep)
    
    if len(items) == 1:
        out = (items[0], None)
    else:
        out = (items[0], items[1])
    
    # represent "nothing stored" more gracefully
    if out[0] == '': out[0] = None
    if out[1] == '': out[1] = None
    
    return out

def toslashed(pair_or_val, sep=u'/'):
    """Store a pair of items or a single item in a slashed string. If
    only one value is provided (in a list/tuple or as a single value),
    no slash is used."""
    if type(pair_or_val) is list or type(pair_or_val) is tuple:
        if len(pair_or_val) == 0:
            out = [u'']
        elif len(pair_or_val) == 1:
            out = [unicode(pair_or_val[0])]
        else:
            out = [unicode(pair_or_val[0]), unicode(pair_or_val[1])]
    else: # "scalar"
        out = [unicode(pair_or_val)]
    return sep.join(out)

def unpair(pair, right=False, noneval=None):
    """Return the left or right value in a pair (as selected by the "right"
    parameter. If the value on that side is not available, return noneval.)"""
    if right: idx = 1
    else: idx = 0
    
    try:
        out = pair[idx]
    except:
        out = None
    finally:
        if out is None:
            return noneval
        else:
            return out

def normalize_pair(pair, noneval=None):
    """Make sure the pair is a tuple that has exactly two entries. If we need
    to fill anything in, we'll use noneval."""
    return (unpair(pair, False, noneval),
            unpair(pair, True, noneval))




#### flags used to define fields' behavior ####

class Enumeration(object):
    def __init__(self, *values):
        for value, equiv in zip(values, range(1, len(values)+1)):
            setattr(self, value, equiv)
packing = Enumeration('SLASHED', 'TUPLE')

class StorageStyle(object):
    """Parameterizes the storage behavior of a single field for a certain tag
    format."""
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





class MediaField(object):
    """A descriptor providing access to a particular (abstract) metadata
    field. out_type is the type that users of MediaFile should see and can
    be unicode, int, or bool. id3, mp4, and flac are StorageStyle instances
    parameterizing the field's storage for each type."""
    
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
        necessary."""
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
                return entry[0]
            else:
                return entry
        except KeyError: # the tag isn't present
            return None
    
    def _storedata(self, obj, val):
        """Store val for this descriptor's key in the tag dictionary. Store it
        as a single-item list if necessary. Uses id3_desc if present."""
        style = self._style(obj)
        
        # wrap as a list if necessary
        if style.list_elem: out = [val]
        else:             out = val
        
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
        """Retrieve the value of this metadata field."""
        style = self._style(obj)
        out = self._fetchdata(obj)
        
        # deal with slashed and tuple storage
        if style.packing:
            if style.packing == packing.SLASHED:
                out = fromslashed(out)
            out = unpair(out, style.pack_pos, noneval=0)
        
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
        """Set the value of this metadata field."""
        style = self._style(obj)
        
        if style.packing:
            # fetch the existing value so we can preserve half of it
            pair = self._fetchdata(obj)
            if style.packing == packing.SLASHED:
                pair = fromslashed(pair)
            pair = normalize_pair(pair, noneval=0)
            
            # set the appropriate side of the pair
            if style.pack_pos == 0:
                pair = (val, pair[1])
            else:
                pair = (pair[0], val)
            
            if style.packing == packing.SLASHED:
                out = toslashed(pair)
            else:
                out = pair
                
        else: # unicode, integer, or boolean
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







class MediaFile(object):
    """Represents a multimedia file on disk and provides access to its
    metadata."""
    
    def __init__(self, path):
        self.mgfile = mutagen.File(path)
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
                mp3  = StorageStyle('TDRC'),
                mp4  = StorageStyle("\xa9day"), 
                flac = StorageStyle('date')
            )
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
            
