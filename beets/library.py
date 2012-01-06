# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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
import sys
import logging
import shlex
from unidecode import unidecode
from beets.mediafile import MediaFile
from beets import plugins
from beets import util
from beets.util import bytestring_path, syspath, normpath, samefile
from beets.util.functemplate import Template

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

    ('title',            'text', True, True),
    ('artist',           'text', True, True),
    ('album',            'text', True, True),
    ('albumartist',      'text', True, True),
    ('genre',            'text', True, True),
    ('composer',         'text', True, True),
    ('grouping',         'text', True, True),
    ('year',             'int',  True, True),
    ('month',            'int',  True, True),
    ('day',              'int',  True, True),
    ('track',            'int',  True, True),
    ('tracktotal',       'int',  True, True),
    ('disc',             'int',  True, True),
    ('disctotal',        'int',  True, True),
    ('lyrics',           'text', True, True),
    ('comments',         'text', True, True),
    ('bpm',              'int',  True, True),
    ('comp',             'bool', True, True),
    ('mb_trackid',       'text', True, True),
    ('mb_albumid',       'text', True, True),
    ('mb_artistid',      'text', True, True),
    ('mb_albumartistid', 'text', True, True),
    ('albumtype',        'text', True, True),
    ('label',            'text', True, True),

    ('length',      'real', False, True),
    ('bitrate',     'int',  False, True),
    ('format',      'text', False, True),
    ('mtime',       'int',  False, False),
]
ITEM_KEYS_WRITABLE = [f[0] for f in ITEM_FIELDS if f[3] and f[2]]
ITEM_KEYS_META     = [f[0] for f in ITEM_FIELDS if f[3]]
ITEM_KEYS          = [f[0] for f in ITEM_FIELDS]

# Database fields for the "albums" table.
# The third entry in each tuple indicates whether the field reflects an
# identically-named field in the items table.
ALBUM_FIELDS = [
    ('id',      'integer primary key', False),
    ('artpath', 'blob',                False),

    ('albumartist',      'text', True),
    ('album',            'text', True),
    ('genre',            'text', True),
    ('year',             'int',  True),
    ('month',            'int',  True),
    ('day',              'int',  True),
    ('tracktotal',       'int',  True),
    ('disctotal',        'int',  True),
    ('comp',             'bool', True),
    ('mb_albumid',       'text', True),
    ('mb_albumartistid', 'text', True),
    ('albumtype',        'text', True),
    ('label',            'text', True),
]
ALBUM_KEYS = [f[0] for f in ALBUM_FIELDS]
ALBUM_KEYS_ITEM = [f[0] for f in ALBUM_FIELDS if f[2]]

# Default search fields for various granularities.
ARTIST_DEFAULT_FIELDS = ('artist',)
ALBUM_DEFAULT_FIELDS = ('album', 'albumartist', 'genre')
ITEM_DEFAULT_FIELDS = ARTIST_DEFAULT_FIELDS + ALBUM_DEFAULT_FIELDS + \
    ('title', 'comments')

# Special path format key.
PF_KEY_DEFAULT = 'default'

# Logger.
log = logging.getLogger('beets')
if not log.handlers:
    log.addHandler(logging.StreamHandler())


# Exceptions.

