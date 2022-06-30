# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

import json
import time
import os
import re
from functools import reduce
from itertools import chain
from operator import add
from collections import defaultdict
import threading
import sqlite3
import contextlib

from unidecode import unidecode
import beets
from beets.util import functemplate
from beets.util import py3_path
from beets.dbcore import types
from .query import MatchQuery, NullSort, TrueQuery
from collections.abc import Mapping

DEBUG = 0

# converter to load json strings produced by the 'group_to_json' aggregate
sqlite3.register_converter("json_str", json.loads)


class DBAccessError(Exception):
    """The SQLite database became inaccessible.

    This can happen when trying to read or write the database when, for
    example, the database file is deleted or otherwise disappears. There
    is probably no way to recover from this error.
    """


class FormattedMapping(Mapping):
    """A `dict`-like formatted view of a model.

    The accessor `mapping[key]` returns the formatted version of
    `model[key]` as a unicode string.

    The `included_keys` parameter allows filtering the fields that are
    returned. By default all fields are returned. Limiting to specific keys can
    avoid expensive per-item database queries.

    If `for_path` is true, all path separators in the formatted values
    are replaced.
    """

    ALL_KEYS = '*'

    def __init__(self, model, included_keys=ALL_KEYS, for_path=False):
        self.for_path = for_path
        self.model = model
        if included_keys == self.ALL_KEYS:
            # Performance note: this triggers a database query.
            self.model_keys = self.model.keys(True)
        else:
            self.model_keys = included_keys

    def __getitem__(self, key):
        if key in self.model_keys:
            return self._get_formatted(self.model, key)
        else:
            raise KeyError(key)

    def __iter__(self):
        return iter(self.model_keys)

    def __len__(self):
        return len(self.model_keys)

    def get(self, key, default=None):
        if default is None:
            default = self.model._type(key).format(None)
        return super().get(key, default)

    def _get_formatted(self, model, key):
        value = model._type(key).format(model.get(key))
        if isinstance(value, bytes):
            value = value.decode('utf-8', 'ignore')

        if self.for_path:
            sep_repl = beets.config['path_sep_replace'].as_str()
            sep_drive = beets.config['drive_sep_replace'].as_str()

            if re.match(r'^\w:', value):
                value = re.sub(r'(?<=^\w):', sep_drive, value)

            for sep in (os.path.sep, os.path.altsep):
                if sep:
                    value = value.replace(sep, sep_repl)

        return value


class LazyConvertDict:
    """Lazily convert types for attributes fetched from the database
    """

    def __init__(self, model_cls):
        """Initialize the object empty
        """
        self.data = {}
        self.model_cls = model_cls
        self._converted = {}

    def init(self, data):
        """Set the base data that should be lazily converted
        """
        self.data = data

    def _convert(self, key, value):
        """Convert the attribute type according the the SQL type
        """
        return self.model_cls._type(key).from_sql(value)

    def __setitem__(self, key, value):
        """Set an attribute value, assume it's already converted
        """
        self._converted[key] = value

    def __getitem__(self, key):
        """Get an attribute value, converting the type on demand
        if needed
        """
        if key in self._converted:
            return self._converted[key]
        elif key in self.data:
            value = self._convert(key, self.data[key])
            self._converted[key] = value
            return value

    def __delitem__(self, key):
        """Delete both converted and base data
        """
        if key in self._converted:
            del self._converted[key]
        if key in self.data:
            del self.data[key]

    def keys(self):
        """Get a list of available field names for this object.
        """
        return list(self._converted.keys()) + list(self.data.keys())

    def copy(self):
        """Create a copy of the object.
        """
        new = self.__class__(self.model_cls)
        new.data = self.data.copy()
        new._converted = self._converted.copy()
        return new

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
        return key in self.keys()

    def __iter__(self):
        """Iterate over the available field names (excluding computed
        fields).
        """
        return iter(self.keys())


