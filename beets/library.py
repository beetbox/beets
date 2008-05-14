#!/usr/bin/env python
import sqlite3, os, sys, operator
import beets.tag
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

class Library(object):
    def __init__(self, path='library.blb'):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.setup()
    
    def setup(self):
        "Set up the schema of the library file."
        
        # options (library data) table
        setup_sql = """
        create table if not exists options (
            key text primary key,
            value text
        );"""
        
        # items (things in the library) table
        setup_sql += """create table if not exists items (
                            path text primary key, """
        setup_sql += ', '.join(map(' '.join, metadata_fields))
        setup_sql += ' );'
        
        c = self.conn.cursor()
        c.executescript(setup_sql)
        c.close()
        self.conn.commit()
    
    # DATABASE UTILITY FUNCTIONS
    def select(self, where='', subvars=[], columns='*'):
        "Look up items in the library. Returns a cursor."
        c = self.conn.cursor()
        if where.strip(): # we have a where clause
            where = ' where ' + where
        c.execute('select ' + columns + ' from items' + where,
                    subvars)
        return c
    def selects_any(self, where, subvars):
        "Returns True iff the SELECT query matches any rows."
        c = self.select(where, subvars)
        out = (c.fetchone() is not None)
        c.close()
    
    # FILE/DB UTILITY FUNCTIONS
    def add_file(self, path):
        "Adds a new file to the library."
        
        # build query part for metadata fields
        columns = ','.join(map(operator.itemgetter(0),metadata_fields))
        values = ','.join(['?']*len(metadata_fields))
        subvars = []
        f = beets.tag.MediaFile(path)
        for field, value in metadata_fields:
            subvars.append(getattr(f, field))
        
        # other fields
        columns += ',path'
        values += ',?'
        subvars.append(path)
        
        # issue query
        c = self.conn.cursor()
        query = 'insert into items (' + columns + ') values (' + values + ')'
        c.execute(query, subvars)
        c.close()

    def update_file(self, path):
        "Updates a file already in the database with the file's metadata."
        
        # build query part for metadata fields
        assignments = ','.join(['?=?']*len(metadata_fields))
        subvars = []
        f = beets.tag.MediaFile(path)
        for field, value in metadata_fields:
            subvars += [field, getattr(f, field)]
        
        # build the full query itself
        query = 'update items set ' + assignments + ' where path=?'
        subvars.append(path)
        
        c = self.conn.cursor()
        c.execute(query, subvars)
        c.close()
    
    # MISC. UTILITY FUNCTIONS
    def mynormpath(self, path):
        """Provide the canonical form of the path suitable for storing in the
        database. In the future, options may modify the behavior of this
        method."""
        # force absolute paths:
        # os.path.normpath(os.path.abspath(os.path.expanduser(path)))
        return os.path.normpath(os.path.expanduser(path))
    def log(self, msg):
        """Print a log message."""
        print >>sys.stderr, msg
    def pprint(self, item, form='$artist - $title'):
        print Template(form).substitute(item)
    
    def add_path(self, path, clobber=False):
        """Add a file to the library or recursively search a directory and add
        all its contents."""
        if os.path.isdir(path):
            # recurse into all directory contents
            for ent in os.listdir(path):
                self.add_path(path + os.sep + ent, clobber)
        elif os.path.isfile(path):
            # add _if_ it's legible (otherwise ignore but say so)
            if self.selects_any('path=?', (self.mynormpath(path),)):
                if not clobber:
                    self.log(path + ' already in database, skipping')
                    return
                else:
                    self.update_file(self.mynormpath(path))
            else:
                try:
                    self.add_file(self.mynormpath(path))
                except beets.tag.FileTypeError:
                    self.log(path + ' of unknown type, skipping')
        elif not os.path.exists(path):
            raise IOError('file not found: ' + path)
    
    # high-level (and command-line) interface
    def add(self, *paths):
        for path in paths:
            self.add_path(path, clobber=False)
            self.conn.commit()
    def remove(self, *criteria):
        raise NotImplementedError
    def update(self, *criteria):
        #c = self.select(criteria, [], 'path')
        #for f in c:
        #    self.update_file(f.path)
        #c.close()
        raise NotImplementedError
    def write(self, *criteria):
        raise NotImplementedError
    def list(self, *criteria):
        c = self.select(' '.join(criteria), [])
        for row in c:
            self.pprint(row)
        c.close()