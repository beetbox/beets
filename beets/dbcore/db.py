# This file is part of beets.
# Copyright 2014, Adrian Sampson.
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

"""The central Model and Database constructs for DBCore.
"""
import time
import os
from collections import defaultdict
import threading
import sqlite3
import contextlib

import beets
from beets.util.functemplate import Template
from .query import MatchQuery



# Abstract base for model classes.


class Model(object):
    """An abstract object representing an object in the database. Model
    objects act like dictionaries (i.e., the allow subscript access like
    ``obj['field']``). The same field set is available via attribute
    access as a shortcut (i.e., ``obj.field``). Three kinds of attributes are
    available:

    * **Fixed attributes** come from a predetermined list of field
      names. These fields correspond to SQLite table columns and are
      thus fast to read, write, and query.
    * **Flexible attributes** are free-form and do not need to be listed
      ahead of time.
    * **Computed attributes** are read-only fields computed by a getter
      function provided by a plugin.

    Access to all three field types is uniform: ``obj.field`` works the
    same regardless of whether ``field`` is fixed, flexible, or
    computed.

    Model objects can optionally be associated with a `Library` object,
    in which case they can be loaded and stored from the database. Dirty
    flags are used to track which fields need to be stored.
    """

    # Abstract components (to be provided by subclasses).

    _table = None
    """The main SQLite table name.
    """

    _flex_table = None
    """The flex field SQLite table name.
    """

    _fields = {}
    """A mapping indicating available "fixed" fields on this type. The
    keys are field names and the values are Type objects.
    """

    _bytes_keys = ()
    """Keys whose values should be stored as raw bytes blobs rather than
    strings.
    """

    _search_fields = ()
    """The fields that should be queried by default by unqualified query
    terms.
    """

    @classmethod
    def _getters(cls):
        """Return a mapping from field names to getter functions.
        """
        # We could cache this if it becomes a performance problem to
        # gather the getter mapping every time.
        raise NotImplementedError()

    def _template_funcs(self):
        """Return a mapping from function names to text-transformer
        functions.
        """
        # As above: we could consider caching this result.
        raise NotImplementedError()


    # Basic operation.

    def __init__(self, db=None, **values):
        """Create a new object with an optional Database association and
        initial field values.
        """
        self._db = db
        self._dirty = set()
        self._values_fixed = {}
        self._values_flex = {}

        # Initial contents.
        self.update(values)
        self.clear_dirty()

    def __repr__(self):
        return '{0}({1})'.format(
            type(self).__name__,
            ', '.join('{0}={1!r}'.format(k, v) for k, v in dict(self).items()),
        )

    def clear_dirty(self):
        """Mark all fields as *clean* (i.e., not needing to be stored to
        the database).
        """
        self._dirty = set()

    def _check_db(self, need_id=True):
        """Ensure that this object is associated with a database row: it
        has a reference to a database (`_db`) and an id. A ValueError
        exception is raised otherwise.
        """
        if not self._db:
            raise ValueError('{0} has no database'.format(type(self).__name__))
        if need_id and not self.id:
            raise ValueError('{0} has no id'.format(type(self).__name__))


    # Essential field accessors.

    def __getitem__(self, key):
        """Get the value for a field. Raise a KeyError if the field is
        not available.
        """
        getters = self._getters()
        if key in getters:  # Computed.
            return getters[key](self)
        elif key in self._fields:  # Fixed.
            return self._values_fixed.get(key)
        elif key in self._values_flex:  # Flexible.
            return self._values_flex[key]
        else:
            raise KeyError(key)

    def __setitem__(self, key, value):
        """Assign the value for a field.
        """
        source = self._values_fixed if key in self._fields \
                 else self._values_flex
        old_value = source.get(key)
        source[key] = value
        if old_value != value:
            self._dirty.add(key)

    def __delitem__(self, key):
        """Remove a flexible attribute from the model.
        """
        if key in self._values_flex:  # Flexible.
            del self._values_flex[key]
            self._dirty.add(key)  # Mark for dropping on store.
        elif key in self._getters():  # Computed.
            raise KeyError('computed field {0} cannot be deleted'.format(key))
        elif key in self._fields:  # Fixed.
            raise KeyError('fixed field {0} cannot be deleted'.format(key))
        else:
            raise KeyError('no such field {0}'.format(key))

    def keys(self, computed=False):
        """Get a list of available field names for this object. The
        `computed` parameter controls whether computed (plugin-provided)
        fields are included in the key list.
        """
        base_keys = list(self._fields) + self._values_flex.keys()
        if computed:
            return base_keys + self._getters().keys()
        else:
            return base_keys


    # Act like a dictionary.

    def update(self, values):
        """Assign all values in the given dict.
        """
        for key, value in values.items():
            self[key] = value

    def items(self):
        """Iterate over (key, value) pairs that this object contains.
        Computed fields are not included.
        """
        for key in self:
            yield key, self[key]

    def get(self, key, default=None):
        """Get the value for a given key or `default` if it does not
        exist.
        """
        if key in self:
            return self[key]
        else:
            return default

    def __contains__(self, key):
        """Determine whether `key` is an attribute on this object.
        """
        return key in self.keys(True)

    def __iter__(self):
        """Iterate over the available field names (excluding computed
        fields).
        """
        return iter(self.keys())


    # Convenient attribute access.

    def __getattr__(self, key):
        if key.startswith('_'):
            raise AttributeError('model has no attribute {0!r}'.format(key))
        else:
            try:
                return self[key]
            except KeyError:
                raise AttributeError('no such field {0!r}'.format(key))

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super(Model, self).__setattr__(key, value)
        else:
            self[key] = value

    def __delattr__(self, key):
        if key.startswith('_'):
            super(Model, self).__delattr__(key)
        else:
            del self[key]


    # Database interaction (CRUD methods).

    def store(self):
        """Save the object's metadata into the library database.
        """
        self._check_db()

        # Build assignments for query.
        assignments = ''
        subvars = []
        for key in self._fields:
            if key != 'id' and key in self._dirty:
                self._dirty.remove(key)
                assignments += key + '=?,'
                value = self[key]
                # Wrap path strings in buffers so they get stored
                # "in the raw".
                if key in self._bytes_keys and isinstance(value, str):
                    value = buffer(value)
                subvars.append(value)
        assignments = assignments[:-1]  # Knock off last ,

        with self._db.transaction() as tx:
            # Main table update.
            if assignments:
                query = 'UPDATE {0} SET {1} WHERE id=?'.format(
                    self._table, assignments
                )
                subvars.append(self.id)
                tx.mutate(query, subvars)

            # Modified/added flexible attributes.
            for key, value in self._values_flex.items():
                if key in self._dirty:
                    self._dirty.remove(key)
                    tx.mutate(
                        'INSERT INTO {0} '
                        '(entity_id, key, value) '
                        'VALUES (?, ?, ?);'.format(self._flex_table),
                        (self.id, key, value),
                    )

            # Deleted flexible attributes.
            for key in self._dirty:
                tx.mutate(
                    'DELETE FROM {0} '
                    'WHERE entity_id=? AND key=?'.format(self._flex_table),
                    (self.id, key)
                )

        self.clear_dirty()

    def load(self):
        """Refresh the object's metadata from the library database.
        """
        self._check_db()
        stored_obj = self._db._get(type(self), self.id)
        assert stored_obj is not None, "object {0} not in DB".format(self.id)
        self.update(dict(stored_obj))
        self.clear_dirty()

    def remove(self):
        """Remove the object's associated rows from the database.
        """
        self._check_db()
        with self._db.transaction() as tx:
            tx.mutate(
                'DELETE FROM {0} WHERE id=?'.format(self._table),
                (self.id,)
            )
            tx.mutate(
                'DELETE FROM {0} WHERE entity_id=?'.format(self._flex_table),
                (self.id,)
            )

    def add(self, db=None):
        """Add the object to the library database. This object must be
        associated with a database; you can provide one via the `db`
        parameter or use the currently associated database.

        The object's `id` and `added` fields are set along with any
        current field values.
        """
        if db:
            self._db = db
        self._check_db(False)

        with self._db.transaction() as tx:
            new_id = tx.mutate(
                'INSERT INTO {0} DEFAULT VALUES'.format(self._table)
            )
            self.id = new_id
            self.added = time.time()

            # Mark every non-null field as dirty and store.
            for key in self:
                if self[key] is not None:
                    self._dirty.add(key)
            self.store()


    # Formatting and templating.

    @classmethod
    def _format(cls, key, value, for_path=False):
        """Format a value as the given field for this model.
        """
        # Format the value as a string according to its type, if any.
        if key in cls._fields:
            value = cls._fields[key].format(value)
            # Formatting must result in a string. To deal with
            # Python2isms, implicitly convert ASCII strings.
            assert isinstance(value, basestring), \
                    u'field formatter must produce strings'
            if isinstance(value, bytes):
                value = value.decode('utf8', 'ignore')

        elif not isinstance(value, unicode):
            # Fallback formatter. Convert to unicode at all cost.
            if value is None:
                value = u''
            elif isinstance(value, basestring):
                if isinstance(value, bytes):
                    value = value.decode('utf8', 'ignore')
            else:
                value = unicode(value)

        if for_path:
            sep_repl = beets.config['path_sep_replace'].get(unicode)
            for sep in (os.path.sep, os.path.altsep):
                if sep:
                    value = value.replace(sep, sep_repl)

        return value

    def _get_formatted(self, key, for_path=False):
        """Get a field value formatted as a string (`unicode` object)
        for display to the user. If `for_path` is true, then the value
        will be sanitized for inclusion in a pathname (i.e., path
        separators will be removed from the value).
        """
        return self._format(key, self.get(key), for_path)

    def _formatted_mapping(self, for_path=False):
        """Get a mapping containing all values on this object formatted
        as human-readable strings.
        """
        # In the future, this could be made "lazy" to avoid computing
        # fields unnecessarily.
        out = {}
        for key in self.keys(True):
            out[key] = self._get_formatted(key, for_path)
        return out

    def evaluate_template(self, template, for_path=False):
        """Evaluate a template (a string or a `Template` object) using
        the object's fields. If `for_path` is true, then no new path
        separators will be added to the template.
        """
        # Build value mapping.
        mapping = self._formatted_mapping(for_path)

        # Get template functions.
        funcs = self._template_funcs()

        # Perform substitution.
        if isinstance(template, basestring):
            template = Template(template)
        return template.substitute(mapping, funcs)


    # Parsing.

    @classmethod
    def _parse(cls, key, string):
        """Parse a string as a value for the given key.
        """
        if not isinstance(string, basestring):
            raise TypeError("_parse() argument must be a string")

        typ = cls._fields.get(key)
        if typ:
            return typ.parse(string)
        else:
            # Fall back to unparsed string.
            return string



