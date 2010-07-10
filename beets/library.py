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
import operator
import re
import shutil
import sys
from string import Template
import logging
from beets.mediafile import MediaFile, UnreadableFileError, FileTypeError

MAX_FILENAME_LENGTH = 200

# Fields in the "items" table; all the metadata available for items in the
# library. These are used directly in SQL; they are vulnerable to injection if
# accessible to the user. The fields are divided into read-write
# metadata, all metadata (inlcuding read-only attributes), and all
# fields (i.e., including non-metadata attributes).
metadata_rw_fields = [
    ('title',      'text'),
    ('artist',     'text'),
    ('album',      'text'),
    ('genre',      'text'),
    ('composer',   'text'),
    ('grouping',   'text'),
    ('year',       'int'),
    ('month',      'int'),
    ('day',        'int'),
    ('track',      'int'),
    ('tracktotal', 'int'),
    ('disc',       'int'),
    ('disctotal',  'int'),
    ('lyrics',     'text'),
    ('comments',   'text'),
    ('bpm',        'int'),
    ('comp',       'bool'),
]
metadata_fields = [
    ('length',  'real'),
    ('bitrate', 'int'),
] + metadata_rw_fields
item_fields = [
    ('id',      'integer primary key'),
    ('path',    'text'),
] + metadata_fields
metadata_rw_keys = map(operator.itemgetter(0), metadata_rw_fields)
metadata_keys = map(operator.itemgetter(0), metadata_fields)
item_keys = map(operator.itemgetter(0), item_fields)

# Default search fields for various granularities.
ARTIST_DEFAULT_FIELDS = ('artist',)
ALBUM_DEFAULT_FIELDS = ARTIST_DEFAULT_FIELDS + ('album', 'genre')
ITEM_DEFAULT_FIELDS = ALBUM_DEFAULT_FIELDS + ('title', 'comments')

# Logger.
log = logging.getLogger('beets')
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())


#### exceptions ####

class LibraryError(Exception):
    pass
class InvalidFieldError(Exception):
    pass


#### utility functions ####

def _normpath(path):
    """Provide the canonical form of the path suitable for storing in the
    database.
    """
    return os.path.normpath(os.path.abspath(os.path.expanduser(path)))

def _ancestry(path):
    """Return a list consisting of path's parent directory, its grandparent,
    and so on. For instance, _ancestry('/a/b/c') == ['/', '/a', '/a/b'].
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

def _components(path):
    """Return a list of the path components in path. For instance,
    _components('/a/b/c') == ['a', 'b', 'c'].
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

def _unicode_path(path):
    """Ensures that a path string is in Unicode."""
    if isinstance(path, unicode):
        return path
    return path.decode(sys.getfilesystemencoding())




class Item(object):
    def __init__(self, values):
        self.dirty = {}
        self._fill_record(values)
        self._clear_dirty()
        
    @classmethod
    def from_path(cls, path):
        """Creates a new item from the media file at the specified path.
        """
        i = cls({})
        i.read(_unicode_path(path))
        return i

    def _fill_record(self, values):
        self.record = {}
        for key in item_keys:
            try:
                setattr(self, key, values[key])
            except KeyError:
                pass # don't use values that aren't present

    def _clear_dirty(self):
        self.dirty = {}
        for key in item_keys:
            self.dirty[key] = False

    def __repr__(self):
        return 'Item(' + repr(self.record) + ')'


    #### item field accessors ####

    def __getattr__(self, key):
        """If key is an item attribute (i.e., a column in the database),
        returns the record entry for that key. Otherwise, performs an ordinary
        getattr.
        """
        if key in item_keys:
            return self.record[key]
        else:
            raise AttributeError(key + ' is not a valid item field')

    def __setattr__(self, key, value):
        """If key is an item attribute (i.e., a column in the database), sets
        the record entry for that key to value. Note that to change the
        attribute in the database or in the file's tags, one must call store()
        or write().
        
        Otherwise, performs an ordinary setattr.
        """
        if key in item_keys:
            if (not (key in self.record)) or (self.record[key] != value):
                # don't dirty if value unchanged
                self.record[key] = value
                self.dirty[key] = True
        else:
            super(Item, self).__setattr__(key, value)
    
    
    #### interaction with files' metadata ####
    
    def read(self, read_path=None):
        """Read the metadata from the associated file. If read_path is
        specified, read metadata from that file instead.
        """
        if read_path is None:
            read_path = self.path
        f = MediaFile(read_path)

        for key in metadata_keys:
            setattr(self, key, getattr(f, key))
        self.path = read_path
    
    def write(self):
        """Writes the item's metadata to the associated file.
        """
        f = MediaFile(self.path)
        for key in metadata_rw_keys:
            setattr(f, key, getattr(self, key))
        f.save()
    
    
    #### dealing with files themselves ####
    
    def move(self, library, copy=False):
        """Move the item to its designated location within the library
        directory (provided by destination()). Subdirectories are created as
        needed. If the operation succeeds, the item's path field is updated to
        reflect the new location.
        
        If copy is True, moving the file is copied rather than moved.
        
        Passes on appropriate exceptions if directories cannot be created or
        moving/copying fails.
        
        Note that one should almost certainly call store() and library.save()
        after this method in order to keep on-disk data consistent.
        """
        dest = library.destination(self)
        
        # Create necessary ancestry for the move. Like os.renames but only
        # halfway.
        for ancestor in _ancestry(dest):
            if not os.path.isdir(ancestor):
                os.mkdir(ancestor)
        
        if copy:
            shutil.copy(self.path, dest)
        else:
            shutil.move(self.path, dest)
            
        # Either copying or moving succeeded, so update the stored path.
        self.path = dest









