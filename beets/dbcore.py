import time
import os

import beets
from beets.util.functemplate import Template


# Path element formatting for templating.
# FIXME remove this once we have type-based formatting.
def format_for_path(value, key=None):
    """Sanitize the value for inclusion in a path: replace separators
    with _, etc. Doesn't guarantee that the whole path will be valid;
    you should still call `util.sanitize_path` on the complete path.
    """
    if isinstance(value, basestring):
        if isinstance(value, str):
            value = value.decode('utf8', 'ignore')
    elif key in ('track', 'tracktotal', 'disc', 'disctotal'):
        # Pad indices with zeros.
        value = u'%02i' % (value or 0)
    elif key == 'year':
        value = u'%04i' % (value or 0)
    elif key in ('month', 'day'):
        value = u'%02i' % (value or 0)
    elif key == 'bitrate':
        # Bitrate gets formatted as kbps.
        value = u'%ikbps' % ((value or 0) // 1000)
    elif key == 'samplerate':
        # Sample rate formatted as kHz.
        value = u'%ikHz' % ((value or 0) // 1000)
    elif key in ('added', 'mtime'):
        # Times are formatted to be human-readable.
        value = time.strftime(beets.config['time_format'].get(unicode),
                              time.localtime(value))
        value = unicode(value)
    elif value is None:
        value = u''
    else:
        value = unicode(value)

    return value


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

    _fields = ()
    """The available "fixed" fields on this type.
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

    def __init__(self, lib=None, **values):
        """Create a new object with an optional Library association and
        initial field values.
        """
        self._lib = lib
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
        has a reference to a library (`_lib`) and an id. A ValueError
        exception is raised otherwise.
        """
        if not self._lib:
            raise ValueError('{0} has no library'.format(type(self).__name__))
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
                assignments += key + '=?,'
                value = self[key]
                # Wrap path strings in buffers so they get stored
                # "in the raw".
                if key in self._bytes_keys and isinstance(value, str):
                    value = buffer(value)
                subvars.append(value)
        assignments = assignments[:-1]  # Knock off last ,

        with self._lib.transaction() as tx:
            # Main table update.
            if assignments:
                query = 'UPDATE {0} SET {1} WHERE id=?'.format(
                    self._table, assignments
                )
                subvars.append(self.id)
                tx.mutate(query, subvars)

            # Flexible attributes.
            for key, value in self._values_flex.items():
                if key in self._dirty:
                    tx.mutate(
                        'INSERT INTO {0} '
                        '(entity_id, key, value) '
                        'VALUES (?, ?, ?);'.format(self._flex_table),
                        (self.id, key, value),
                    )

        self.clear_dirty()

    def load(self):
        """Refresh the object's metadata from the library database.
        """
        self._check_db()
        stored_obj = self._lib._get(type(self), self.id)
        self.update(dict(stored_obj))
        self.clear_dirty()

    def remove(self):
        """Remove the object's associated rows from the database.
        """
        self._check_db()
        with self._lib.transaction() as tx:
            tx.mutate(
                'DELETE FROM {0} WHERE id=?'.format(self._table),
                (self.id,)
            )
            tx.mutate(
                'DELETE FROM {0} WHERE entity_id=?'.format(self._flex_table),
                (self.id,)
            )

    def add(self, lib=None):
        """Add the object to the library database. This object must be
        associated with a library; you can provide one via the `lib`
        parameter or use the currently associated library.

        The object's `id` and `added` fields are set along with any
        current field values.
        """
        if lib:
            self._lib = lib
        self._check_db(False)

        with self._lib.transaction() as tx:
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

    def _get_formatted(self, key, for_path=False):
        """Get a field value formatted as a string (`unicode` object)
        for display to the user. If `for_path` is true, then the value
        will be sanitized for inclusion in a pathname (i.e., path
        separators will be removed from the value).
        """
        value = self.get(key)

        # FIXME this will get replaced with more sophisticated
        # (type-based) formatting logic.
        value = format_for_path(value, key)

        if for_path:
            sep_repl = beets.config['path_sep_replace'].get(unicode)
            for sep in (os.path.sep, os.path.altsep):
                if sep:
                    value = value.replace(sep, sep_repl)

        return value

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