# Abstract base for model classes.

class Model:
    """An abstract object representing an object in the database. Model
    objects act like dictionaries (i.e., they allow subscript access like
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
    keys are field names and the values are `Type` objects.
    """

    _search_fields = ()
    """The fields that should be queried by default by unqualified query
    terms.
    """

    _types = {}
    """Optional Types for non-fixed (i.e., flexible and computed) fields.
    """

    _sorts = {}
    """Optional named sort criteria. The keys are strings and the values
    are subclasses of `Sort`.
    """

    _queries = {}
    """Named queries that use a field-like `name:value` syntax but which
    do not relate to any specific field.
    """

    _always_dirty = False
    """By default, fields only become "dirty" when their value actually
    changes. Enabling this flag marks fields as dirty even when the new
    value is the same as the old value (e.g., `o.f = o.f`).
    """

    _revision = -1
    """A revision number from when the model was loaded from or written
    to the database.
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
        self._values_fixed = LazyConvertDict(self)
        self._values_flex = LazyConvertDict(self)

        # Initial contents.
        self.update(values)
        self.clear_dirty()

    @classmethod
    def _awaken(cls, db=None, fixed_values={}, flex_values={}):
        """Create an object with values drawn from the database.

        This is a performance optimization: the checks involved with
        ordinary construction are bypassed.
        """
        obj = cls(db)

        obj._values_fixed.init(fixed_values)
        obj._values_flex.init(flex_values)

        return obj

    def __repr__(self):
        return '{}({})'.format(
            type(self).__name__,
            ', '.join(f'{k}={v!r}' for k, v in dict(self).items()),
        )

    def clear_dirty(self):
        """Mark all fields as *clean* (i.e., not needing to be stored to
        the database). Also update the revision.
        """
        self._dirty = set()
        if self._db:
            self._revision = self._db.revision

    def _check_db(self, need_id=True):
        """Ensure that this object is associated with a database row: it
        has a reference to a database (`_db`) and an id. A ValueError
        exception is raised otherwise.
        """
        if not self._db:
            raise ValueError(
                '{} has no database'.format(type(self).__name__)
            )
        if need_id and not self.id:
            raise ValueError('{} has no id'.format(type(self).__name__))

    def copy(self):
        """Create a copy of the model object.

        The field values and other state is duplicated, but the new copy
        remains associated with the same database as the old object.
        (A simple `copy.deepcopy` will not work because it would try to
        duplicate the SQLite connection.)
        """
        new = self.__class__()
        new._db = self._db
        new._values_fixed = self._values_fixed.copy()
        new._values_flex = self._values_flex.copy()
        new._dirty = self._dirty.copy()
        return new

    # Essential field accessors.

    @classmethod
    def _type(cls, key):
        """Get the type of a field, a `Type` instance.

        If the field has no explicit type, it is given the base `Type`,
        which does no conversion.
        """
        return cls._fields.get(key) or cls._types.get(key) or types.DEFAULT

    def _get(self, key, default=None, raise_=False):
        """Get the value for a field, or `default`. Alternatively,
        raise a KeyError if the field is not available.
        """
        getters = self._getters()
        if key in getters:  # Computed.
            return getters[key](self)
        elif key in self._fields:  # Fixed.
            if key in self._values_fixed:
                return self._values_fixed[key]
            else:
                return self._type(key).null
        elif key in self._values_flex:  # Flexible.
            return self._values_flex[key]
        elif raise_:
            raise KeyError(key)
        else:
            return default

    get = _get

    def __getitem__(self, key):
        """Get the value for a field. Raise a KeyError if the field is
        not available.
        """
        return self._get(key, raise_=True)

    def _setitem(self, key, value):
        """Assign the value for a field, return whether new and old value
        differ.
        """
        # Choose where to place the value.
        if key in self._fields:
            source = self._values_fixed
        else:
            source = self._values_flex

        # If the field has a type, filter the value.
        value = self._type(key).normalize(value)

        # Assign value and possibly mark as dirty.
        old_value = source.get(key)
        source[key] = value
        changed = old_value != value
        if self._always_dirty or changed:
            self._dirty.add(key)

        return changed

    def __setitem__(self, key, value):
        """Assign the value for a field.
        """
        self._setitem(key, value)

    def __delitem__(self, key):
        """Remove a flexible attribute from the model.
        """
        if key in self._values_flex:  # Flexible.
            del self._values_flex[key]
            self._dirty.add(key)  # Mark for dropping on store.
        elif key in self._fields:  # Fixed
            setattr(self, key, self._type(key).null)
        elif key in self._getters():  # Computed.
            raise KeyError(f'computed field {key} cannot be deleted')
        else:
            raise KeyError(f'no such field {key}')

    def keys(self, computed=False):
        """Get a list of available field names for this object. The
        `computed` parameter controls whether computed (plugin-provided)
        fields are included in the key list.
        """
        base_keys = list(self._fields) + list(self._values_flex.keys())
        if computed:
            return base_keys + list(self._getters().keys())
        else:
            return base_keys

    @classmethod
    def all_keys(cls):
        """Get a list of available keys for objects of this type.
        Includes fixed and computed fields.
        """
        return list(cls._fields) + list(cls._getters().keys())

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

    def __contains__(self, key):
        """Determine whether `key` is an attribute on this object.
        """
        return key in self.keys(computed=True)

    def __iter__(self):
        """Iterate over the available field names (excluding computed
        fields).
        """
        return iter(self.keys())

    # Convenient attribute access.

    def __getattr__(self, key):
        if key.startswith('_'):
            raise AttributeError(f'model has no attribute {key!r}')
        else:
            try:
                return self[key]
            except KeyError:
                raise AttributeError(f'no such field {key!r}')

    def __setattr__(self, key, value):
        if key.startswith('_'):
            super().__setattr__(key, value)
        else:
            self[key] = value

    def __delattr__(self, key):
        if key.startswith('_'):
            super().__delattr__(key)
        else:
            del self[key]

    # Database interaction (CRUD methods).

    def store(self, fields=None):
        """Save the object's metadata into the library database.
        :param fields: the fields to be stored. If not specified, all fields
        will be.
        """
        if fields is None:
            fields = self._fields
        self._check_db()

        # Build assignments for query.
        assignments = []
        subvars = []
        for key in fields:
            if key != 'id' and key in self._dirty:
                self._dirty.remove(key)
                assignments.append(key + '=?')
                value = self._type(key).to_sql(self[key])
                subvars.append(value)
        assignments = ','.join(assignments)

        with self._db.transaction() as tx:
            # Main table update.
            if assignments:
                query = 'UPDATE {} SET {} WHERE id=?'.format(
                    self._table, assignments
                )
                subvars.append(self.id)
                tx.mutate(query, subvars)

            # Modified/added flexible attributes.
            for key, value in self._values_flex.items():
                if key in self._dirty:
                    self._dirty.remove(key)
                    tx.mutate(
                        'INSERT INTO {} '
                        '(entity_id, key, value) '
                        'VALUES (?, ?, ?);'.format(self._flex_table),
                        (self.id, key, value),
                    )

            # Deleted flexible attributes.
            for key in self._dirty:
                tx.mutate(
                    'DELETE FROM {} '
                    'WHERE entity_id=? AND key=?'.format(self._flex_table),
                    (self.id, key)
                )

        self.clear_dirty()

    def load(self):
        """Refresh the object's metadata from the library database.

        If check_revision is true, the database is only queried loaded when a
        transaction has been committed since the item was last loaded.
        """
        self._check_db()
        if not self._dirty and self._db.revision == self._revision:
            # Exit early
            return
        stored_obj = self._db._get(type(self), self.id)
        assert stored_obj is not None, f"object {self.id} not in DB"
        self._values_fixed = LazyConvertDict(self)
        self._values_flex = LazyConvertDict(self)
        self.update(dict(stored_obj))
        self.clear_dirty()

    def remove(self):
        """Remove the object's associated rows from the database.
        """
        self._check_db()
        with self._db.transaction() as tx:
            tx.mutate(
                f'DELETE FROM {self._table} WHERE id=?',
                (self.id,)
            )
            tx.mutate(
                f'DELETE FROM {self._flex_table} WHERE entity_id=?',
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
                f'INSERT INTO {self._table} DEFAULT VALUES'
            )
            self.id = new_id
            self.added = time.time()

            # Mark every non-null field as dirty and store.
            for key in self:
                if self[key] is not None:
                    self._dirty.add(key)
            self.store()

    # Formatting and templating.

    _formatter = FormattedMapping

    def formatted(self, included_keys=_formatter.ALL_KEYS, for_path=False):
        """Get a mapping containing all values on this object formatted
        as human-readable unicode strings.
        """
        return self._formatter(self, included_keys, for_path)

    def evaluate_template(self, template, for_path=False):
        """Evaluate a template (a string or a `Template` object) using
        the object's fields. If `for_path` is true, then no new path
        separators will be added to the template.
        """
        # Perform substitution.
        if isinstance(template, str):
            template = functemplate.template(template)
        return template.substitute(self.formatted(for_path=for_path),
                                   self._template_funcs())

    # Parsing.

    @classmethod
    def _parse(cls, key, string):
        """Parse a string as a value for the given key.
        """
        if not isinstance(string, str):
            raise TypeError("_parse() argument must be a string")

        return cls._type(key).parse(string)

    def set_parse(self, key, string):
        """Set the object's key to a value represented by a string.
        """
        self[key] = self._parse(key, string)


# Database controller and supporting interfaces.

class Results:
    """An item query result set. Iterating over the collection lazily
    constructs LibModel objects that reflect database rows.
    """

    def __init__(self, model_class, rows, db, sort=None):
        """Create a result set that will construct objects of type
        `model_class`.

        `model_class` is a subclass of `LibModel` that will be
        constructed. `rows` is a query result: a list of mappings. The
        new objects will be associated with the database `db`.

        If `sort` is provided, it is used to sort the
        full list of results before returning. This means it is a "slow
        sort" and all objects must be built before returning the first
        one.
        """
        self.model_class = model_class
        self.rows = rows
        self.db = db
        self.sort = sort

        # We keep a queue of rows we haven't yet consumed for
        # materialization. We preserve the original total number of
        # rows.
        self._rows = rows
        self._row_count = len(rows)

        # The materialized objects corresponding to rows that have been
        # consumed.
        self._objects = []

    def _get_objects(self):
        """Construct and generate Model objects for they query. The
        objects are returned in the order emitted from the database; no
        slow sort is applied.

        For performance, this generator caches materialized objects to
        avoid constructing them more than once. This way, iterating over
        a `Results` object a second time should be much faster than the
        first.
        """

        index = 0  # Position in the materialized objects.
        while index < len(self._objects) or self._rows:
            # Are there previously-materialized objects to produce?
            if index < len(self._objects):
                yield self._objects[index]
                index += 1

            # Otherwise, we consume another row, materialize its object
            # and produce it.
            else:
                while self._rows:
                    row = self._rows.pop(0)
                    obj = self._make_model(row)
                    self._objects.append(obj)
                    index += 1
                    yield obj
                    break

    def __iter__(self):
        """Construct and generate Model objects for all matching
        objects, in sorted order.
        """
        if self.sort:
            # Slow sort. Must build the full list first.
            objects = self.sort.sort(list(self._get_objects()))
            return iter(objects)

        else:
            # Objects are pre-sorted (i.e., by the database).
            return self._get_objects()

    def _make_model(self, row):
        """ Create a Model object for the given row."""
        values = dict(row)
        flex_values = values.pop("flex_attrs", {})

        # Construct the Python object
        return self.model_class._awaken(self.db, values, flex_values)

    def __len__(self):
        """Get the number of matching objects.
        """
        if not self._rows:
            # Fully materialized. Just count the objects.
            return len(self._objects)
        else:
            # Just count the rows.
            return self._row_count

    def __nonzero__(self):
        """Does this result contain any objects?
        """
        return self.__bool__()

    def __bool__(self):
        """Does this result contain any objects?
        """
        return bool(len(self))

    def __getitem__(self, n):
        """Get the nth item in this result set. This is inefficient: all
        items up to n are materialized and thrown away.
        """
        if not self._rows and not self.sort:
            # Fully materialized and already in order. Just look up the
            # object.
            return self._objects[n]

        it = iter(self)
        try:
            for i in range(n):
                next(it)
            return next(it)
        except StopIteration:
            raise IndexError(f'result index {n} out of range')

    def get(self):
        """Return the first matching object, or None if no objects
        match.
        """
        it = iter(self)
        try:
            return next(it)
        except StopIteration:
            return None


class Transaction:
    """A context manager for safe, concurrent access to the database.
    All SQL commands should be executed through a transaction.
    """

    _mutated = False
    """A flag storing whether a mutation has been executed in the
    current transaction.
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
        # Beware of races; currently secured by db._db_lock
        self.db.revision += self._mutated
        with self.db._tx_stack() as stack:
            assert stack.pop() is self
            empty = not stack
        if empty:
            # Ending a "root" transaction. End the SQLite transaction.
            self.db._connection().commit()
            self._mutated = False
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
        try:
            cursor = self.db._connection().execute(statement, subvals)
        except sqlite3.OperationalError as e:
            # In two specific cases, SQLite reports an error while accessing
            # the underlying database file. We surface these exceptions as
            # DBAccessError so the application can abort.
            if e.args[0] in ("attempt to write a readonly database",
                             "unable to open database file"):
                raise DBAccessError(e.args[0])
            else:
                raise
        else:
            self._mutated = True
            return cursor.lastrowid

    def script(self, statements):
        """Execute a string containing multiple SQL statements."""
        # We don't know whether this mutates, but quite likely it does.
        self._mutated = True
        self.db._connection().executescript(statements)