class InvalidFieldError(Exception):
    pass


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
        i.mtime = i.current_mtime() # Initial mtime.
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
                value = bytestring_path(value)
            elif isinstance(value, buffer):
                value = str(value)

        if key in ITEM_KEYS:
            # If the value changed, mark the field as dirty.
            if (not (key in self.record)) or (self.record[key] != value):
                self.record[key] = value
                self.dirty[key] = True
                if key in ITEM_KEYS_WRITABLE:
                    self.mtime = 0 # Reset mtime on dirty.
        else:
            super(Item, self).__setattr__(key, value)
    
    
    # Interaction with file metadata.
    
    def read(self, read_path=None):
        """Read the metadata from the associated file. If read_path is
        specified, read metadata from that file instead.
        """
        if read_path is None:
            read_path = self.path
        else:
            read_path = normpath(read_path)
        f = MediaFile(syspath(read_path))

        for key in ITEM_KEYS_META:
            setattr(self, key, getattr(f, key))
        self.path = read_path

        # Database's mtime should now reflect the on-disk value.
        if read_path == self.path:
            self.mtime = self.current_mtime()
    
    def write(self):
        """Writes the item's metadata to the associated file.
        """
        f = MediaFile(syspath(self.path))
        plugins.send('write', item=self, mf=f)
        for key in ITEM_KEYS_WRITABLE:
            setattr(f, key, getattr(self, key))
        f.save()

        # The file has a new mtime.
        self.mtime = self.current_mtime()


    # Files themselves.

    def move(self, dest, copy=False):
        """Moves or copies the item's file, updating the path value if
        the move succeeds. If a file exists at ``dest``, then it is
        slightly modified to be unique.
        """
        if not util.samefile(self.path, dest):
            dest = util.unique_path(dest)
        if copy:
            util.copy(self.path, dest)
        else:
            util.move(self.path, dest)
            
        # Either copying or moving succeeded, so update the stored path.
        self.path = dest

    def current_mtime(self):
        """Returns the current mtime of the file, rounded to the nearest
        integer.
        """
        return int(os.path.getmtime(syspath(self.path)))


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
        c = library.conn.execute(statement, subvals)
        result = c.fetchone()
        c.close()
        return (result[0], result[1] or 0.0)

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
        value = getattr(item, self.field) or ''
        return self.pattern.lower() in value.lower()

class BooleanQuery(MatchQuery):
    """Matches a boolean field. Pattern should either be a boolean or a
    string reflecting a boolean.
    """
    def __init__(self, field, pattern):
        super(BooleanQuery, self).__init__(field, pattern)
        if isinstance(pattern, basestring):
            self.pattern = util.str2bool(pattern)
        self.pattern = int(self.pattern)

class SingletonQuery(Query):
    """Matches either singleton or non-singleton items."""
    def __init__(self, sense):
        self.sense = sense

    def clause(self):
        if self.sense:
            return "album_id ISNULL", ()
        else:
            return "NOT album_id ISNULL", ()

    def match(self, item):
        return (not item.album_id) == self.sense

class CollectionQuery(Query):
    """An abstract query class that aggregates other queries. Can be
    indexed like a list to access the sub-queries.
    """
    def __init__(self, subqueries = ()):
        self.subqueries = subqueries
    
    # is there a better way to do this?
    def __len__(self): return len(self.subqueries)
    def __getitem__(self, key): return self.subqueries[key]
    def __iter__(self): return iter(self.subqueries)
    def __contains__(self, item): return item in self.subqueries

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
    
    # regular expression for _parse_query_part, below
    _pq_regex = re.compile(# non-grouping optional segment for the keyword
                           r'(?:'
                                r'(\S+?)'   # the keyword
                                r'(?<!\\):' # unescaped :
                           r')?'
                           r'(.+)',        # the term itself
                           re.I)            # case-insensitive
    @classmethod
    def _parse_query_part(cls, part):
        """Takes a query in the form of a key/value pair separated by a
        colon. Returns pair (key, term) where key is None if the search
        term has no key.

        For instance,
        parse_query('stapler') == (None, 'stapler')
        parse_query('color:red') == ('color', 'red')

        Colons may be 'escaped' with a backslash to disable the keying
        behavior.
        """
        part = part.strip()
        match = cls._pq_regex.match(part)
        if match:
            return match.group(1), match.group(2).replace(r'\:', ':')

    @classmethod
    def from_strings(cls, query_parts, default_fields=None, all_keys=ITEM_KEYS):
        """Creates a query from a list of strings in the format used by
        _parse_query_part. If default_fields are specified, they are the
        fields to be searched by unqualified search terms. Otherwise,
        all fields are searched for those terms.
        """
        subqueries = []
        for part in query_parts:
            res = cls._parse_query_part(part)
            if not res:
                continue
            key, pattern = res
            if key is None: # No key specified.
                if os.sep in pattern and 'path' in all_keys:
                    # This looks like a path.
                    subqueries.append(PathQuery(pattern))
                else:
                    # Match any field.
                    subqueries.append(AnySubstringQuery(pattern,
                                                        default_fields))
            elif key.lower() == 'comp': # a boolean field
                subqueries.append(BooleanQuery(key.lower(), pattern))
            elif key.lower() == 'path' and 'path' in all_keys:
                subqueries.append(PathQuery(pattern))
            elif key.lower() in all_keys: # ignore unrecognized keys
                subqueries.append(SubstringQuery(key.lower(), pattern))
            elif key.lower() == 'singleton':
                subqueries.append(SingletonQuery(util.str2bool(pattern)))
        if not subqueries: # no terms in query
            subqueries = [TrueQuery()]
        return cls(subqueries)

    @classmethod
    def from_string(cls, query, default_fields=None, all_keys=ITEM_KEYS):
        """Creates a query based on a single string. The string is split
        into query parts using shell-style syntax.
        """
        return cls.from_strings(shlex.split(query))

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