class Query(object):
    """An abstract class representing a query into the item database."""
    def clause(self):
        """Returns (clause, subvals) where clause is a valid sqlite WHERE
        clause implementing the query and subvals is a list of items to be
        substituted for ?s in the clause.
        """
        raise NotImplementedError

    def match(self, item):
        """Check whether this query matches a given Item. Can be used to
        perform queries on arbitrary sets of Items.
        """
        raise NotImplementedError

    def statement(self, columns='*'):
        """Returns (query, subvals) where clause is a sqlite SELECT statement
        to enact this query and subvals is a list of values to substitute in
        for ?s in the query.
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
        if field not in item_keys:
            raise InvalidFieldError(field + ' is not an item key')
        self.field = field
        self.pattern = pattern
        
class MatchQuery(FieldQuery):
    """A query that looks for exact matches in an item field."""
    def clause(self):
        return self.field + " = ?", [self.pattern]

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
    """An abstract query class that aggregates other queries. Can be indexed
    like a list to access the sub-queries.
    """
    def __init__(self, subqueries = ()):
        self.subqueries = subqueries
    
    # is there a better way to do this?
    def __len__(self): return len(self.subqueries)
    def __getitem__(self, key): return self.subqueries[key]
    def __iter__(self): iter(self.subqueries)
    def __contains__(self, item): item in self.subqueries

    def clause_with_joiner(self, joiner):
        """Returns a clause created by joining together the clauses of all
        subqueries with the string joiner (padded by spaces).
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
        """Construct a query from a dictionary, matches, whose keys are item
        field names and whose values are substring patterns.
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
        """Takes a query in the form of a whitespace-separated list of search
        terms that may be preceded with a key followed by a colon. Returns a
        list of pairs (key, term) where key is None if the search term has no
        key.

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
            elif key.lower() in item_keys: # ignore unrecognized keys
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
        self.fields = fields or metadata_rw_keys

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
    """A collection query whose subqueries may be modified after the query is
    initialized.
    """
    def __setitem__(self, key, value): self.subqueries[key] = value
    def __delitem__(self, key): del self.subqueries[key]

class AndQuery(MutableCollectionQuery):
    """A conjunction of a list of other queries."""
    def clause(self):
        return self.clause_with_joiner('and')

    def match(self, item):
        return all([q.match(item) for q in self.subqueries])
def assert_matched(self, result_iterator, title):
    self.assertEqual(result_iterator.next().title, title)
def assert_done(self, result_iterator):
    self.assertRaises(StopIteration, result_iterator.next)
def assert_matched_all(self, result_iterator):
    self.assert_matched(result_iterator, 'Littlest Things')
    self.assert_matched(result_iterator, 'Lovers Who Uncover')
    self.assert_matched(result_iterator, 'Boracay')
    self.assert_matched(result_iterator, 'Take Pills')
    self.assert_done(result_iterator)
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




