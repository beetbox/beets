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
                 # Store item as a single object or as first element of a list.
                 list_elem = True,
                 # Which type the value is stored as (unicode, int, or bool).
                 as_type = unicode,
                 # If this value is packed in a multiple-value storage unit,
                 # which type of packing (in the packing enum). Otherwise,
                 # None. (Makes as_type irrelevant).
                 packing = None,
                 # If the value is packed, in which position it is stored.
                 pack_pos = 0):
        self.list_elem = list_elem
        self.as_type = as_type
        self.packing = packing
        self.pack_pos = pack_pos





class MediaField(object):
    """A descriptor providing access to a particular (abstract) metadata
    field. The various messy parameters control the translation to concrete
    metadata manipulations in the language of mutagen."""
    
    def __init__(self, id3key, mp4key, flackey,
            # in ID3 tags, use only the frame with this "desc" field
            id3desc=None,
            # the field's semantic (exterior) type
            out_type = unicode,
            # StorageStyle instances parameterizing the field's storage
            id3_style =  StorageStyle(),
            mp4_style =  StorageStyle(),
            flac_style = StorageStyle()
            ):
            
        self.id3desc = id3desc
        self.out_type = out_type
        self.keys = { 'mp3':  id3key,
                      'mp4':  mp4key,
                      'flac': flackey }
        self.styles = { 'mp3':  id3_style,
                        'mp4':  mp4_style,
                        'flac': flac_style }
    
    def _fetchdata(self, obj):
        """Get the value associated with this descriptor's key (and id3desc if
        present) from the mutagen tag dict. Unwraps from a list if
        necessary."""
        (key, style) = self._params(obj)
        
        try:
            # fetch the value, which may be a scalar or a list
            if obj.type == 'mp3':
                if self.id3desc is not None: # also match on 'desc' field
                    frames = obj.mgfile.tags.getall(key)
                    entry = None
                    for frame in frames:
                        if frame.desc == self.id3desc:
                            entry = frame.text
                            break
                    if entry is None: # no desc match
                        return None
                else:
                    entry = obj.mgfile[key].text
            else:
                entry = obj.mgfile[key]
            
            # possibly index the list
            if style.list_elem:
                return entry[0]
            else:
                return entry
        except KeyError: # the tag isn't present
            return None
    
    def _storedata(self, obj, val):
        """Store val for this descriptor's key in the tag dictionary. Store it
        as a single-item list if necessary. Uses id3desc if present."""
        (key, style) = self._params(obj)
        
        # wrap as a list if necessary
        if style.list_elem: out = [val]
        else:             out = val
        
        if obj.type == 'mp3':
            if self.id3desc is not None: # match on id3desc
                frames = obj.mgfile.tags.getall(key)
                
                # try modifying in place
                found = False
                for frame in frames:
                    if frame.desc == self.id3desc:
                        frame.text = out
                        found = True
                        break
                
                # need to make a new frame?
                if not found:
                    frame = mutagen.id3.Frames[key](
                                encoding=3, desc=self.id3desc, text=val)
                    obj.mgfile.tags.add(frame)
            
            else: # no match on desc; just replace based on key
                frame = mutagen.id3.Frames[key](encoding=3, text=val)
                obj.mgfile.tags.setall(key, [frame])
        else:
            obj.mgfile[key] = out
    
    def _params(self, obj):
        return (self.keys[obj.type],
                self.styles[obj.type])
    
    def __get__(self, obj, owner):
        """Retrieve the value of this metadata field."""
        (key, style) = self._params(obj)
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
        (key, style) = self._params(obj)
        
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
    
    title = MediaField('TIT2', "\xa9nam", 'title')
    artist = MediaField('TPE1', "\xa9ART", 'artist')
    album = MediaField('TALB', "\xa9alb", 'album')
    genre = MediaField('TCON', "\xa9gen", 'genre')
    composer = MediaField('TCOM', "\xa9wrt", 'composer')
    grouping = MediaField('TIT1', "\xa9grp", 'grouping')
    year = MediaField('TDRC', "\xa9day", 'date', out_type=int)
    track = MediaField('TRCK', 'trkn', 'tracknumber',
                id3_style = StorageStyle(packing = packing.SLASHED,
                                pack_pos = 0),
                mp4_style = StorageStyle(packing = packing.TUPLE,     
                                pack_pos = 0),                              
                out_type = int)
    tracktotal = MediaField('TRCK', 'trkn', 'tracktotal',
                id3_style = StorageStyle(packing = packing.SLASHED,
                                pack_pos = 1),
                mp4_style = StorageStyle(packing = packing.TUPLE,     
                                pack_pos = 1),
                out_type = int)
    disc = MediaField('TPOS', 'disk', 'disc',
                id3_style = StorageStyle(packing = packing.SLASHED,
                                pack_pos = 0),
                mp4_style = StorageStyle(packing = packing.TUPLE,     
                                pack_pos = 0),
                out_type = int)
    disctotal = MediaField('TPOS', 'disk', 'disctotal',
                id3_style = StorageStyle(packing = packing.SLASHED,
                                pack_pos = 1),
                mp4_style = StorageStyle(packing = packing.TUPLE,     
                                pack_pos = 1),
                out_type = int)
    lyrics = MediaField(u"USLT", "\xa9lyr", 'lyrics',
                id3desc = u'',
                id3_style = StorageStyle(list_elem = False))
    comments = MediaField(u"COMM", "\xa9cmt", 'description',
                id3desc = u'')
    bpm = MediaField('TBPM', 'tmpo', 'bpm',
                mp4_style = StorageStyle(as_type = int),
                out_type = int)
    comp = MediaField('TCMP', 'cpil', 'compilation',
                mp4_style = StorageStyle(list_elem = False, as_type = bool),
                out_type = bool)
