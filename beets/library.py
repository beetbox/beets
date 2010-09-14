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

import sqlite3
import os
import re
import shutil
import sys
from string import Template
import logging
import platform
from beets.mediafile import MediaFile, UnreadableFileError, FileTypeError
from beets import plugins

MAX_FILENAME_LENGTH = 200

# Fields in the "items" database table; all the metadata available for
# items in the library. These are used directly in SQL; they are
# vulnerable to injection if accessible to the user.
# Each tuple has the following values:
# - The name of the field.
# - The (SQLite) type of the field.
# - Is the field writable?
# - Does the field reflect an attribute of a MediaFile?
ITEM_FIELDS = [
    ('id',          'integer primary key', False, False),
    ('path',        'blob', False, False),
    ('album_id',    'int',  False, False),

    ('title',       'text', True,  True),
    ('artist',      'text', True,  True),
    ('album',       'text', True,  True),
    ('genre',       'text', True,  True),
    ('composer',    'text', True,  True),
    ('grouping',    'text', True,  True),
    ('year',        'int',  True,  True),
    ('month',       'int',  True,  True),
    ('day',         'int',  True,  True),
    ('track',       'int',  True,  True),
    ('tracktotal',  'int',  True,  True),
    ('disc',        'int',  True,  True),
    ('disctotal',   'int',  True,  True),
    ('lyrics',      'text', True,  True),
    ('comments',    'text', True,  True),
    ('bpm',         'int',  True,  True),
    ('comp',        'bool', True,  True),
    ('mb_trackid',  'text', True,  True),
    ('mb_albumid',  'text', True,  True),
    ('mb_artistid', 'text', True,  True),

    ('length',      'real', False, True),
    ('bitrate',     'int',  False, True),
    ('format',      'text', False, True),
]
ITEM_KEYS_WRITABLE = [f[0] for f in ITEM_FIELDS if f[3] and f[2]]
ITEM_KEYS_META     = [f[0] for f in ITEM_FIELDS if f[3]]
ITEM_KEYS          = [f[0] for f in ITEM_FIELDS]

# Database fields for the "albums" table.
# The third entry in each tuple indicates whether the field reflects an
# identically-named field in the items table.
ALBUM_FIELDS = [
    ('id', 'integer primary key', False),
    ('artpath', 'blob', False),

    ('artist',      'text', True),
    ('album',       'text', True),
    ('genre',       'text', True),
    ('year',        'int',  True),
    ('month',       'int',  True),
    ('day',         'int',  True),
    ('tracktotal',  'int',  True),
    ('disctotal',   'int',  True),
    ('comp',        'bool', True),
    ('mb_albumid',  'text', True),
    ('mb_artistid', 'text', True),
]
ALBUM_KEYS = [f[0] for f in ALBUM_FIELDS]
ALBUM_KEYS_ITEM = [f[0] for f in ALBUM_FIELDS if f[2]]

# Default search fields for various granularities.
ARTIST_DEFAULT_FIELDS = ('artist',)
ALBUM_DEFAULT_FIELDS = ARTIST_DEFAULT_FIELDS + ('album', 'genre')
ITEM_DEFAULT_FIELDS = ALBUM_DEFAULT_FIELDS + ('title', 'comments')

# Logger.
log = logging.getLogger('beets')
log.addHandler(logging.StreamHandler())


# Exceptions.

class InvalidFieldError(Exception):
    pass


# Utility functions.

def _normpath(path):
    """Provide the canonical form of the path suitable for storing in
    the database.
    """
    return os.path.normpath(os.path.abspath(os.path.expanduser(path)))

def _ancestry(path):
    """Return a list consisting of path's parent directory, its
    grandparent, and so on. For instance:
       >>> _ancestry('/a/b/c')
       ['/', '/a', '/a/b']
    """
    out = []
    last_path = None
    while path:
        path = os.path.dirname(path)
        
        if path == last_path:
            break
        last_path = path
    
        if path: # don't yield ''
            out.insert(0, path)
    return out

def _mkdirall(path):
    """Make all the enclosing directories of path (like mkdir -p on the
    parent).
    """
    for ancestor in _ancestry(path):
        if not os.path.isdir(ancestor):
            os.mkdir(ancestor)

