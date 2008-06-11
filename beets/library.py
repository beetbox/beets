import sqlite3, os, sys, operator, re
from beets.tag import MediaFile, FileTypeError
from string import Template

# Fields in the "items" table; all the metadata available for items in the
# library. These are used directly in SQL; they are vulnerable to injection if
# accessible to the user.
metadata_fields = [
    ('title',    'text'),
    ('artist',   'text'),
    ('album',    'text'),
    ('genre',    'text'),
    ('composer', 'text'),
    ('grouping', 'text'),
    ('year',     'int'),
    ('track',    'int'),
    ('maxtrack', 'int'),
    ('disc',     'int'),
    ('maxdisc',  'int'),
    ('lyrics',   'text'),
    ('comments', 'text'),
    ('bpm',      'int'),
    ('comp',     'bool')
]
item_fields = [
    ('id',      'integer primary key'),
    ('path',    'text')
] + metadata_fields
metadata_keys = map(operator.itemgetter(0), metadata_fields)
item_keys = map(operator.itemgetter(0), item_fields)

class LibraryError(Exception):
    pass
class InvalidFieldError(Exception):
    pass





class Item(object):
    def __init__(self, values, library=None):
        self.library = library
        self.__fillrecord(values)
    
    def __fillrecord(self, values):
        self.record = {}  
        for key in item_keys:
            try:
                self.record[key] = values[key]
            except KeyError:
                pass # don't use values that aren't present


    #### field accessors ####

    def __getattr__(self, name):
        if name in item_keys:
            return self.record[name]
            # maybe fetch if it's not available
        else:
            return self.__dict__[name]

    def __setattr__(self, name, value):
        if name in item_keys:
            self.record[name] = value
            if self.library: # we're "connected" to a library; keep it updated
                c = self.library.conn.cursor()
                c.execute('update items set ?=? where id=?',
                          (self.colname, obj.record[self.colname],
                           obj.record['id']))
                c.close()
        else:
            self.__dict__[name] = value
    
    
    #### interaction with the database ####
    
    def load(self, fetch_id=None):
        """Refresh the item's metadata from the library database. If fetch_id
        is not specified, use the current item's id."""
        
        if not self.library:
            raise LibraryError('no library to load from')
        
        if load_id is None:
            load_id = self.record['id']
        
        c = self.library.conn.cursor()
        c.execute('select * from items where id=?', (load_id,))
        self.__fillrecord(c.fetchone())
        c.close()
    
    def store(self, store_id=None):
        """Save the item's metadata into the library database. If store_id is
        not specified, use the current item's id."""
        
        if not self.library:
            raise LibraryError('no library to store to')
            
        if store_id is None:
            store_id = self.record['id']
 
        # build assignments for query
        assignments = ','.join( ['?=?'] * (len(item_fields)-1) )
        subvars = []
        for key in item_keys:
            if key != 'id':
                subvars += [key, self.record[key]]

        # finish the query
        query = 'update items set ' + assignments + ' where id=?'
        subvars.append(self.record['id'])

        c = self.library.conn.cursor()
        c.execute(query, subvars)
        c.close()

    def add(self):
        """Add the item as a new object to the library database. The id field
        will be updated; the new id is returned."""
        
        if not self.library:
            raise LibraryError('no library to add to')
            
        # build essential parts of query
        columns = ','.join([key for key in item_keys if key != 'id'])
        values = ','.join( ['?'] * (len(item_keys)-1) )
        subvars = []
        for key in item_keys:
            if key != 'id':
                subvars.append(self.record[key])
        
        # issue query
        c = self.library.conn.cursor()
        query = 'insert into items (' + columns + ') values (' + values + ')'
        c.execute(query, subvars)
        new_id = c.lastrowid
        c.close()
        
        self.record['id'] = new_id
        return new_id
    
    
    #### interaction with files ####
    
    def read(self, read_path=None):
        """Read the metadata from a file. If no read_path is provided, the
        item's path is used. If the item has a library, it is stored after
        the metadata is read."""
        
        if read_path is None:
            read_path = self.record['path']
        f = MediaFile(read_path)
        
        for key in metadata_keys:
            self.record[key] = getattr(f, key)
        self.record['path'] = read_path
        
        if self.library:
            self.add()
    
    def write(self, write_path=None):
        """Writes the item's metadata to a file. If no write_path is specified,
        the metadata is written to the path stored in the item."""
        
        if write_path is None:
            write_path = self.record['path']
        f = MediaFile(write_path)
        
        for key in metadata_keys:
            setattr(f, key, self.record[key])
        
        f.save_tags()
    
    @classmethod
    def from_path(cls, path, library=None):
        """Creates a new item from the media file at the specified path. If a
        library is specified, add it to that library."""
        i = cls({}, library=library)
        i.read(path)
        return i