class FalseQuery(Query):
    """A query that never matches."""
    def clause(self):
        return '0', ()

    def match(self, item):
        return False

class PathQuery(Query):
    """A query that matches all items under a given path."""
    def __init__(self, path):
        # Match the path as a single file.
        self.file_path = normpath(path)
        # As a directory (prefix).
        self.dir_path = os.path.join(self.file_path, '') 

    def match(self, item):
        return (item.path == self.file_path) or \
               item.path.startswith(self.dir_path)

    def clause(self):
        dir_pat = self.dir_path + '%'
        file_blob = buffer(bytestring_path(self.file_path))
        return '(path = ?) || (path LIKE ?)', (file_blob, dir_pat)

class ResultIterator(object):
    """An iterator into an item query result set. The iterator eagerly
    fetches all of the results from the cursor but lazily constructs
    Item objects that reflect them.
    """
    def __init__(self, cursor):
        # Fetch all of the rows, closing the cursor (and unlocking the
        # database).
        self.rows = cursor.fetchall()
        self.rowiter = iter(self.rows)
    
    def __iter__(self):
        return self
    
    def next(self):
        row = self.rowiter.next() # May raise StopIteration.
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
    def _get_query(cls, val=None, album=False):
        """Takes a value which may be None, a query string, a query
        string list, or a Query object, and returns a suitable Query
        object. album determines whether the query is to match items
        or albums.
        """
        if album:
            default_fields = ALBUM_DEFAULT_FIELDS
            all_keys = ALBUM_KEYS
        else:
            default_fields = ITEM_DEFAULT_FIELDS
            all_keys = ITEM_KEYS

        # Convert a single string into a list of space-separated
        # criteria.
        if isinstance(val, basestring):
            val = val.split()

        if val is None:
            return TrueQuery()
        elif isinstance(val, list) or isinstance(val, tuple):
            return AndQuery.from_strings(val, default_fields, all_keys)
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

    def _get(self, query=None, default_fields=None):
        """Returns a sequence of the items matching query, which may
        be None (match the entire library), a Query object, or a query
        string. If default_fields is specified, it restricts the fields
        that may be matched by unqualified query string terms.
        """
        raise NotImplementedError

    def albums(self, artist=None, query=None):
        """Returns a sorted list of BaseAlbum objects, possibly filtered
        by an artist name or an arbitrary query. Unqualified query
        string terms only match fields that apply at an album
        granularity: artist, album, and genre.
        """
        # Gather the unique album/artist names and associated example
        # Items.
        specimens = {}
        for item in self._get(query, ALBUM_DEFAULT_FIELDS):
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
        for item in self._get(query, ITEM_DEFAULT_FIELDS):
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
        super(BaseAlbum, self).__setattr__('_library', library)
        super(BaseAlbum, self).__setattr__('_record', record)

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
                items = self._library.items(albumartist=self.albumartist,
                                            album=self.album)
                for item in items:
                    setattr(item, key, value)
                self._library.store(item)
        else:
            super(BaseAlbum, self).__setattr__(key, value)

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
                       path_formats=((PF_KEY_DEFAULT,
                                      '$artist/$album/$track $title'),),
                       art_filename='cover',
                       timeout=5.0,
                       replacements=None,
                       item_fields=ITEM_FIELDS,
                       album_fields=ALBUM_FIELDS):
        if path == ':memory:':
            self.path = path
        else:
            self.path = bytestring_path(normpath(path))
        self.directory = bytestring_path(normpath(directory))
        self.path_formats = path_formats
        self.art_filename = bytestring_path(art_filename)
        self.replacements = replacements
        
        self.timeout = timeout
        self.conn = sqlite3.connect(self.path, timeout)
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
            setup_sql += ');\n'
            
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

        # Special case. If we're moving from a version without
        # albumartist, copy all the "artist" values to "albumartist"
        # values on the album data structure.
        if table == 'albums' and 'artist' in current_fields and \
                    'albumartist' not in current_fields:
            setup_sql += "UPDATE ALBUMS SET albumartist=artist;\n"
        
        self.conn.executescript(setup_sql)
        self.conn.commit()
    
    def destination(self, item, pathmod=None, in_album=False,
                    fragment=False, basedir=None):
        """Returns the path in the library directory designated for item
        item (i.e., where the file ought to be). in_album forces the
        item to be treated as part of an album. fragment makes this
        method return just the path fragment underneath the root library
        directory; the path is also returned as Unicode instead of
        encoded as a bytestring. basedir can override the library's base
        directory for the destination.
        """
        pathmod = pathmod or os.path
        
        # Use a path format based on a query, falling back on the
        # default.
        for query, path_format in self.path_formats:
            if query == PF_KEY_DEFAULT:
                continue
            query = AndQuery.from_string(query)
            if in_album:
                # If we're treating this item as a member of the item,
                # hack the query so that singleton queries always
                # observe the item to be non-singleton.
                for i, subquery in enumerate(query):
                    if isinstance(subquery, SingletonQuery):
                        query[i] = FalseQuery() if subquery.sense \
                                   else TrueQuery()
            if query.match(item):
                # The query matches the item! Use the corresponding path
                # format.
                break
        else:
            # No query matched; fall back to default.
            for query, path_format in self.path_formats:
                if query == PF_KEY_DEFAULT:
                    break
            else:
                assert False, "no default path format"
        subpath_tmpl = Template(path_format)
        
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
            mapping[key] = util.sanitize_for_path(value, pathmod, key)
        
        # Use the album artist if the track artist is not set and
        # vice-versa.
        if not mapping['artist']:
            mapping['artist'] = mapping['albumartist']
        if not mapping['albumartist']:
            mapping['albumartist'] = mapping['artist']
        
        # Perform substitution.
        mapping.update(plugins.template_values(item))
        funcs = dict(TEMPLATE_FUNCTIONS)
        funcs.update(plugins.template_funcs())
        subpath = subpath_tmpl.substitute(mapping, funcs)
        
        # Encode for the filesystem, dropping unencodable characters.
        if isinstance(subpath, unicode) and not fragment:
            encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()
            subpath = subpath.encode(encoding, 'replace')
        
        # Truncate components and remove forbidden characters.
        subpath = util.sanitize_path(subpath, pathmod, self.replacements)
        
        # Preserve extension.
        _, extension = pathmod.splitext(item.path)
        subpath += extension
        
        if fragment:
            return subpath
        else:
            basedir = basedir or self.directory
            return normpath(os.path.join(basedir, subpath))   


    # Item manipulation.

    def add(self, item, copy=False):
        #FIXME make a deep copy of the item?
        item.library = self
        if copy:
            self.move(item, copy=True)

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
    
    def save(self, event=True):
        """Writes the library to disk (completing an sqlite
        transaction).
        """
        self.conn.commit()
        if event:
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

    def remove(self, item, delete=False, with_album=True):
        """Removes this item. If delete, then the associated file is
        removed from disk. If with_album, then the item's album (if any)
        is removed if it the item was the last in the album.
        """
        album = self.get_album(item) if with_album else None

        self.conn.execute('DELETE FROM items WHERE id=?', (item.id,))

        if album:
            item_iter = album.items()
            try:
                item_iter.next()
            except StopIteration:
                # Album is empty.
                album.remove(delete, False)

        if delete:
            util.soft_remove(item.path)
            util.prune_dirs(os.path.dirname(item.path), self.directory)
    
    def move(self, item, copy=False, in_album=False, basedir=None,
             with_album=True):
        """Move the item to its designated location within the library
        directory (provided by destination()). Subdirectories are
        created as needed. If the operation succeeds, the item's path
        field is updated to reflect the new location.
        
        If copy is True, moving the file is copied rather than moved.
        
        If in_album is True, then the track is treated as part of an
        album even if it does not yet have an album_id associated with
        it. (This allows items to be moved before they are added to the
        database, a performance optimization.)

        basedir overrides the library base directory for the
        destination.

        If the item is in an album, the album is given an opportunity to
        move its art. (This can be disabled by passing
        with_album=False.)
        
        The item is stored to the database if it is in the database, so
        any dirty fields prior to the move() call will be written as a
        side effect. You probably want to call save() to commit the DB
        transaction.
        """
        dest = self.destination(item, in_album=in_album, basedir=basedir)
        
        # Create necessary ancestry for the move.
        util.mkdirall(dest)
        
        # Perform the move and store the change.
        old_path = item.path
        item.move(dest, copy)
        if item.id is not None:
            self.store(item)

        # If this item is in an album, move its art.
        if with_album:
            album = self.get_album(item)
            if album:
                album.move_art(copy)

        # Prune vacated directory.
        if not copy:
            util.prune_dirs(os.path.dirname(old_path), self.directory)


    # Querying.

    def albums(self, query=None, artist=None):
        query = self._get_query(query, True)
        if artist is not None:
            # "Add" the artist to the query.
            query = AndQuery((query, MatchQuery('albumartist', artist)))
        where, subvals = query.clause()
        sql = "SELECT * FROM albums " + \
              "WHERE " + where + \
              " ORDER BY albumartist, album"
        c = self.conn.execute(sql, subvals)
        return [Album(self, dict(res)) for res in c.fetchall()]

    def items(self, query=None, artist=None, album=None, title=None):
        queries = [self._get_query(query, False)]
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
        log.debug('Getting items with SQL: %s' % sql)
        c = self.conn.execute(sql, subvals)
        return ResultIterator(c)


    # Convenience accessors.

    def get_item(self, id):
        """Fetch an Item by its ID. Returns None if no match is found.
        """
        c = self.conn.execute("SELECT * FROM items WHERE id=?", (id,))
        it = ResultIterator(c)
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

        c = self.conn.execute(
            'SELECT * FROM albums WHERE id=?',
            (album_id,)
        )
        try:
            record = c.fetchone()
        finally:
            c.close()
        if record:
            return Album(self, dict(record))

    def add_album(self, items):
        """Create a new album in the database with metadata derived
        from its items. The items are added to the database if they
        don't yet have an ID. Returns an Album object.
        """
        # Set the metadata from the first item.
        #fixme: check for consensus?
        item_values = dict(
            (key, getattr(items[0], key)) for key in ALBUM_KEYS_ITEM)

        sql = 'INSERT INTO albums (%s) VALUES (%s)' % \
              (', '.join(ALBUM_KEYS_ITEM),
               ', '.join(['?'] * len(ALBUM_KEYS_ITEM)))
        subvals = [item_values[key] for key in ALBUM_KEYS_ITEM]
        c = self.conn.execute(sql, subvals)
        album_id = c.lastrowid

        # Construct the new Album object.
        record = {}
        for key in ALBUM_KEYS:
            if key in ALBUM_KEYS_ITEM:
                record[key] = item_values[key]
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
            record['artpath'] = bytestring_path(record['artpath'])
        super(Album, self).__init__(lib, record)

    def __setattr__(self, key, value):
        """Set the value of an album attribute."""
        if key == 'id':
            raise AttributeError("can't modify album id")

        elif key in ALBUM_KEYS:
            # Make sure paths are bytestrings.
            if key == 'artpath' and isinstance(value, unicode):
                value = bytestring_path(value)

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
        return ResultIterator(c)

    def remove(self, delete=False, with_items=True):
        """Removes this album and all its associated items from the
        library. If delete, then the items' files are also deleted
        from disk, along with any album art. The directories
        containing the album are also removed (recursively) if empty.
        Set with_items to False to avoid removing the album's items.
        """
        if with_items:
            # Remove items.
            for item in self.items():
                self._library.remove(item, delete, False)
        
        if delete:
            # Delete art file.
            artpath = self.artpath
            if artpath:
                util.soft_remove(artpath)
        
        # Remove album from database.
        self._library.conn.execute(
            'DELETE FROM albums WHERE id=?',
            (self.id,)
        )

    def move_art(self, copy=False):
        """Move or copy any existing album art so that it remains in the
        same directory as the items.
        """
        old_art = self.artpath
        if not old_art:
            return

        new_art = self.art_destination(old_art)
        if new_art == old_art:
            return

        log.debug('moving album art %s to %s' % (old_art, new_art))
        if copy:
            util.copy(old_art, new_art)
        else:
            util.move(old_art, new_art)
        self.artpath = new_art

        # Prune old path when moving.
        if not copy: 
            util.prune_dirs(os.path.dirname(old_art),
                            self._library.directory)

    def move(self, copy=False, basedir=None):
        """Moves (or copies) all items to their destination.  Any album
        art moves along with them. basedir overrides the library base
        directory for the destination.
        """
        basedir = basedir or self._library.directory

        # Move items.
        items = list(self.items())
        for item in items:
            self._library.move(item, copy, basedir=basedir, with_album=False)

        # Move art.
        self.move_art(copy)

    def item_dir(self):
        """Returns the directory containing the album's first item,
        provided that such an item exists.
        """
        try:
            item = self.items().next()
        except StopIteration:
            raise ValueError('empty album')
        return os.path.dirname(item.path)

    def art_destination(self, image, item_dir=None):
        """Returns a path to the destination for the album art image
        for the album. `image` is the path of the image that will be
        moved there (used for its extension).

        The path construction uses the existing path of the album's
        items, so the album must contain at least one item or
        item_dir must be provided.
        """
        image = bytestring_path(image)
        item_dir = item_dir or self.item_dir()
        _, ext = os.path.splitext(image)
        dest = os.path.join(item_dir, self._library.art_filename + ext)
        return dest
    
    def set_art(self, path):
        """Sets the album's cover art to the image at the given path.
        The image is copied into place, replacing any existing art.
        """
        path = bytestring_path(path)
        oldart = self.artpath
        artdest = self.art_destination(path)

        if oldart and samefile(path, oldart):
            # Art already set.
            return
        elif samefile(path, artdest):
            # Art already in place.
            self.artpath = path
            return

        # Normal operation.
        if oldart == artdest:
            util.soft_remove(oldart)
        artdest = util.unique_path(artdest)
        util.copy(path, artdest)
        self.artpath = artdest


