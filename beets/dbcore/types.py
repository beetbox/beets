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
    information about how to store the value in the database, query,
    format, and parse a given field.
    """

    sql = None
    """The SQLite column type for the value.
    """

    query = None
    """The `Query` subclass to be used when querying the field.
    """

    def format(self, value):
        """Given a value of this type, produce a Unicode string
        representing the value. This is used in template evaluation.
        """
        raise NotImplementedError()

    def parse(self, string):
        """Parse a (possibly human-written) string and return the
        indicated value of this type.
        """
        raise NotImplementedError()



# Reusable types.


class Integer(Type):
    """A basic integer type.
    """
    sql = u'INTEGER'
    query = query.NumericQuery

    def format(self, value):
        return unicode(value or 0)

    def parse(self, string):
        try:
            return int(string)
        except ValueError:
            return 0


class PaddedInt(Integer):
    """An integer field that is formatted with a given number of digits,
    padded with zeroes.
    """
    def __init__(self, digits):
        self.digits = digits

    def format(self, value):
        return u'{0:0{1}d}'.format(value or 0, self.digits)


class ScaledInt(Integer):
    """An integer whose formatting operation scales the number by a
    constant and adds a suffix. Good for units with large magnitudes.
    """
    def __init__(self, unit, suffix=u''):
        self.unit = unit
        self.suffix = suffix

    def format(self, value):
        return u'{0}{1}'.format((value or 0) // self.unit, self.suffix)


class Id(Integer):
    """An integer used as the row key for a SQLite table.
    """
    sql = u'INTEGER PRIMARY KEY'


class Float(Type):
    """A basic floating-point type.
    """
    sql = u'REAL'
    query = query.NumericQuery

    def format(self, value):
        return u'{0:.1f}'.format(value or 0.0)

    def parse(self, string):
        try:
            return float(string)
        except ValueError:
            return 0.0


class String(Type):
    """A Unicode string type.
    """
    sql = u'TEXT'
    query = query.SubstringQuery

    def format(self, value):
        return unicode(value) if value else u''

    def parse(self, string):
        return string


class Boolean(Type):
    """A boolean type.
    """
    sql = u'INTEGER'
    query = query.BooleanQuery

    def format(self, value):
        return unicode(bool(value))

    def parse(self, string):
        return str2bool(string)