class Query(object):
    """An abstract class representing a query into the item database."""
    def clause(self):
        """Returns (clause, subvals) where clause is a valid sqlite WHERE
        clause implementing the query and subvals is a list of items to be
        substituted for ?s in the clause."""
        raise NotImplementedError

    def statement(self, columns='*'):
        """Returns (query, subvals) where clause is a sqlite SELECT statement
        to enact this query and subvals is a list of values to substitute in
        for ?s in the query."""
        clause, subvals = self.clause()
        return ('select ' + columns + ' from items where ' + clause, subvals)

    def execute(self, library):
        """Runs the query in the specified library, returning an
        ItemResultIterator."""
        cursor = library.conn.cursor()
        cursor.execute(*self.statement())
        return ResultIterator(cursor)
    
class SubstringQuery(Query):
    """A query that matches a substring in a specific item field."""
    
    def __init__(self, field, pattern):
        if field not in item_keys:
            raise InvalidFieldError(field + ' is not an item key')
        self.field = field
        self.pattern = pattern
    
    def clause(self):
        search = '%' + (self.pattern.replace('\\','\\\\').replace('%','\\%')
                            .replace('_','\\_')) + '%'
        clause = self.field + " like ? escape '\\'"
        subvals = [search]
        return clause, subvals

class CollectionQuery(Query):
    """An abstract query class that aggregates other queries. Can be indexed
    like a list to access the sub-queries."""
    
    def __init__(self, subqueries = ()):
        self.subqueries = subqueries
    
    # is there a better way to do this?
    def __len__(self): return len(self.subqueries)
    def __getitem__(self, key): return self.subqueries[key]
    def __iter__(self): iter(self.subqueries)
    def __contains__(self, item): item in self.subqueries

    def clause_with_joiner(self, joiner):
        """Returns a clause created by joining together the clauses of all
        subqueries with the string joiner (padded by spaces)."""
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
        field names and whose values are substring patterns."""
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
    """A query that matches a substring in any item field. """

    def __init__(self, pattern):
        subqueries = []
        for field in item_keys:
            subqueries.append(SubstringQuery(field, pattern))
        super(AnySubstringQuery, self).__init__(subqueries)

    def clause(self):
        return self.clause_with_joiner('or')

class MutableCollectionQuery(CollectionQuery):
    """A collection query whose subqueries may be modified after the query is
    initialized."""
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
    
    def __init__(self, cursor):
        self.cursor = cursor
    
    def __iter__(self): return self
    
    def next(self):
        try:
            row = self.cursor.next()
        except StopIteration:
            self.cursor.close()
            raise StopIteration
        return Item(row)








class Library(object):
    def __init__(self, path='library.blb'):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
            # this way we can access our SELECT results like dictionaries
        self.__setup()
    
    def __setup(self):
        "Set up the schema of the library file."
        
        # options (library data) table
        setup_sql = """
        create table if not exists options (
            key text primary key,
            value text
        );"""
        
        # items (things in the library) table
        setup_sql += 'create table if not exists items ('
        setup_sql += ', '.join(map(' '.join, item_fields))
        setup_sql += ');'
        
        c = self.conn.cursor()
        c.executescript(setup_sql)
        c.close()
        self.conn.commit()
    
    
    #### utility functions ####
    
    def __normpath(self, path):
        """Provide the canonical form of the path suitable for storing in the
        database. In the future, options may modify the behavior of this
        method."""
        # force absolute paths:
        # os.path.normpath(os.path.abspath(os.path.expanduser(path)))
        return os.path.normpath(os.path.expanduser(path))
    def __log(self, msg):
        """Print a log message."""
        print >>sys.stderr, msg
    
    
    #### main interface ####
    
    def add(self, path, clobber=False):
        """Add a file to the library or recursively search a directory and add
        all its contents."""
        
        if os.path.isdir(path): # directory
            # recurse into contents
            for ent in os.listdir(path):
                self.add(path + os.sep + ent, clobber)
        
        elif os.path.isfile(path): # normal file
            #fixme avoid clobbering/duplicates!
            # add _if_ it's legible (otherwise ignore but say so)
            try:
                Item.from_path(self.__normpath(path), self)
            except FileTypeError:
                self.__log(path + ' of unknown type, skipping')
        
        elif not os.path.exists(path): # no file
            raise IOError('file not found: ' + path)
        
        else: # something else: special file?
            self.__log(path + ' special file, skipping')
    
    def get(self, query):
        """Returns a ResultIterator to the items matching query, which may be
        None (match the entire library), a Query object, or a query string."""
        if query is None:
            query = TrueQuery()
        elif isinstance(query, str) or isinstance(query, unicode):
            query = AndQuery.from_string(query)
        elif not isinstance(query, Query):
            raise ValueError('query must be None or have type Query or str')
        return query.execute(self)
    
    def save(self):
        """Writes the library to disk (completing a sqlite transaction)."""
        self.conn.commit()