# Database controller and supporting interfaces.


class Results(object):
    """An item query result set. Iterating over the collection lazily
    constructs LibModel objects that reflect database rows.
    """
    def __init__(self, model_class, rows, db, query=None):
        """Create a result set that will construct objects of type
        `model_class`, which should be a subclass of `LibModel`, out of
        the query result mapping in `rows`. The new objects are
        associated with the database `db`. If `query` is provided, it is
        used as a predicate to filter the results for a "slow query" that
        cannot be evaluated by the database directly.
        """
        self.model_class = model_class
        self.rows = rows
        self.db = db
        self.query = query

    def __iter__(self):
        """Construct Python objects for all rows that pass the query
        predicate.
        """
        for row in self.rows:
            # Get the flexible attributes for the object.
            with self.db.transaction() as tx:
                flex_rows = tx.query(
                    'SELECT * FROM {0} WHERE entity_id=?'.format(
                        self.model_class._flex_table
                    ),
                    (row['id'],)
                )
            values = dict(row)
            values.update(
                dict((row['key'], row['value']) for row in flex_rows)
            )

            # Construct the Python object and yield it if it passes the
            # predicate.
            obj = self.model_class(self.db, **values)
            if not self.query or self.query.match(obj):
                yield obj

    def __len__(self):
        """Get the number of matching objects.
        """
        if self.query:
            # A slow query. Fall back to testing every object.
            count = 0
            for obj in self:
                count += 1
            return count

        else:
            # A fast query. Just count the rows.
            return len(self.rows)

    def __nonzero__(self):
        """Does this result contain any objects?
        """
        return bool(len(self))

    def __getitem__(self, n):
        """Get the nth item in this result set. This is inefficient: all
        items up to n are materialized and thrown away.
        """
        it = iter(self)
        try:
            for i in range(n):
                it.next()
            return it.next()
        except StopIteration:
            raise IndexError('result index {0} out of range'.format(n))

    def get(self):
        """Return the first matching object, or None if no objects
        match.
        """
        it = iter(self)
        try:
            return it.next()
        except StopIteration:
            return None


