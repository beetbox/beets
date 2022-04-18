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

"""Representation of type information for DBCore model fields.
"""

from . import query
from beets.util import str2bool


# Abstract base.

class Type:
    """An object encapsulating the type of a model field. Includes
    information about how to store, query, format, and parse a given
    field.
    """

    sql = 'TEXT'
    """The SQLite column type for the value.
    """

    query = query.SubstringQuery
    """The `Query` subclass to be used when querying the field.
    """

    model_type = str
    """The Python type that is used to represent the value in the model.

    The model is guaranteed to return a value of this type if the field
    is accessed.  To this end, the constructor is used by the `normalize`
    and `from_sql` methods and the `default` property.
    """

    @property
    def null(self):
        """The value to be exposed when the underlying value is None.
        """
        return self.model_type()

    def format(self, value):
        """Given a value of this type, produce a Unicode string
        representing the value. This is used in template evaluation.
        """
        if value is None:
            value = self.null
        # `self.null` might be `None`
        if value is None:
            value = ''
        if isinstance(value, bytes):
            value = value.decode('utf-8', 'ignore')

        return str(value)

    def parse(self, string):
        """Parse a (possibly human-written) string and return the
        indicated value of this type.
        """
        try:
            return self.model_type(string)
        except ValueError:
            return self.null

    def normalize(self, value):
        """Given a value that will be assigned into a field of this
        type, normalize the value to have the appropriate type. This
        base implementation only reinterprets `None`.
        """
        if value is None:
            return self.null
        else:
            # TODO This should eventually be replaced by
            # `self.model_type(value)`
            return value

    def from_sql(self, sql_value):
        """Receives the value stored in the SQL backend and return the
        value to be stored in the model.

        For fixed fields the type of `value` is determined by the column
        type affinity given in the `sql` property and the SQL to Python
        mapping of the database adapter. For more information see:
        https://www.sqlite.org/datatype3.html
        https://docs.python.org/2/library/sqlite3.html#sqlite-and-python-types

        Flexible fields have the type affinity `TEXT`. This means the
        `sql_value` is either a `memoryview` or a `unicode` object`
        and the method must handle these in addition.
        """
        if isinstance(sql_value, memoryview):
            sql_value = bytes(sql_value).decode('utf-8', 'ignore')
        if isinstance(sql_value, str):
            return self.parse(sql_value)
        else:
            return self.normalize(sql_value)

    def to_sql(self, model_value):
        """Convert a value as stored in the model object to a value used
        by the database adapter.
        """
        return model_value


# Reusable types.

class Default(Type):
    null = None


class Integer(Type):
    """A basic integer type.
    """
    sql = 'INTEGER'
    query = query.NumericQuery
    model_type = int

    def normalize(self, value):
        try:
            return self.model_type(round(float(value)))
        except ValueError:
            return self.null
        except TypeError:
            return self.null


class PaddedInt(Integer):
    """An integer field that is formatted with a given number of digits,
    padded with zeroes.
    """
    def __init__(self, digits):
        self.digits = digits

    def format(self, value):
        return '{0:0{1}d}'.format(value or 0, self.digits)


class NullPaddedInt(PaddedInt):
    """Same as `PaddedInt`, but does not normalize `None` to `0.0`.
    """
    null = None


class ScaledInt(Integer):
    """An integer whose formatting operation scales the number by a
    constant and adds a suffix. Good for units with large magnitudes.
    """
    def __init__(self, unit, suffix=''):
        self.unit = unit
        self.suffix = suffix

    def format(self, value):
        return '{}{}'.format((value or 0) // self.unit, self.suffix)


class Id(Integer):
    """An integer used as the row id or a foreign key in a SQLite table.
    This type is nullable: None values are not translated to zero.
    """
    null = None

    def __init__(self, primary=True):
        if primary:
            self.sql = 'INTEGER PRIMARY KEY'


class Float(Type):
    """A basic floating-point type. The `digits` parameter specifies how
    many decimal places to use in the human-readable representation.
    """
    sql = 'REAL'
    query = query.NumericQuery
    model_type = float

    def __init__(self, digits=1):
        self.digits = digits

    def format(self, value):
        return '{0:.{1}f}'.format(value or 0, self.digits)


class NullFloat(Float):
    """Same as `Float`, but does not normalize `None` to `0.0`.
    """
    null = None


class String(Type):
    """A Unicode string type.
    """
    sql = 'TEXT'
    query = query.SubstringQuery

    def normalize(self, value):
        if value is None:
            return self.null
        else:
            return self.model_type(value)


class Boolean(Type):
    """A boolean type.
    """
    sql = 'INTEGER'
    query = query.BooleanQuery
    model_type = bool

    def format(self, value):
        return str(bool(value))

    def parse(self, string):
        return str2bool(string)


# Shared instances of common types.
DEFAULT = Default()
INTEGER = Integer()
PRIMARY_ID = Id(True)
FOREIGN_ID = Id(False)
FLOAT = Float()
NULL_FLOAT = NullFloat()
STRING = String()
BOOLEAN = Boolean()