def _components(path):
    """Return a list of the path components in path. For instance:
       >>> _components('/a/b/c')
       ['a', 'b', 'c']
    """
    comps = []
    ances = _ancestry(path)
    for anc in ances:
        comp = os.path.basename(anc)
        if comp:
            comps.append(comp)
        else: # root
            comps.append(anc)
    
    last = os.path.basename(path)
    if last:
        comps.append(last)
    
    return comps

def _bytestring_path(path):
    """Given a path, which is either a str or a unicode, returns a str
    path (ensuring that we never deal with Unicode pathnames).
    """
    # Pass through bytestrings.
    if isinstance(path, str):
        return path

    # Try to encode with default encodings, but fall back to UTF8.
    encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
    try:
        return path.encode(encoding)
    except UnicodeError:
        return path.encode('utf8')

# Note: POSIX actually supports \ and : -- I just think they're
# a pain. And ? has caused problems for some.
CHAR_REPLACE = [
    (re.compile(r'[\\/\?]|^\.'), '_'),
    (re.compile(r':'), '-'),
]
CHAR_REPLACE_WINDOWS = re.compile('["\*<>\|]|^\.|\.$'), '_'
def _sanitize_path(path, plat=None):
    """Takes a path and makes sure that it is legal for the specified
    platform (as returned by platform.system()). Returns a new path.
    """
    plat = plat or platform.system()
    comps = _components(path)
    for i, comp in enumerate(comps):
        # Replace special characters.
        for regex, repl in CHAR_REPLACE:
            comp = regex.sub(repl, comp)
        if plat == 'Windows':
            regex, repl = CHAR_REPLACE_WINDOWS
            comp = regex.sub(repl, comp)
        
        # Truncate each component.
        if len(comp) > MAX_FILENAME_LENGTH:
            comp = comp[:MAX_FILENAME_LENGTH]
                
        comps[i] = comp
    return os.path.join(*comps)


# Library items (songs).

class Item(object):
    def __init__(self, values):
        self.dirty = {}
        self._fill_record(values)
        self._clear_dirty()
        
    @classmethod
    def from_path(cls, path):
        """Creates a new item from the media file at the specified path.
        """
        # Initiate with values that aren't read from files.
        i = cls({
            'album_id': None,
        })
        i.read(path)
        return i

    def _fill_record(self, values):
        self.record = {}
        for key in ITEM_KEYS:
            try:
                setattr(self, key, values[key])
            except KeyError:
                setattr(self, key, None)

    def _clear_dirty(self):
        self.dirty = {}
        for key in ITEM_KEYS:
            self.dirty[key] = False

    def __repr__(self):
        return 'Item(' + repr(self.record) + ')'


    # Item field accessors.

    def __getattr__(self, key):
        """If key is an item attribute (i.e., a column in the database),
        returns the record entry for that key.
        """
        if key in ITEM_KEYS:
            return self.record[key]
        else:
            raise AttributeError(key + ' is not a valid item field')

    def __setattr__(self, key, value):
        """If key is an item attribute (i.e., a column in the database),
        sets the record entry for that key to value. Note that to change
        the attribute in the database or in the file's tags, one must
        call store() or write().
        
        Otherwise, performs an ordinary setattr.
        """
        # Encode unicode paths and read buffers.
        if key == 'path':
            if isinstance(value, unicode):
                value = _bytestring_path(value)
            elif isinstance(value, buffer):
                value = str(value)

        if key in ITEM_KEYS:
            if (not (key in self.record)) or (self.record[key] != value):
                # don't dirty if value unchanged
                self.record[key] = value
                self.dirty[key] = True
        else:
            super(Item, self).__setattr__(key, value)
    
    
    # Interaction with file metadata.
    
    def read(self, read_path=None):
        """Read the metadata from the associated file. If read_path is
        specified, read metadata from that file instead.
        """
        if read_path is None:
            read_path = self.path
        f = MediaFile(read_path)

        for key in ITEM_KEYS_META:
            setattr(self, key, getattr(f, key))
        self.path = read_path
    
    def write(self):
        """Writes the item's metadata to the associated file.
        """
        f = MediaFile(self.path)
        for key in ITEM_KEYS_WRITABLE:
            setattr(f, key, getattr(self, key))
        f.save()
    
    
    # Dealing with files themselves.
    
    def move(self, library, copy=False):
        """Move the item to its designated location within the library
        directory (provided by destination()). Subdirectories are
        created as needed. If the operation succeeds, the item's path
        field is updated to reflect the new location.
        
        If copy is True, moving the file is copied rather than moved.
        
        Passes on appropriate exceptions if directories cannot be created
        or moving/copying fails.
        
        Note that one should almost certainly call store() and
        library.save() after this method in order to keep on-disk data
        consistent.
        """
        dest = library.destination(self)
        
        # Create necessary ancestry for the move.
        _mkdirall(dest)
        
        if copy:
            shutil.copy(self.path, dest)
        else:
            shutil.move(self.path, dest)
            
        # Either copying or moving succeeded, so update the stored path.
        self.path = dest