# Default path template resources.

def _int_arg(s):
    """Convert a string argument to an integer for use in a template
    function.  May raise a ValueError.
    """
    return int(s.strip())
def _tmpl_lower(s):
    """Convert a string to lower case."""
    return s.lower()
def _tmpl_upper(s):
    """Covert a string to upper case."""
    return s.upper()
def _tmpl_title(s):
    """Convert a string to title case."""
    return s.title()
def _tmpl_left(s, chars):
    """Get the leftmost characters of a string."""
    return s[0:_int_arg(chars)]
def _tmpl_right(s, chars):
    """Get the rightmost characters of a string."""
    return s[-_int_arg(chars):]
def _tmpl_if(condition, trueval, falseval=u''):
    """If ``condition`` is nonempty and nonzero, emit ``trueval``;
    otherwise, emit ``falseval`` (if provided).
    """
    try:
        condition = _int_arg(condition)
    except ValueError:
        condition = condition.strip()
    if condition:
        return trueval
    else:
        return falseval
def _tmpl_asciify(s):
    """Translate non-ASCII characters to their ASCII equivalents.
    """
    return unidecode(s)

TEMPLATE_FUNCTIONS = {
    'lower': _tmpl_lower,
    'upper': _tmpl_upper,
    'title': _tmpl_title,
    'left': _tmpl_left,
    'right': _tmpl_right,
    'if': _tmpl_if,
    'asciify': _tmpl_asciify,
}
