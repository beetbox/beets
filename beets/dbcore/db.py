# -*- coding: utf-8 -*-
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
from __future__ import division, absolute_import, print_function

import time
import os
import re
from collections import defaultdict
import threading
import sqlite3
import contextlib

import beets
from beets.util import functemplate
from beets.util import py3_path
from beets.dbcore import types
from .query import MatchQuery, NullSort, TrueQuery
import six
if six.PY2:
    from collections import Mapping
else:
    from collections.abc import Mapping


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

    If `for_path` is true, all path separators in the formatted values
    are replaced.
    """

    def __init__(self, model, for_path=False):
        self.for_path = for_path
        self.model = model
        self.model_keys = model.keys(True)

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
        return super(FormattedMapping, self).get(key, default)

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


class LazyConvertDict(object):
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

class Model(object):
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
            raise ValueError(
                u'{0} has no database'.format(type(self).__name__)
            )
        if need_id and not self.id:
            raise ValueError(u'{0} has no id'.format(type(self).__name__))

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

    def __getitem__(self, key):
        """Get the value for a field. Raise a KeyError if the field is
        not available.
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
        else:
            raise KeyError(key)

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
            raise KeyError(u'computed field {0} cannot be deleted'.format(key))
        else:
            raise KeyError(u'no such field {0}'.format(key))

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
            raise AttributeError(u'model has no attribute {0!r}'.format(key))
        else:
            try:
                return self[key]
            except KeyError:
                raise AttributeError(u'no such field {0!r}'.format(key))

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
        assert stored_obj is not None, u"object {0} not in DB".format(self.id)
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

    _formatter = FormattedMapping

    def formatted(self, for_path=False):
        """Get a mapping containing all values on this object formatted
        as human-readable unicode strings.
        """
        return self._formatter(self, for_path)

    def evaluate_template(self, template, for_path=False):
        """Evaluate a template (a string or a `Template` object) using
        the object's fields. If `for_path` is true, then no new path
        separators will be added to the template.
        """
        # Perform substitution.
        if isinstance(template, six.string_types):
            template = functemplate.template(template)
        return template.substitute(self.formatted(for_path),
                                   self._template_funcs())

    # Parsing.

    @classmethod
    def _parse(cls, key, string):
        """Parse a string as a value for the given key.
        """
        if not isinstance(string, six.string_types):
            raise TypeError(u"_parse() argument must be a string")

        return cls._type(key).parse(string)

    def set_parse(self, key, string):
        """Set the object's key to a value represented by a string.
        """
        self[key] = self._parse(key, string)


# Database controller and supporting interfaces.

class Results(object):
    """An item query result set. Iterating over the collection lazily
    constructs LibModel objects that reflect database rows.
    """
    def __init__(self, model_class, rows, db, flex_rows,
                 query=None, sort=None):
        """Create a result set that will construct objects of type
        `model_class`.

        `model_class` is a subclass of `LibModel` that will be
        constructed. `rows` is a query result: a list of mappings. The
        new objects will be associated with the database `db`.

        If `query` is provided, it is used as a predicate to filter the
        results for a "slow query" that cannot be evaluated by the
        database directly. If `sort` is provided, it is used to sort the
        full list of results before returning. This means it is a "slow
        sort" and all objects must be built before returning the first
        one.
        """
        self.model_class = model_class
        self.rows = rows
        self.db = db
        self.query = query
        self.sort = sort
        self.flex_rows = flex_rows

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

        # Index flexible attributes by the item ID, so we have easier access
        flex_attrs = self._get_indexed_flex_attrs()

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
                    obj = self._make_model(row, flex_attrs.get(row['id'], {}))
                    # If there is a slow-query predicate, ensurer that the
                    # object passes it.
                    if not self.query or self.query.match(obj):
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

    def _get_indexed_flex_attrs(self):
        """ Index flexible attributes by the entity id they belong to
        """
        flex_values = dict()
        for row in self.flex_rows:
            if row['entity_id'] not in flex_values:
                flex_values[row['entity_id']] = dict()

            flex_values[row['entity_id']][row['key']] = row['value']

        return flex_values

    def _make_model(self, row, flex_values={}):
        """ Create a Model object for the given row
        """
        cols = dict(row)
        values = dict((k, v) for (k, v) in cols.items()
                      if not k[:4] == 'flex')

        # Construct the Python object
        obj = self.model_class._awaken(self.db, values, flex_values)
        return obj

    def __len__(self):
        """Get the number of matching objects.
        """
        if not self._rows:
            # Fully materialized. Just count the objects.
            return len(self._objects)

        elif self.query:
            # A slow query. Fall back to testing every object.
            count = 0
            for obj in self:
                count += 1
            return count

        else:
            # A fast query. Just count the rows.
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
            raise IndexError(u'result index {0} out of range'.format(n))

    def get(self):
        """Return the first matching object, or None if no objects
        match.
        """
        it = iter(self)
        try:
            return next(it)
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
        try:
            cursor = self.db._connection().execute(statement, subvals)
            return cursor.lastrowid
        except sqlite3.OperationalError as e:
            # In two specific cases, SQLite reports an error while accessing
            # the underlying database file. We surface these exceptions as
            # DBAccessError so the application can abort.
            if e.args[0] in ("attempt to write a readonly database",
                             "unable to open database file"):
                raise DBAccessError(e.args[0])
            else:
                raise

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

    supports_extensions = hasattr(sqlite3.Connection, 'enable_load_extension')
    """Whether or not the current version of SQLite supports extensions"""

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
            py3_path(self.path), timeout=self.timeout
        )

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

    def _fetch(self, model_cls, query=None, sort=None):
        """Fetch the objects of type `model_cls` matching the given
        query. The query may be given as a string, string sequence, a
        Query object, or None (to fetch everything). `sort` is an
        `Sort` object.
        """
        query = query or TrueQuery()  # A null query.
        sort = sort or NullSort()  # Unsorted.
        where, subvals = query.clause()
        order_by = sort.order_clause()

        sql = ("SELECT * FROM {0} WHERE {1} {2}").format(
            model_cls._table,
            where or '1',
            "ORDER BY {0}".format(order_by) if order_by else '',
        )

        # Fetch flexible attributes for items matching the main query.
        # Doing the per-item filtering in python is faster than issuing
        # one query per item to sqlite.
        flex_sql = ("""
            SELECT * FROM {0} WHERE entity_id IN
                (SELECT id FROM {1} WHERE {2});
            """.format(
                model_cls._flex_table,
                model_cls._table,
                where or '1',
            )
        )

        with self.transaction() as tx:
            rows = tx.query(sql, subvals)
            flex_rows = tx.query(flex_sql, subvals)

        return Results(
            model_cls, rows, self, flex_rows,
            None if where else query,  # Slow query component.
            sort if sort.is_slow() else None,  # Slow sort component.
        )

    def _get(self, model_cls, id):
        """Get a Model object by its id or None if the id does not
        exist.
        """
        return self._fetch(model_cls, MatchQuery('id', id)).get()