# Library queries.

class Query(object):
    """An abstract class representing a query into the item database.
    """
    def clause(self):
        """Returns (clause, subvals) where clause is a valid sqlite
        WHERE clause implementing the query and subvals is a list of
        items to be substituted for ?s in the clause.
        """
        raise NotImplementedError

    def match(self, item):
        """Check whether this query matches a given Item. Can be used to
        perform queries on arbitrary sets of Items.
        """
        raise NotImplementedError

    def statement(self, columns='*'):
        """Returns (query, subvals) where clause is a sqlite SELECT
        statement to enact this query and subvals is a list of values
        to substitute in for ?s in the query.
        """
        clause, subvals = self.clause()
        return ('SELECT ' + columns + ' FROM items WHERE ' + clause, subvals)

    def count(self, library):
        """Returns `(num, length)` where `num` is the number of items in
        the library matching this query and `length` is their total
        length in seconds.
        """
        clause, subvals = self.clause()
        statement = 'SELECT COUNT(id), SUM(length) FROM items WHERE ' + clause
        c = library.conn.cursor()
        result = c.execute(statement, subvals).fetchone()
        return (result[0], result[1])

    def execute(self, library):
        """Runs the query in the specified library, returning a
        ResultIterator.
        """
        c = library.conn.cursor()
        c.execute(*self.statement())
        return ResultIterator(c, library)

class FieldQuery(Query):
    """An abstract query that searches in a specific field for a
    pattern.
    """
    def __init__(self, field, pattern):
        if field not in ITEM_KEYS:
            raise InvalidFieldError(field + ' is not an item key')
        self.field = field
        self.pattern = pattern
        
class MatchQuery(FieldQuery):
    """A query that looks for exact matches in an item field."""
    def clause(self):
        pattern = self.pattern
        if self.field == 'path' and isinstance(pattern, str):
            pattern = buffer(pattern)
        return self.field + " = ?", [pattern]

    def match(self, item):
        return self.pattern == getattr(item, self.field)

class SubstringQuery(FieldQuery):
    """A query that matches a substring in a specific item field."""
    def clause(self):
        search = '%' + (self.pattern.replace('\\','\\\\').replace('%','\\%')
                            .replace('_','\\_')) + '%'
        clause = self.field + " like ? escape '\\'"
        subvals = [search]
        return clause, subvals

    def match(self, item):
        return self.pattern.lower() in getattr(item, self.field).lower()

