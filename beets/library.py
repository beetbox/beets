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

import sqlite3
import os
import operator
import re
import shutil
from string import Template
import logging
from beets.mediafile import MediaFile, FileTypeError

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

def _walk_files(path):
    """Like os.walk, but only yields the files in the directory tree. The full
    pathnames to the files (under path) are given. Also, if path is a file,
    _walk_files just yields that.
    """
    if os.path.isfile(path):
        yield path
    else:
        for root, dirs, files in os.walk(path):
            for filebase in files:
                yield os.path.join(root, filebase)

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





class Item(object):
    def __init__(self, values, library=None):
        self.library = library
        self.dirty = {}
        self._fill_record(values)
        self._clear_dirty()
    
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
        return 'Item(' + repr(self.record) + \
               ', library=' + repr(self.library) + ')'


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
    
    
    #### interaction with the database ####
    
    def load(self, load_id=None):
        """Refresh the item's metadata from the library database. If fetch_id
        is not specified, use the current item's id.
        """
        if not self.library:
            raise LibraryError('no library to load from')
        
        if load_id is None:
            load_id = self.id
        
        c = self.library.conn.execute(
                'SELECT * FROM items WHERE id=?', (load_id,) )
        self._fill_record(c.fetchone())
        self._clear_dirty()
        c.close()
    
    def store(self, store_id=None, store_all=False):
        """Save the item's metadata into the library database. If store_id is
        specified, use it instead of the item's current id. If store_all is
        true, save the entire record instead of just the dirty fields.
        """
        if not self.library:
            raise LibraryError('no library to store to')
            
        if store_id is None:
            store_id = self.id
 
        # build assignments for query
        assignments = ''
        subvars = []
        for key in item_keys:
            if (key != 'id') and (self.dirty[key] or store_all):
                assignments += key + '=?,'
                subvars.append(getattr(self, key))
        
        if not assignments:
            # nothing to store (i.e., nothing was dirty)
            return
        
        assignments = assignments[:-1] # knock off last ,

        # finish the query
        query = 'UPDATE items SET ' + assignments + ' WHERE id=?'
        subvars.append(self.id)

        self.library.conn.execute(query, subvars)
        self._clear_dirty()

    def add(self, library=None):
        """Add the item as a new object to the library database. The id field
        will be updated; the new id is returned. If library is specified, set
        the item's library before adding.
        """
        if library:
            self.library = library
        if not self.library:
            raise LibraryError('no library to add to')
            
        # build essential parts of query
        columns = ','.join([key for key in item_keys if key != 'id'])
        values = ','.join( ['?'] * (len(item_keys)-1) )
        subvars = []
        for key in item_keys:
            if key != 'id':
                subvars.append(getattr(self, key))
        
        # issue query
        c = self.library.conn.cursor()
        query = 'INSERT INTO items (' + columns + ') VALUES (' + values + ')'
        c.execute(query, subvars)
        new_id = c.lastrowid
        c.close()
        
        self._clear_dirty()
        self.id = new_id
        return new_id
    
    def remove(self):
        """Removes the item from the database (leaving the file on disk).
        """
        self.library.conn.execute('DELETE FROM items WHERE id=?',
                                  (self.id,) )
    
    
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
    
    def destination(self):
        """Returns the path within the library directory designated for this
        item (i.e., where the file ought to be).
        """
        libpath = self.library.directory
        subpath_tmpl = Template(self.library.path_format)
        
        # build the mapping for substitution in the path template, beginning
        # with the values from the database
        mapping = {}
        for key in metadata_keys:
            value = getattr(self, key)
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
        _, extension = os.path.splitext(self.path)
        subpath += extension
        
        return _normpath(os.path.join(libpath, subpath))
    
    def move(self, copy=False):
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
        dest = self.destination()
        
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
    
    def delete(self):
        """Deletes the item from the filesystem. If the item is located
        in the library directory, any empty parent directories are trimmed.
        Also calls remove(), deleting the appropriate row from the database.
        
        As with move(), library.save() should almost certainly be called after
        invoking this (although store() should not).
        """
        os.unlink(self.path)
        self.remove()
    
    @classmethod
    def from_path(cls, path, library=None):
        """Creates a new item from the media file at the specified path. Sets
        the item's library (but does not add the item) if library is
        specified.
        """
        i = cls({})
        i.read(path)
        i.library = library
        return i








