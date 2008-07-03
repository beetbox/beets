"""Handles low-level interfacing for files' tags. Wraps mutagen to
automatically detect file types and provide a unified interface for the
specific tags Beets is interested in."""

from mutagen import mp4, mp3, id3
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





class MediaField(object):
    """A descriptor providing access to a particular (abstract) metadata
    field. The various messy parameters control the translation to concrete
    metadata manipulations in the language of mutagen."""
    
    # possible types used to store the relevant data
    TYPE_RAW =     0      # stored as a single object (not in a list)
    TYPE_LIST =    1 << 0 # stored in the first element of a list
    TYPE_UNICODE = 1 << 1 # stored as a unicode object
    TYPE_INTEGER = 1 << 2 # as an int
    TYPE_BOOLEAN = 1 << 3 # as a bool
    # RAW and LIST are mutually exclusive, as are UNICODE, INTEGER and
    # BOOLEAN. Must pick either RAW or LIST, but none of the other types
    # are necessary.
    
    # non-type aspects of data storage
    STYLE_PLAIN =   0      # no filtering
    STYLE_UNICODE = 1 << 0 # value is a string, stored as a string
    STYLE_INTEGER = 1 << 1 # value is an integer, maybe stored as a string
    STYLE_BOOLEAN = 1 << 2 # value is a boolean, probably stored as a string
    STYLE_SLASHED = 1 << 3 # int stored in a string on one side of a / char
    STYLE_2PLE =    1 << 4 # stored as one value in an integer 2-tuple
    # The above styles are all mutually exclusive.
    STYLE_LEFT =    1 << 5 # for SLASHED or 2PLE, value is in first entry
    STYLE_RIGHT =   1 << 6 # likewise, in second entry
    # These are mutually exclusive and relevant only with SLASHED and 2PLE.
    
    def __init__(self, id3key, mp4key,
            # in ID3 tags, use only the frame with this "desc" field
            id3desc=None,
            # compositions of the TYPE_ flag above
            id3type=TYPE_UNICODE|TYPE_LIST, mp4type=TYPE_UNICODE|TYPE_LIST,
            # compositions of STYLE_ flags
            id3style=STYLE_UNICODE, mp4style=STYLE_UNICODE
            ):
        
        self.keys = { 'mp3': id3key,
                      'mp4': mp4key }
        self.types = { 'mp3': id3type,
                       'mp4': mp4type }
        self.styles = { 'mp3': id3style,
                        'mp4': mp4style }
        self.id3desc = id3desc
    
    def _fetchdata(self, obj):
        """Get the value associated with this descriptor's key (and id3desc if
        present) from the mutagen tag dict. Unwraps from a list if
        necessary."""
        (mykey, mytype, mystyle) = self._params(obj)
        
        try:
            # fetch the value, which may be a scalar or a list
            if obj.type == 'mp3':
                if self.id3desc is not None: # also match on 'desc' field
                    frames = obj.tags.tags.getall(mykey)
                    entry = None
                    for frame in frames:
                        if frame.desc == self.id3desc:
                            entry = frame.text
                            break
                    if entry is None: # no desc match
                        return None
                else:
                    entry = obj.tags[mykey].text
            else:
                entry = obj.tags[mykey]
            
            # possibly index the list
            if mytype & self.TYPE_LIST:
                return entry[0]
            else:
                return entry
        except KeyError: # the tag isn't present
            return None
    
    def _storedata(self, obj, val):
        """Store val for this descriptor's key in the tag dictionary. Store it
        as a single-item list if necessary. Uses id3desc if present."""
        (mykey, mytype, mystyle) = self._params(obj)
        
        # wrap as a list if necessary
        if mytype & self.TYPE_LIST: out = [val]
        else:                       out = val
        
        if obj.type == 'mp3':
            if self.id3desc is not None: # match on id3desc
                frames = obj.tags.tags.getall(mykey)
                
                # try modifying in place
                found = False
                for frame in frames:
                    if frame.desc == self.id3desc:
                        frame.text = out
                        found = True
                        break
                
                # need to make a new frame?
                if not found:
                    frame = id3.Frames[mykey](encoding=3, desc=self.id3desc,
                                              text=val)
                    obj.tags.tags.add(frame)
            
            else: # no match on desc; just replace based on key
                frame = id3.Frames[mykey](encoding=3, text=val)
                obj.tags.tags.setall(mykey, [frame])
        else:
            obj.tags[mykey] = out
    
    def _params(self, obj):
        return (self.keys[obj.type],
                self.types[obj.type],
                self.styles[obj.type])
    
    def __get__(self, obj, owner):
        """Retrieve the value of this metadata field."""
        out = None
        (mykey, mytype, mystyle) = self._params(obj)
        
        out = self._fetchdata(obj)
        
        # deal with slashed and tuple storage
        if mystyle & self.STYLE_SLASHED or mystyle & self.STYLE_2PLE:
            if mystyle & self.STYLE_SLASHED:
                out = fromslashed(out)
            out = unpair(out, mystyle & self.STYLE_RIGHT, noneval=0)
        
        # return the appropriate type
        if mystyle & self.STYLE_INTEGER or mystyle & self.STYLE_SLASHED \
                    or mystyle & self.STYLE_2PLE:
            if out is None:
                return 0
            else:
                try:
                    return int(out)
                except: # in case out is not convertible directly to an int
                    return int(unicode(out))
        elif mystyle & self.STYLE_BOOLEAN:
            if out is None:
                return False
            else:
                return bool(int(out)) # should work for strings, bools, ints
        elif mystyle & self.STYLE_UNICODE:
            if out is None:
                return u''
            else:
                return unicode(out)
        else:
            return out
    
    def __set__(self, obj, val):
        """Set the value of this metadata field."""
        (mykey, mytype, mystyle) = self._params(obj)
        
        # apply style filters
        if mystyle & self.STYLE_SLASHED or mystyle & self.STYLE_2PLE:
            # fetch the existing value so we can preserve half of it
            pair = self._fetchdata(obj)
            if mystyle & self.STYLE_SLASHED:
                pair = fromslashed(pair)
            pair = normalize_pair(pair, noneval=0)
            
            # set the appropriate side of the pair
            if mystyle & self.STYLE_LEFT:
                pair = (val, pair[1])
            else:
                pair = (pair[0], val)
            
            if mystyle & self.STYLE_SLASHED:
                out = toslashed(pair)
            else:
                out = pair
        else: # plain, integer, or boolean
            out = val
        
        # deal with Nones according to abstract type if present
        if out is None:
            if mystyle & self.STYLE_INTEGER:
                out = 0
            elif mystyle & self.STYLE_BOOLEAN:
                out = False
            elif mystyle & self.STYLE_UNICODE:
                out = u''
            # We trust that SLASHED and 2PLE are handled above.
        
        # convert to correct storage type
        if mytype & self.TYPE_UNICODE:
            if out is None:
                out = u''
            else:
                if mystyle & self.STYLE_BOOLEAN:
                    # store bools as 1,0 instead of True,False
                    out = unicode(int(out))
                else:
                    out = unicode(out)
        elif mytype & self.TYPE_INTEGER:
            if out is None:
                out = 0
            else:
                out = int(out)
        elif mytype & self.TYPE_BOOLEAN:
            out = bool(out)
        
        # store the data
        self._storedata(obj, out)