class CollectionQuery(Query):
    """An abstract query class that aggregates other queries. Can be
    indexed like a list to access the sub-queries.
    """
    def __init__(self, subqueries = ()):
        self.subqueries = subqueries
    
    # is there a better way to do this?
    def __len__(self): return len(self.subqueries)
    def __getitem__(self, key): return self.subqueries[key]
    def __iter__(self): iter(self.subqueries)
    def __contains__(self, item): item in self.subqueries

    def clause_with_joiner(self, joiner):
        """Returns a clause created by joining together the clauses of
        all subqueries with the string joiner (padded by spaces).
        """
        clause_parts = []
        subvals = []
        for subq in self.subqueries:
            subq_clause, subq_subvals = subq.clause()
            clause_parts.append('(' + subq_clause + ')')
            subvals += subq_subvals
        clause = (' ' + joiner + ' ').join(clause_parts)
        return clause, subvals
    
    @classmethod
    def from_dict(cls, matches):
        """Construct a query from a dictionary, matches, whose keys are
        item field names and whose values are substring patterns.
        """
        subqueries = []
        for key, pattern in matches.iteritems():
            subqueries.append(SubstringQuery(key, pattern))
        return cls(subqueries)
    
    # regular expression for _parse_query, below
    _pq_regex = re.compile(r'(?:^|(?<=\s))' # zero-width match for whitespace
                                            # or beginning of string
       
                           # non-grouping optional segment for the keyword
                           r'(?:'
                                r'(\S+?)'   # the keyword
                                r'(?<!\\):' # unescaped :
                           r')?'
       
                           r'(\S+)',        # the term itself
                           re.I)            # case-insensitive
    @classmethod
    def _parse_query(cls, query_string):
        """Takes a query in the form of a whitespace-separated list of
        search terms that may be preceded with a key followed by a
        colon. Returns a list of pairs (key, term) where key is None if
        the search term has no key.

        For instance,
        parse_query('stapler color:red') ==
            [(None, 'stapler'), ('color', 'red')]

        Colons may be 'escaped' with a backslash to disable the keying
        behavior.
        """
        out = []
        for match in cls._pq_regex.finditer(query_string):
            out.append((match.group(1), match.group(2).replace(r'\:',':')))
        return out

    @classmethod
    def from_string(cls, query_string, default_fields=None):
        """Creates a query from a string in the format used by
        _parse_query. If default_fields are specified, they are the
        fields to be searched by unqualified search terms. Otherwise,
        all fields are searched for those terms.
        """
        subqueries = []
        for key, pattern in cls._parse_query(query_string):
            if key is None: # no key specified; match any field
                subqueries.append(AnySubstringQuery(pattern, default_fields))
            elif key.lower() in ITEM_KEYS: # ignore unrecognized keys
                subqueries.append(SubstringQuery(key.lower(), pattern))
        if not subqueries: # no terms in query
            subqueries = [TrueQuery()]
        return cls(subqueries)

class AnySubstringQuery(CollectionQuery):
    """A query that matches a substring in any of a list of metadata
    fields.
    """
    def __init__(self, pattern, fields=None):
        """Create a query for pattern over the sequence of fields
        given. If no fields are given, all available fields are
        used.
        """
        self.pattern = pattern
        self.fields = fields or ITEM_KEYS_WRITABLE

        subqueries = []
        for field in self.fields:
            subqueries.append(SubstringQuery(field, pattern))
        super(AnySubstringQuery, self).__init__(subqueries)

    def clause(self):
        return self.clause_with_joiner('or')

    def match(self, item):
        for fld in self.fields:
            try:
                val = getattr(item, fld)
            except KeyError:
                continue
            if isinstance(val, basestring) and \
               self.pattern.lower() in val.lower():
                return True
        return False

class MutableCollectionQuery(CollectionQuery):
    """A collection query whose subqueries may be modified after the
    query is initialized.
    """
    def __setitem__(self, key, value): self.subqueries[key] = value
    def __delitem__(self, key): del self.subqueries[key]

class AndQuery(MutableCollectionQuery):
    """A conjunction of a list of other queries."""
    def clause(self):
        return self.clause_with_joiner('and')

    def match(self, item):
        return all([q.match(item) for q in self.subqueries])

class TrueQuery(Query):
    """A query that always matches."""
    def clause(self):
        return '1', ()

    def match(self, item):
        return True

class ResultIterator(object):
    """An iterator into an item query result set."""
    
    def __init__(self, cursor, library):
        self.cursor = cursor
        self.library = library
    
    def __iter__(self): return self
    
    def next(self):
        try:
            row = self.cursor.next()
        except StopIteration:
            self.cursor.close()
            raise
        return Item(row)


# An abstract library.