class Query(object):
    """An abstract class representing a query into the item database."""
    def clause(self):
        """Returns (clause, subvals) where clause is a valid sqlite WHERE
        clause implementing the query and subvals is a list of items to be
        substituted for ?s in the clause.
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

class SubstringQuery(FieldQuery):
    """A query that matches a substring in a specific item field."""
    
    def clause(self):
        search = '%' + (self.pattern.replace('\\','\\\\').replace('%','\\%')
                            .replace('_','\\_')) + '%'
        clause = self.field + " like ? escape '\\'"
        subvals = [search]
        return clause, subvals

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
    def from_string(cls, query_string):
        """Creates a query from a string in the format used by _parse_query."""
        subqueries = []
        for key, pattern in cls._parse_query(query_string):
            if key is None: # no key specified; match any field
                subqueries.append(AnySubstringQuery(pattern))
            elif key.lower() in item_keys: # ignore unrecognized keys
                subqueries.append(SubstringQuery(key.lower(), pattern))
        if not subqueries: # no terms in query
            subqueries = [TrueQuery()]
        return cls(subqueries)

class AnySubstringQuery(CollectionQuery):
    """A query that matches a substring in any metadata field. """

    def __init__(self, pattern):
        subqueries = []
        for field in metadata_rw_keys:
            subqueries.append(SubstringQuery(field, pattern))
        super(AnySubstringQuery, self).__init__(subqueries)

    def clause(self):
        return self.clause_with_joiner('or')

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

class TrueQuery(Query):
    """A query that always matches."""
    def clause(self):
        return '1', ()

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
        return Item(row, self.library)








class Library(object):
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
    

    ### helpers ###

    @classmethod
    def _get_query(cls, val=None):
        """Takes a value which may be None, a query string, or a Query object,
        and returns a suitable Query object.
        """
        if val is None:
            return TrueQuery()
        elif isinstance(val, basestring):
            return AndQuery.from_string(val)
        elif isinstance(val, Query):
            return val
        elif not isinstance(query, Query):
            raise ValueError('query must be None or have type Query or str')
       

    
    #### main interface ####
    
    def add(self, path, copy=False):
        """Add a file to the library or recursively search a directory and add
        all its contents. If copy is True, copy files to their destination in
        the library directory while adding.
        """
        
        for f in _walk_files(path):
            try:
                i = Item.from_path(_normpath(f), self)
                if copy:
                    i.move(copy=True)
                i.add()
            except FileTypeError:
                log.warn(f + ' of unknown type, skipping')
    
    def get(self, query=None):
        """Returns a ResultIterator to the items matching query, which may be
        None (match the entire library), a Query object, or a query string.
        """
        return self._get_query(query).execute(self)
    
    def save(self):
        """Writes the library to disk (completing a sqlite transaction).
        """
        self.conn.commit()


    ### browsing ###

    def artists(self, query=None):
        """Returns a list of artists in the database, possibly filtered by a
        query (in the same sense as get()).
        """
        where, subvals = self._get_query(query).clause()
        sql = "SELECT DISTINCT artist FROM items " + \
              "WHERE " + where + \
              " ORDER BY artist"
        c = self.conn.execute(sql, subvals)
        return [res[0] for res in c.fetchall()]

    def albums(self, artist=None, query=None):
        """Returns a list of (artist, album) pairs, possibly filtered by an
        artist name or an arbitrary query.
        """
        query = self._get_query(query)
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
        """Returns a ResultIterator over the items matching the given artist,
        album, title, and query (if present). Sorts in such a way as to group
        albums appropriately.
        """
        queries = [self._get_query(query)]
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