class BaseLibrary(object):
    """Abstract base class for music libraries, which are loosely
    defined as sets of Items.
    """
    def __init__(self):
        raise NotImplementedError


    ### helpers ###

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


    ### basic operations ###

    def add(self, item, copy=False): #FIXME copy should default to true
        """Add the item as a new object to the library database. The id field
        will be updated; the new id is returned. If copy, then each item is
        copied to the destination location before it is added.
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
        """Refresh the item's metadata from the library database. If fetch_id
        is not specified, use the item's current id.
        """
        raise NotImplementedError

    def store(self, item, store_id=None, store_all=False):
        """Save the item's metadata into the library database. If store_id is
        specified, use it instead of the item's current id. If store_all is
        true, save the entire record instead of just the dirty fields.
        """
        raise NotImplementedError

    def remove(self, item):
        """Removes the item from the database (leaving the file on disk).
        """
        raise NotImplementedError


    ### browsing operations ###
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
        """Returns a sorted list of (artist, album) pairs, possibly
        filtered by an artist name or an arbitrary query. Unqualified
        query string terms only match fields that apply at an album
        granularity: artist, album, and genre.
        """
        out = set()
        for item in self.get(query, ALBUM_DEFAULT_FIELDS):
            if artist is None or item.artist == artist:
                out.add((item.artist, item.album))
        return sorted(out)

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


class Library(BaseLibrary):
    """A music library using an SQLite database as a metadata store."""
    def __init__(self, path='library.blb',
                       directory='~/Music',
                       path_format='$artist/$album/$track $title'):
        self.path = path
        self.directory = directory
        self.path_format = path_format
        
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
            # this way we can access our SELECT results like dictionaries
        
        self._setup()
    
    def _setup(self):
        """Set up the schema of the library file."""
        setup_sql =  'CREATE TABLE IF NOT EXISTS items ('
        setup_sql += ', '.join([' '.join(f) for f in item_fields])
        setup_sql += ');'
        
        self.conn.executescript(setup_sql)
        self.conn.commit()

    def destination(self, item):
        """Returns the path in the library directory designated for item
        item (i.e., where the file ought to be).
        """
        libpath = self.directory
        subpath_tmpl = Template(self.path_format)
        
        # build the mapping for substitution in the path template, beginning
        # with the values from the database
        mapping = {}
        for key in metadata_keys:
            value = getattr(item, key)
            # sanitize the value for inclusion in a path:
            # replace / and leading . with _
            if isinstance(value, basestring):
                value.replace(os.sep, '_')
                value = re.sub(r'[\\/:]|^\.', '_', value)
            elif key in ('track', 'tracktotal', 'disc', 'disctotal'):
                # pad with zeros
                value = '%02i' % value
            else:
                value = str(value)
            mapping[key] = value
        
        # Perform substitution.
        subpath = subpath_tmpl.substitute(mapping)
        
        # Truncate path components.
        comps = _components(subpath)
        for i, comp in enumerate(comps):
            if len(comp) > MAX_FILENAME_LENGTH:
                comps[i] = comp[:MAX_FILENAME_LENGTH]
        subpath = os.path.join(*comps)
        
        # Preserve extension.
        _, extension = os.path.splitext(item.path)
        subpath += extension
        
        return _normpath(os.path.join(libpath, subpath))   

    #### main interface ####
    
    def add(self, item, copy=False):
        #FIXME make a deep copy of the item?
        item.library = self
        if copy:
            item.move(self, copy=True)

        # build essential parts of query
        columns = ','.join([key for key in item_keys if key != 'id'])
        values = ','.join( ['?'] * (len(item_keys)-1) )
        subvars = []
        for key in item_keys:
            if key != 'id':
                subvars.append(getattr(item, key))
        
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
        """Writes the library to disk (completing a sqlite transaction).
        """
        self.conn.commit()

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
        for key in item_keys:
            if (key != 'id') and (item.dirty[key] or store_all):
                assignments += key + '=?,'
                subvars.append(getattr(item, key))
        
        if not assignments:
            # nothing to store (i.e., nothing was dirty)
            return
        
        assignments = assignments[:-1] # knock off last ,

        # finish the query
        query = 'UPDATE items SET ' + assignments + ' WHERE id=?'
        subvars.append(item.id)

        self.conn.execute(query, subvars)
        item._clear_dirty()

    def remove(self, item):
        self.conn.execute('DELETE FROM items WHERE id=?', (item.id,))


    ### browsing ###

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
        sql = "SELECT DISTINCT artist, album FROM items " + \
              "WHERE " + where + \
              " ORDER BY artist, album"
        c = self.conn.execute(sql, subvals)
        return [(res[0], res[1]) for res in c.fetchall()]

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