class BaseLibrary(object):
    """Abstract base class for music libraries, which are loosely
    defined as sets of Items.
    """
    def __init__(self):
        raise NotImplementedError


    # Helpers.

    @classmethod
    def _get_query(cls, val=None, default_fields=None):
        """Takes a value which may be None, a query string, or a Query
        object, and returns a suitable Query object. If default_fields
        is specified, then it restricts the list of fields to search
        for unqualified terms in query strings.
        """
        if val is None:
            return TrueQuery()
        elif isinstance(val, basestring):
            return AndQuery.from_string(val, default_fields)
        elif isinstance(val, Query):
            return val
        elif not isinstance(val, Query):
            raise ValueError('query must be None or have type Query or str')


    # Basic operations.

    def add(self, item, copy=False): #FIXME copy should default to true
        """Add the item as a new object to the library database. The id
        field will be updated; the new id is returned. If copy, then
        each item is copied to the destination location before it is
        added.
        """
        raise NotImplementedError

    def get(self, query=None, default_fields=None):
        """Returns a sequence of the items matching query, which may
        be None (match the entire library), a Query object, or a query
        string. If default_fields is specified, it restricts the fields
        that may be matched by unqualified query string terms.
        """
        raise NotImplementedError

    def save(self):
        """Ensure that the library is consistent on disk. A no-op by
        default.
        """
        pass

    def load(self, item, load_id=None):
        """Refresh the item's metadata from the library database. If
        fetch_id is not specified, use the item's current id.
        """
        raise NotImplementedError

    def store(self, item, store_id=None, store_all=False):
        """Save the item's metadata into the library database. If
        store_id is specified, use it instead of the item's current id.
        If store_all is true, save the entire record instead of just
        the dirty fields.
        """
        raise NotImplementedError

    def remove(self, item):
        """Removes the item from the database (leaving the file on
        disk).
        """
        raise NotImplementedError


    # Browsing operations.
    # Naive implementations are provided, but these methods should be
    # overridden if a better implementation exists.

    def artists(self, query=None):
        """Returns a sorted sequence of artists in the database,
        possibly filtered by a query. Unqualified query string terms
        only match the artist field.
        """
        out = set()
        for item in self.get(query, ARTIST_DEFAULT_FIELDS):
            out.add(item.artist)
        return sorted(out)

    def albums(self, artist=None, query=None):
        """Returns a sorted list of BaseAlbum objects, possibly filtered
        by an artist name or an arbitrary query. Unqualified query
        string terms only match fields that apply at an album
        granularity: artist, album, and genre.
        """
        # Gather the unique album/artist names and associated example
        # Items.
        specimens = set()
        for item in self.get(query, ALBUM_DEFAULT_FIELDS):
            if (artist is None or item.artist == artist):
                key = (item.artist, item.album)
                if key not in specimens:
                    specimens[key] = item

        # Build album objects.
        for k in sorted(specimens.keys()):
            item = specimens[k]
            record = {}
            for key in ALBUM_KEYS_ITEM:
                record[key] = getattr(item, key)
            yield BaseAlbum(self, record)

    def items(self, artist=None, album=None, title=None, query=None):
        """Returns a sequence of the items matching the given artist,
        album, title, and query (if present). Sorts in such a way as to
        group albums appropriately. Unqualified query string terms only
        match intuitively relevant fields: artist, album, genre, title,
        and comments.
        """
        out = []
        for item in self.get(query, ITEM_DEFAULT_FIELDS):
            if (artist is None or item.artist == artist) and \
               (album is None  or item.album == album) and \
               (title is None  or item.title == title):
                out.append(item)

        # Sort by: artist, album, disc, track.
        def compare(a, b):
            return cmp(a.artist, b.artist) or \
                   cmp(a.album, b.album) or \
                   cmp(a.disc, b.disc) or \
                   cmp(a.track, b.track)
        return sorted(out, compare)

class BaseAlbum(object):
    """Represents an album in the library, which in turn consists of a
    collection of items in the library.

    This base version just reflects the metadata of the album's items
    and therefore isn't particularly useful. The items are referenced
    by the record's album and artist fields. Implementations can add
    album-level metadata or use distinct backing stores.
    """
    def __init__(self, library, record):
        self._library = library
        self._record = record

    def __getattr__(self, key):
        """Get the value for an album attribute."""
        if key in self._record:
            return self._record[key]
        else:
            raise AttributeError('no such field %s' % key)

    def __setattr__(self, key, value):
        """Set the value of an album attribute, modifying each of the
        album's items.
        """
        if key in self._record:
            # Reflect change in this object.
            self._record[key] = value
            # Modify items.
            if key in ALBUM_KEYS_ITEM:
                items = self._library.items(artist=self.artist,
                                            album=self.album)
                for item in items:
                    setattr(item, key, value)
                self._library.store(item)
        else:
            object.__setattr__(self, key, value)

    def load(self):
        """Refresh this album's cached metadata from the library.
        """
        items = self._library.items(artist=self.artist, album=self.album)
        item = iter(items).next()
        for key in ALBUM_KEYS_ITEM:
            self._record[key] = getattr(item, key)