class Transaction(object):
    """A context manager for safe, concurrent access to the database.
    All SQL commands should be executed through a transaction.
    """
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        """Begin a transaction. This transaction may be created while
        another is active in a different thread.
        """
        with self.db._tx_stack() as stack:
            first = not stack
            stack.append(self)
        if first:
            # Beginning a "root" transaction, which corresponds to an
            # SQLite transaction.
            self.db._db_lock.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Complete a transaction. This must be the most recently
        entered but not yet exited transaction. If it is the last active
        transaction, the database updates are committed.
        """
        with self.db._tx_stack() as stack:
            assert stack.pop() is self
            empty = not stack
        if empty:
            # Ending a "root" transaction. End the SQLite transaction.
            self.db._connection().commit()
            self.db._db_lock.release()

    def query(self, statement, subvals=()):
        """Execute an SQL statement with substitution values and return
        a list of rows from the database.
        """
        cursor = self.db._connection().execute(statement, subvals)
        return cursor.fetchall()

    def mutate(self, statement, subvals=()):
        """Execute an SQL statement with substitution values and return
        the row ID of the last affected row.
        """
        cursor = self.db._connection().execute(statement, subvals)
        return cursor.lastrowid

    def script(self, statements):
        """Execute a string containing multiple SQL statements."""
        self.db._connection().executescript(statements)


class Database(object):
    """A container for Model objects that wraps an SQLite database as
    the backend.
    """
    _models = ()
    """The Model subclasses representing tables in this database.
    """

    def __init__(self, path):
        self.path = path

        self._connections = {}
        self._tx_stacks = defaultdict(list)

        # A lock to protect the _connections and _tx_stacks maps, which
        # both map thread IDs to private resources.
        self._shared_map_lock = threading.Lock()

        # A lock to protect access to the database itself. SQLite does
        # allow multiple threads to access the database at the same
        # time, but many users were experiencing crashes related to this
        # capability: where SQLite was compiled without HAVE_USLEEP, its
        # backoff algorithm in the case of contention was causing
        # whole-second sleeps (!) that would trigger its internal
        # timeout. Using this lock ensures only one SQLite transaction
        # is active at a time.
        self._db_lock = threading.Lock()

        # Set up database schema.
        for model_cls in self._models:
            self._make_table(model_cls._table, model_cls._fields)
            self._make_attribute_table(model_cls._flex_table)


    # Primitive access control: connections and transactions.

    def _connection(self):
        """Get a SQLite connection object to the underlying database.
        One connection object is created per thread.
        """
        thread_id = threading.current_thread().ident
        with self._shared_map_lock:
            if thread_id in self._connections:
                return self._connections[thread_id]
            else:
                # Make a new connection.
                conn = sqlite3.connect(
                    self.path,
                    timeout=beets.config['timeout'].as_number(),
                )

                # Access SELECT results like dictionaries.
                conn.row_factory = sqlite3.Row

                self._connections[thread_id] = conn
                return conn

    @contextlib.contextmanager
    def _tx_stack(self):
        """A context manager providing access to the current thread's
        transaction stack. The context manager synchronizes access to
        the stack map. Transactions should never migrate across threads.
        """
        thread_id = threading.current_thread().ident
        with self._shared_map_lock:
            yield self._tx_stacks[thread_id]

    def transaction(self):
        """Get a :class:`Transaction` object for interacting directly
        with the underlying SQLite database.
        """
        return Transaction(self)


    # Schema setup and migration.

    def _make_table(self, table, fields):
        """Set up the schema of the database. `fields` is a mapping
        from field names to `Type`s. Columns are added if necessary.
        """
        # Get current schema.
        with self.transaction() as tx:
            rows = tx.query('PRAGMA table_info(%s)' % table)
        current_fields = set([row[1] for row in rows])

        field_names = set(fields.keys())
        if current_fields.issuperset(field_names):
            # Table exists and has all the required columns.
            return

        if not current_fields:
            # No table exists.
            columns = []
            for name, typ in fields.items():
                columns.append('{0} {1}'.format(name, typ.sql))
            setup_sql = 'CREATE TABLE {0} ({1});\n'.format(table,
                                                           ', '.join(columns))

        else:
            # Table exists does not match the field set.
            setup_sql = ''
            for name, typ in fields.items():
                if name in current_fields:
                    continue
                setup_sql += 'ALTER TABLE {0} ADD COLUMN {1} {2};\n'.format(
                    table, name, typ.sql
                )

        with self.transaction() as tx:
            tx.script(setup_sql)

    def _make_attribute_table(self, flex_table):
        """Create a table and associated index for flexible attributes
        for the given entity (if they don't exist).
        """
        with self.transaction() as tx:
            tx.script("""
                CREATE TABLE IF NOT EXISTS {0} (
                    id INTEGER PRIMARY KEY,
                    entity_id INTEGER,
                    key TEXT,
                    value TEXT,
                    UNIQUE(entity_id, key) ON CONFLICT REPLACE);
                CREATE INDEX IF NOT EXISTS {0}_by_entity
                    ON {0} (entity_id);
                """.format(flex_table))


    # Querying.

    def _fetch(self, model_cls, query, order_by=None):
        """Fetch the objects of type `model_cls` matching the given
        query. The query may be given as a string, string sequence, a
        Query object, or None (to fetch everything). If provided,
        `order_by` is a SQLite ORDER BY clause for sorting.
        """
        where, subvals = query.clause()

        sql = "SELECT * FROM {0} WHERE {1}".format(
            model_cls._table,
            where or '1',
        )
        if order_by:
            sql += " ORDER BY {0}".format(order_by)
        with self.transaction() as tx:
            rows = tx.query(sql, subvals)

        return Results(model_cls, rows, self, None if where else query)

    def _get(self, model_cls, id):
        """Get a Model object by its id or None if the id does not
        exist.
        """
        return self._fetch(model_cls, MatchQuery('id', id)).get()