class Database:
    """A container for Model objects that wraps an SQLite database as
    the backend.
    """

    _models = ()
    """The Model subclasses representing tables in this database.
    """

    supports_extensions = hasattr(sqlite3.Connection, 'enable_load_extension')
    """Whether or not the current version of SQLite supports extensions"""

    revision = 0
    """The current revision of the database. To be increased whenever
    data is written in a transaction.
    """

    def __init__(self, path, timeout=5.0):
        self.path = path
        self.timeout = timeout

        self._connections = {}
        self._tx_stacks = defaultdict(list)
        self._extensions = []

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
                conn = self._create_connection()
                self._connections[thread_id] = conn
                return conn

    def _create_connection(self):
        """Create a SQLite connection to the underlying database.

        Makes a new connection every time. If you need to configure the
        connection settings (e.g., add custom functions), override this
        method.
        """
        # Make a new connection. The `sqlite3` module can't use
        # bytestring paths here on Python 3, so we need to
        # provide a `str` using `py3_path`.
        conn = sqlite3.connect(
            py3_path(self.path),
            timeout=self.timeout,
            # enable mapping types defined in column names as "col [type]"
            # to sqlite converters
            detect_types=sqlite3.PARSE_COLNAMES
        )

        self.add_functions(conn)
        if self.supports_extensions:
            conn.enable_load_extension(True)

            # Load any extension that are already loaded for other connections.
            for path in self._extensions:
                conn.load_extension(path)

        # Access SELECT results like dictionaries.
        conn.row_factory = sqlite3.Row
        return conn

    def _close(self):
        """Close the all connections to the underlying SQLite database
        from all threads. This does not render the database object
        unusable; new connections can still be opened on demand.
        """
        with self._shared_map_lock:
            self._connections.clear()

    def add_functions(self, conn):
        def regexp(value, pattern):
            if isinstance(value, bytes):
                value = value.decode()
            return re.search(pattern, str(value)) is not None

        class GroupToJSON:
            """Re-implementation of the 'json_group_object' SQLite function.

            An aggregate function which accepts two values (key, val) and
            groups the corresponding column values into a single JSON object.

            a    b    c  -> GROUP BY c -> c, group_to_json(a, b)
            hi   bye  1                   1  {"hi":"bye","hey":"by"}
            hey  by   1

            It is found in the json1 extension which was not included in the
            standard SQLite installations until version 3.38.0 (2022-02-22).
            Therefore, to ensure support for older SQLite versions, we add our
            implementation.
            """

            def __init__(self):
                self.flex = {}

            def step(self, field, value):
                if field:
                    self.flex[field] = value

            def finalize(self):
                return json.dumps(self.flex)

        conn.create_function("regexp", 2, regexp)
        conn.create_function("unidecode", 1, unidecode)
        conn.create_aggregate("group_to_json", 2, GroupToJSON)

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

    def load_extension(self, path):
        """Load an SQLite extension into all open connections."""
        if not self.supports_extensions:
            raise ValueError(
                'this sqlite3 installation does not support extensions')

        self._extensions.append(path)

        # Load the extension into every open connection.
        for conn in self._connections.values():
            conn.load_extension(path)

    # Schema setup and migration.

    def _make_table(self, table, fields):
        """Set up the schema of the database. `fields` is a mapping
        from field names to `Type`s. Columns are added if necessary.
        """
        # Get current schema.
        with self.transaction() as tx:
            rows = tx.query('PRAGMA table_info(%s)' % table)
        current_fields = {row[1] for row in rows}

        field_names = set(fields.keys())
        if current_fields.issuperset(field_names):
            # Table exists and has all the required columns.
            return

        if not current_fields:
            # No table exists.
            columns = []
            for name, typ in fields.items():
                columns.append(f'{name} {typ.sql}')
            setup_sql = 'CREATE TABLE {} ({});\n'.format(table,
                                                         ', '.join(columns))

        else:
            # Table exists does not match the field set.
            setup_sql = ''
            for name, typ in fields.items():
                if name in current_fields:
                    continue
                setup_sql += 'ALTER TABLE {} ADD COLUMN {} {};\n'.format(
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

    @staticmethod
    def _get_fields(query):
        """Return a list of (field, fast) tuples.
        Nested queries are handled through recursion.
        """
        if hasattr(query, "subqueries"):
            return reduce(add, map(Database._get_fields, query.subqueries))
        if hasattr(query, "subquery"):
            return Database._get_fields(query.subquery)
        elif hasattr(query, "fields"):
            return [(f, True) for f in query.fields]
        elif hasattr(query, "field"):
            return [(query.field, query.fast), ]
        else:
            return []

    @staticmethod
    def _relation_join(model):
        """Given a model class, return a join between itself and the related
        table if the relation exists.
        For example for items and albums it would be
            items JOIN albums ON items.album_id == albums.id
        or
            albums JOIN items ON albums.id == items.album_id
        """
        relation = getattr(model, "_relation", None)
        if relation:
            return "{0} LEFT JOIN {1} ON {0}.{2} == {1}.{3}".format(
                model._table,
                model._relation._table,
                model._relation_id_field,
                model._relation._relation_id_field,
            )
        return model._table

    @staticmethod
    def print_query(sql, subvals):
        """If debugging, replace placeholders and print the query."""
        if not DEBUG:
            return
        topr = sql
        for val in subvals:
            topr = topr.replace("?", str(val), 1)
        print(topr)

    def _get_matching_ids(self, model, where, subvals):
        """Return ids of entities which match the given filter (`where` clause).
        This function is called only if we filter by at least one flexible
        attribute field.

        Since we cannot tell which entity the flexible attributes belong to
        (or even whether they exist), we must join the related entity and query
        both flexible attribute tables.

        Since these queries only return IDs of the entities _matching_
        the filter, they are performed very quickly, regardless of which table
        the queried fields belong to, or the size of the music library.

        Attempts to achieve this using a single query resulted in significantly
        slower performance, since the main query contains both GROUP BY
        and ORDER BY clauses, and because the query asks for all data.
        """

        id_field = f"{model._table}.id"
        join_tmpl = "LEFT JOIN {} ON {} = entity_id"
        joins = [join_tmpl.format(model._flex_table, id_field)]

        _from = self._relation_join(model)
        if _from != model._table:
            joins.append(join_tmpl.format(model._relation._flex_table,
                                          f"{model._relation._table}.id"))

        ids = set()
        with self.transaction() as tx:
            for join in joins:
                sql = f"SELECT {id_field} FROM {_from} {join} WHERE {where}"
                self.print_query(sql, subvals)
                ids.update(chain.from_iterable(tx.query(sql, subvals)))

        return ids

    def _fetch(self, model_cls, query=None, sort=None, limit=None):
        """Fetch the objects of type `model_cls` matching the given
        query. `query` is a Query object, or None (to fetch everything).
        `sort` is a `Sort` object while `limit` is an integer or None.
        """
        sort = sort or NullSort()
        order_by = sort.order_clause()

        query = query or TrueQuery()
        where, subvals = query.clause()

        fields = defaultdict(set)
        for field, fast in self._get_fields(query):
            fields[fast].add(field)

        flex_fields, model_fields = fields[False], fields[True]
        relation_fields = model_fields - set(model_cls._fields)

        table = model_cls._table
        _from = table
        # select all fields from the queried entity
        select_fields = [f"{table}.*"]
        if flex_fields:
            # prefetch IDs of entities that match the filter which includes
            # flexible attributes
            ids = self._get_matching_ids(model_cls, where or 1, subvals)
            where = f"{table}.id IN ({', '.join(map(str, ids))})"
            subvals = []
        elif relation_fields:
            # otherwise, if we are filtering by a related field, join
            # the related entity table, and return the required fields,
            # such as `items.path`
            _from = self._relation_join(model_cls)
            select_fields += relation_fields

        sql = f"""
        SELECT
            {", ".join(select_fields)},
            group_to_json(key, value) AS "flex_attrs [json_str]"
        FROM {_from}
        LEFT JOIN (
            SELECT entity_id, key, value
            FROM {model_cls._flex_table}
        ) ON {table}.id = entity_id
        WHERE {where or 1}
        GROUP BY {table}.id
        """
        if order_by:
            # a field name in `order_by`, say `album`, would be ambiguous
            # in the `sql` query since it may exist on both (joined) tables
            # in `_from`, causing sqlite3.OperationalError.
            # Since we know that `sql` selects unique fields, we wrap it in
            # a subquery.
            # This is also good for performance, since ordering is applied
            # to the final (filtered) list of entities, staying away from the
            # joins and the GROUP BY clause.
            sql = f"SELECT * FROM ({sql}) ORDER BY {order_by}"
        if limit:
            # use the limit at the end ensuring that we limit sorted entities
            sql += f"\nLIMIT {limit}"

        self.print_query(sql, subvals)

        with self.transaction() as tx:
            rows = tx.query(sql, subvals)

        return Results(
            model_cls, rows, self,
            sort if sort.is_slow() else None,  # Slow sort component.
        )

    def _get(self, model_cls, id):
        """Get a Model object by its id or None if the id does not
        exist.
        """
        return self._fetch(model_cls, MatchQuery('id', id)).get()