# Concrete DB-backed library.

class Library(BaseLibrary):
    """A music library using an SQLite database as a metadata store."""
    def __init__(self, path='library.blb',
                       directory='~/Music',
                       path_format='$artist/$album/$track $title',
                       art_filename='cover',
                       item_fields=ITEM_FIELDS,
                       album_fields=ALBUM_FIELDS):
        self.path = _bytestring_path(path)
        self.directory = _bytestring_path(directory)
        self.path_format = path_format
        self.art_filename = _bytestring_path(art_filename)
        
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
            # this way we can access our SELECT results like dictionaries
        
        self._make_table('items', item_fields)
        self._make_table('albums', album_fields)
    
    def _make_table(self, table, fields):
        """Set up the schema of the library file. fields is a list of
        all the fields that should be present in the indicated table.
        Columns are added if necessary.
        """
        # Get current schema.
        cur = self.conn.cursor()
        cur.execute('PRAGMA table_info(%s)' % table)
        current_fields = set([row[1] for row in cur])
        
        field_names = set([f[0] for f in fields])
        if current_fields.issuperset(field_names):
            # Table exists and has all the required columns.
            return
            
        if not current_fields:
            # No table exists.        
            setup_sql =  'CREATE TABLE %s (' % table
            setup_sql += ', '.join(['%s %s' % f[:2] for f in fields])
            setup_sql += ');'
            
        else:
            # Table exists but is missing fields.
            setup_sql = ''
            for fname in field_names - current_fields:
                for field in fields:
                    if field[0] == fname:
                        break
                else:
                    assert False
                setup_sql += 'ALTER TABLE %s ' % table
                setup_sql += 'ADD COLUMN %s %s;\n' % field[:2]
        
        self.conn.executescript(setup_sql)
        self.conn.commit()

    def destination(self, item):
        """Returns the path in the library directory designated for item
        item (i.e., where the file ought to be).
        """
        subpath_tmpl = Template(self.path_format)

        # Get the item's Album if it has one.
        album = self.get_album(item)
        
        # Build the mapping for substitution in the path template,
        # beginning with the values from the database.
        mapping = {}
        for key in ITEM_KEYS_META:
            # Get the values from either the item or its album.
            if key in ALBUM_KEYS_ITEM and album is not None:
                # From album.
                value = getattr(album, key)
            else:
                # From Item.
                value = getattr(item, key)

            # Sanitize the value for inclusion in a path:
            # replace / and leading . with _
            if isinstance(value, basestring):
                value = value.replace(os.sep, '_')
            elif key in ('track', 'tracktotal', 'disc', 'disctotal'):
                # pad with zeros
                value = '%02i' % value
            else:
                value = str(value)
            mapping[key] = value
        
        # Perform substitution.
        subpath = subpath_tmpl.substitute(mapping)
        
        # Encode for the filesystem, dropping unencodable characters.
        if isinstance(subpath, unicode):
            encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
            subpath = subpath.encode(encoding, 'replace')
        
        # Truncate components and remove forbidden characters.
        subpath = _sanitize_path(subpath)
        
        # Preserve extension.
        _, extension = os.path.splitext(item.path)
        subpath += extension
        
        return _normpath(os.path.join(self.directory, subpath))   

    
    # Main interface.

    def add(self, item, copy=False):
        #FIXME make a deep copy of the item?
        item.library = self
        if copy:
            item.move(self, copy=True)

        # build essential parts of query
        columns = ','.join([key for key in ITEM_KEYS if key != 'id'])
        values = ','.join( ['?'] * (len(ITEM_KEYS)-1) )
        subvars = []
        for key in ITEM_KEYS:
            if key != 'id':
                value = getattr(item, key)
                if key == 'path' and isinstance(value, str):
                    value = buffer(value)
                subvars.append(value)
        
        # issue query
        c = self.conn.cursor()
        query = 'INSERT INTO items (' + columns + ') VALUES (' + values + ')'
        c.execute(query, subvars)
        new_id = c.lastrowid
        c.close()
        
        item._clear_dirty()
        item.id = new_id
        return new_id
    
    def get(self, query=None):
        return self._get_query(query).execute(self)
    
    def save(self):
        """Writes the library to disk (completing an sqlite
        transaction).
        """
        self.conn.commit()
        plugins.send('save', lib=self)

    def load(self, item, load_id=None):
        if load_id is None:
            load_id = item.id
        
        c = self.conn.execute(
                'SELECT * FROM items WHERE id=?', (load_id,) )
        item._fill_record(c.fetchone())
        item._clear_dirty()
        c.close()

    def store(self, item, store_id=None, store_all=False):
        if store_id is None:
            store_id = item.id
 
        # build assignments for query
        assignments = ''
        subvars = []
        for key in ITEM_KEYS:
            if (key != 'id') and (item.dirty[key] or store_all):
                assignments += key + '=?,'
                value = getattr(item, key)
                # Wrap path strings in buffers so they get stored
                # "in the raw".
                if key == 'path' and isinstance(value, str):
                    value = buffer(value)
                subvars.append(value)
        
        if not assignments:
            # nothing to store (i.e., nothing was dirty)
            return
        
        assignments = assignments[:-1] # knock off last ,

        # finish the query
        query = 'UPDATE items SET ' + assignments + ' WHERE id=?'
        subvars.append(store_id)

        self.conn.execute(query, subvars)
        item._clear_dirty()

    def remove(self, item, delete=False):
        self.conn.execute('DELETE FROM items WHERE id=?', (item.id,))
        if delete:
            os.unlink(item.path)


    # Browsing.

    def artists(self, query=None):
        query = self._get_query(query, ARTIST_DEFAULT_FIELDS)
        where, subvals = query.clause()
        sql = "SELECT DISTINCT artist FROM items " + \
              "WHERE " + where + \
              " ORDER BY artist"
        c = self.conn.execute(sql, subvals)
        return [res[0] for res in c.fetchall()]

    def albums(self, artist=None, query=None):
        query = self._get_query(query, ALBUM_DEFAULT_FIELDS)
        if artist is not None:
            # "Add" the artist to the query.
            query = AndQuery((query, MatchQuery('artist', artist)))
        where, subvals = query.clause()
        sql = "SELECT * FROM albums " + \
              "WHERE " + where + \
              " ORDER BY artist, album"
        c = self.conn.execute(sql, subvals)
        return [Album(self, dict(res)) for res in c.fetchall()]

    def items(self, artist=None, album=None, title=None, query=None):
        queries = [self._get_query(query, ITEM_DEFAULT_FIELDS)]
        if artist is not None:
            queries.append(MatchQuery('artist', artist))
        if album is not None:
            queries.append(MatchQuery('album', album))
        if title is not None:
            queries.append(MatchQuery('title', title))
        super_query = AndQuery(queries)
        where, subvals = super_query.clause()

        sql = "SELECT * FROM items " + \
              "WHERE " + where + \
              " ORDER BY artist, album, disc, track"
        c = self.conn.execute(sql, subvals)
        return ResultIterator(c, self)


    # Convenience accessors.

    def get_item(self, id):
        """Fetch an Item by its ID. Returns None if no match is found.
        """
        c = self.conn.execute("SELECT * FROM items WHERE id=?", (id,))
        it = ResultIterator(c, self)
        try:
            return it.next()
        except StopIteration:
            return None
    
    def get_album(self, item_or_id):
        """Given an album ID or an item associated with an album,
        return an Album object for the album. If no such album exists,
        returns None.
        """
        if isinstance(item_or_id, int):
            album_id = item_or_id
        else:
            album_id = item_or_id.album_id
        if album_id is None:
            return None

        record = self.conn.execute(
            'SELECT * FROM albums WHERE id=?',
            (album_id,)
        ).fetchone()
        if record:
            return Album(self, dict(record))

    def add_album(self, items):
        """Create a new album in the database with metadata derived
        from its items. The items are added to the database if they
        don't yet have an ID. Returns an Album object.
        """
        # Set the metadata from the first item.
        #fixme: check for consensus?
        sql = 'INSERT INTO albums (%s) VALUES (%s)' % \
              (', '.join(ALBUM_KEYS_ITEM),
               ', '.join(['?'] * len(ALBUM_KEYS_ITEM)))
        subvals = [getattr(items[0], key) for key in ALBUM_KEYS_ITEM]
        c = self.conn.execute(sql, subvals)
        album_id = c.lastrowid

        # Construct the new Album object.
        record = {}
        for key in ALBUM_KEYS:
            if key in ALBUM_KEYS_ITEM:
                record[key] = getattr(items[0], key)
            else:
                # Non-item fields default to None.
                record[key] = None
        record['id'] = album_id
        album = Album(self, record)

        # Add the items to the library.
        for item in items:
            item.album_id = album_id
            if item.id is None:
                self.add(item)
            else:
                self.store(item)

        return album