class MediaFile(object):
    """Represents a multimedia file on disk and provides access to its
    metadata."""
    
    def __init__(self, path):
        root, ext = os.path.splitext(path)
        if ext == '.mp3':
            self.type = 'mp3'
            self.tags = mp3.Open(path)
        elif ext == '.m4a' or ext == '.mp4' or ext == '.m4b' or ext == '.m4p':
            self.type = 'mp4'
            self.tags = mp4.Open(path)
        else:
            raise FileTypeError('unsupported file extension: ' + ext)
    
    def save_tags(self):
        self.tags.save()
    
    
    #### field definitions ####
    
    title = MediaField('TIT2', "\xa9nam")
    artist = MediaField('TPE1', "\xa9ART")
    album = MediaField('TALB', "\xa9alb")
    genre = MediaField('TCON', "\xa9gen")
    composer = MediaField('TCOM', "\xa9wrt")
    grouping = MediaField('TIT1', "\xa9grp")
    year = MediaField('TDRC', "\xa9day",
                id3style=MediaField.STYLE_INTEGER,
                mp4style=MediaField.STYLE_INTEGER)
    track = MediaField('TRCK', 'trkn',
                id3style=MediaField.STYLE_SLASHED | MediaField.STYLE_LEFT,
                mp4type=MediaField.TYPE_LIST,
                mp4style=MediaField.STYLE_2PLE | MediaField.STYLE_LEFT)
    maxtrack = MediaField('TRCK', 'trkn',
                id3style=MediaField.STYLE_SLASHED | MediaField.STYLE_RIGHT,
                mp4type=MediaField.TYPE_LIST,
                mp4style=MediaField.STYLE_2PLE | MediaField.STYLE_RIGHT)
    disc = MediaField('TPOS', 'disk',
                id3style=MediaField.STYLE_SLASHED | MediaField.STYLE_LEFT,
                mp4type=MediaField.TYPE_LIST,
                mp4style=MediaField.STYLE_2PLE | MediaField.STYLE_LEFT)
    maxdisc = MediaField('TPOS', 'disk',
                id3style=MediaField.STYLE_SLASHED | MediaField.STYLE_RIGHT,
                mp4type=MediaField.TYPE_LIST,
                mp4style=MediaField.STYLE_2PLE | MediaField.STYLE_RIGHT)
    lyrics = MediaField(u"USLT", "\xa9lyr", id3desc=u'',
                id3type=MediaField.TYPE_UNICODE)
    comments = MediaField(u"COMM", "\xa9cmt", id3desc=u'')
    bpm = MediaField('TBPM', 'tmpo',
                id3style=MediaField.STYLE_INTEGER,
                mp4type=MediaField.TYPE_LIST | MediaField.TYPE_INTEGER,
                mp4style=MediaField.STYLE_INTEGER)
    comp = MediaField('TCMP', 'cpil',
                id3style=MediaField.STYLE_BOOLEAN,
                mp4type=MediaField.TYPE_BOOLEAN,
                mp4style=MediaField.STYLE_BOOLEAN)
