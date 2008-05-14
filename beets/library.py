import sqlite3, os, sys, operator
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
    
    def save(self):
        """Writes the library to disk (completing a sqlite transaction)."""
        self.conn.commit()