class Album(BaseAlbum):
    """Provides access to information about albums stored in a
    library. Reflects the library's "albums" table, including album
    art.
    """
    def __init__(self, lib, record):
        # Decode Unicode paths in database.
        if 'artpath' in record and isinstance(record['artpath'], unicode):
            record['artpath'] = _bytestring_path(record['artpath'])
        super(Album, self).__init__(lib, record)

    def __setattr__(self, key, value):
        """Set the value of an album attribute."""
        if key == 'id':
            raise AttributeError("can't modify album id")

        elif key in ALBUM_KEYS:
            # Make sure paths are bytestrings.
            if key == 'artpath' and isinstance(value, unicode):
                value = _bytestring_path(value)

            # Reflect change in this object.
            self._record[key] = value

            # Store art path as a buffer.
            if key == 'artpath' and isinstance(value, str):
                value = buffer(value)

            # Change album table.
            sql = 'UPDATE albums SET %s=? WHERE id=?' % key
            self._library.conn.execute(sql, (value, self.id))

            # Possibly make modification on items as well.
            if key in ALBUM_KEYS_ITEM:
                for item in self.items():
                    setattr(item, key, value)
                    self._library.store(item)

        else:
            object.__setattr__(self, key, value)

    def __getattr__(self, key):
        value = super(Album, self).__getattr__(key)

        # Unwrap art path from buffer object.
        if key == 'artpath' and isinstance(value, buffer):
            value = str(value)

        return value

    def items(self):
        """Returns an iterable over the items associated with this
        album.
        """
        c = self._library.conn.execute(
            'SELECT * FROM items WHERE album_id=?',
            (self.id,)
        )
        return ResultIterator(c, self._library)

    def remove(self, delete=False):
        """Removes this album and all its associated items from the
        library. If delete, then the items' files are also deleted
        from disk, along with any album art.
        """
        # Remove items.
        for item in self.items():
            self._library.remove(item, delete)
        
        # Delete art.
        if delete:
            artpath = self.artpath
            if artpath:
                os.unlink(artpath)
        
        # Remove album.
        self._library.conn.execute(
            'DELETE FROM albums WHERE id=?',
            (self.id,)
        )

    def move(self, copy=False):
        """Moves (or copies) all items to their destination. Any
        album art moves along with them.
        """
        # Move items.
        items = list(self.items())
        for item in items:
            item.move(self._library, copy)
        newdir = os.path.dirname(items[0].path)

        # Move art.
        old_art = self.artpath
        if old_art:
            new_art = self.art_destination(old_art, newdir)
            if new_art != old_art:
                if copy:
                    shutil.copy(old_art, new_art)
                else:
                    shutil.move(old_art, new_art)
                self.artpath = new_art

        # Store new item paths. We do this at the end to avoid
        # locking the database for too long while files are copied.
        for item in items:
            self._library.store(item)

    def art_destination(self, image, item_dir=None):
        """Returns a path to the destination for the album art image
        for the album. `image` is the path of the image that will be
        moved there (used for its extension).

        The path construction uses the existing path of the album's
        items, so the album must contain at least one item or
        item_dir must be provided.
        """
        image = _bytestring_path(image)
        if item_dir is None:
            item = self.items().next()
            item_dir = os.path.dirname(item.path)
        _, ext = os.path.splitext(image)
        dest = os.path.join(item_dir, self._library.art_filename + ext)
        return dest
    
    def set_art(self, path):
        """Sets the album's cover art to the image at the given path.
        The image is copied into place, replacing any existing art.
        """
        path = _bytestring_path(path)
        oldart = self.artpath
        artdest = self.art_destination(path)
        if oldart == artdest:
            os.unlink(oldart)

        shutil.copy(path, artdest)
        self.artpath = artdest
