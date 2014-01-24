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


class Type(object):
    """An object encapsulating the type of a model field. Includes
    information about how to store the value in the database, query,
    format, and parse a given field.
    """
    def __init__(self, sql, query, format_func=None):
        """Create a type. `sql` is the SQLite column type for the value.
        `query` is the `Query` subclass to be used when querying the
        field. `format_func` is a function that transforms values of
        this type to a human-readable Unicode string. If `format_func`
        is not provided, the subclass must override `format` to provide
        the functionality.
        """
        self.sql = sql
        self.query = query
        self.format_func = format_func

    def format(self, value):
        """Given a value of this type, produce a Unicode string
        representing the value. This is used in template evaluation.
        """
        return self.format_func(value)


# Common singleton types.

ID_TYPE = Type('INTEGER PRIMARY KEY', query.NumericQuery, unicode)
INT_TYPE = Type('INTEGER', query.NumericQuery,
                lambda n: unicode(n or 0))
FLOAT_TYPE = Type('REAL', query.NumericQuery,
                  lambda n: u'{0:.1f}'.format(n or 0.0))
STRING_TYPE = Type('TEXT', query.SubstringQuery,
                   lambda s: s or u'')
BOOL_TYPE = Type('INTEGER', query.BooleanQuery,
                 lambda b: unicode(bool(b)))



# Parameterized types.


class PaddedInt(Type):
    """An integer field that is formatted with a given number of digits,
    padded with zeroes.
    """
    def __init__(self, digits):
        self.digits = digits
        super(PaddedInt, self).__init__('INTEGER', query.NumericQuery)

    def format(self, value):
        return u'{0:0{1}d}'.format(value or 0, self.digits)


class ScaledInt(Type):
    """An integer whose formatting operation scales the number by a
    constant and adds a suffix. Good for units with large magnitudes.
    """
    def __init__(self, unit, suffix=u''):
        self.unit = unit
        self.suffix = suffix
        super(ScaledInt, self).__init__('INTEGER', query.NumericQuery)

    def format(self, value):
        return u'{0}{1}'.format((value or 0) // self.unit, self.suffix)
