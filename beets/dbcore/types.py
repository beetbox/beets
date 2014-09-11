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

    default = u''
    """The value to be exposed when the underlying value is None.
    """

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
        return value

    def to_sql(self, value):
        return value

    def from_sql(self, value):
        return value


# Reusable types.

class Integer(Type):
    """A basic integer type.
    """
    sql = u'INTEGER'
    query = query.NumericQuery
    default = 0

    def format(self, value):
        return unicode(value)

    def parse(self, string):
        return int(string)


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
    default = None

    def __init__(self, primary=True):
        if primary:
            self.sql = u'INTEGER PRIMARY KEY'


class Float(Type):
    """A basic floating-point type.
    """
    sql = u'REAL'
    query = query.NumericQuery
    default = 0.0

    def format(self, value):
        return u'{0:.1f}'.format(value)

    def normalize(self, value):
        return float(value)


class NullFloat(Float):
    default = None


class String(Type):
    """A Unicode string type.
    """
    sql = u'TEXT'
    query = query.SubstringQuery
    default = u''

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
    null = False

    def format(self, value):
        return unicode(bool(value))

    def normalize(self, value):
        return bool(value)

    def parse(self, string):
        return str2bool(string)


class Bytes(Type):

    sql = u'BLOB'
    default = bytearray()

    def format(self, value):
        return value.decode('utf-8')

    def normalize(self, value):
        return bytearray(value)

    def parse(self, string):
        return bytearray(string, 'utf-8')

    def from_sql(self, sql_value):
        # sql_value is a buffer
        return bytearray(sql_value)

    def to_sql(self, local_value):
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
