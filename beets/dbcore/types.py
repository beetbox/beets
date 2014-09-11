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

"""Representation of type information for DBCore model fields.
"""
from . import query
from beets.util import str2bool


# Abstract base.

class Type(object):
    """An object encapsulating the type of a model field. Includes
    information about how to store, query, format, and parse a given
    field.
    """

    sql = u'TEXT'
    """The SQLite column type for the value.
    """

    query = query.SubstringQuery
    """The `Query` subclass to be used when querying the field.
    """

    model_type = unicode
    """The python type that is used to represent the value in the model.

    The model is guaranteed to return a value of this type if the field
    is accessed.  To this end, the constructor is used by the `normalize`
    and `from_sql` methods and the `default` property.
    """

    @property
    def default(self):
        """The value to be exposed when the underlying value is None.
        """
        return self.model_type()

    def format(self, value):
        """Given a value of this type, produce a Unicode string
        representing the value. This is used in template evaluation.
        """
        return unicode(value)

    def parse(self, string):
        """Parse a human-written unicode object and return the
        indicated value of this type.
        """
        return self.normalize(string)

    def normalize(self, value):
        """Given a value that will be assigned into a field of this
        type, normalize the value to have the appropriate type.
        """
        return self.model_type(value)

    def to_sql(self, value):
        return value

    def from_sql(self, value):
        """Receives the value stored in the SQL backend and return the
        value to be stored in the model.

        For fixed fields the type of `value` is determined by the column
        type given in the `sql` property and the SQL to Python mapping
        given here:
        https://docs.python.org/2/library/sqlite3.html#sqlite-and-python-types

        For flexible field the value is a unicode object. The method
        must therefore be able to parse them.
        """
        return self.model_type(value)


# Reusable types.

class Integer(Type):
    """A basic integer type.
    """
    sql = u'INTEGER'
    query = query.NumericQuery
    model_type = int


class PaddedInt(Integer):
    """An integer field that is formatted with a given number of digits,
    padded with zeroes.
    """
    def __init__(self, digits):
        self.digits = digits

    def format(self, value):
        return u'{0:0{1}d}'.format(value, self.digits)


class ScaledInt(Integer):
    """An integer whose formatting operation scales the number by a
    constant and adds a suffix. Good for units with large magnitudes.
    """
    def __init__(self, unit, suffix=u''):
        self.unit = unit
        self.suffix = suffix

    def format(self, value):
        return u'{0}{1}'.format(value // self.unit, self.suffix)


class Id(Integer):
    """An integer used as the row id or a foreign key in a SQLite table.
    This type is nullable: None values are not translated to zero.
    """
    # TODO we should be able to remove the default value
    default = None

    def __init__(self, primary=True):
        if primary:
            self.sql = u'INTEGER PRIMARY KEY'


class Float(Type):
    """A basic floating-point type.
    """
    sql = u'REAL'
    query = query.NumericQuery
    model_type = float

    def format(self, value):
        return u'{0:.1f}'.format(value)


# TODO we should be able to remove this type
class NullFloat(Float):
    default = None


class String(Type):
    """A Unicode string type.
    """
    sql = u'TEXT'
    query = query.SubstringQuery

    def normalize(self, value):
        if isinstance(value, unicode):
            return value
        else:
            return value.decode('utf-8')


class Boolean(Type):
    """A boolean type.
    """
    sql = u'INTEGER'
    query = query.BooleanQuery
    model_type = bool

    def parse(self, string):
        return str2bool(string)

    def from_sql(self, value):
        if isinstance(value, unicode):
            return str2bool(value)
        else:
            return bool(value)


class Bytes(Type):

    sql = u'BLOB'
    model_type = bytearray

    def format(self, value):
        return value.decode('utf-8')

    def parse(self, string):
        return bytearray(string, 'utf-8')

    def from_sql(self, sql_value):
        if isinstance(sql_value, unicode):
            sql_value = sql_value.encode('utf-8')
        return self.model_type(sql_value)

    def to_sql(self, local_value):
        # local_value is a buffer
        return buffer(local_value)


# Shared instances of common types.
BASE_TYPE = Type()
INTEGER = Integer()
PRIMARY_ID = Id(True)
FOREIGN_ID = Id(False)
FLOAT = Float()
NULL_FLOAT = NullFloat()
STRING = String()
BOOLEAN = Boolean()
