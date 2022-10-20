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

# The file is primarily used for having all the database related
# exceptions in a single place for better modular flow. Exceptions
# are expected to have their own individual namespace for clarity.

class DBAccessError(Exception):
    """The SQLite database became inaccessible.

    This can happen when trying to read or write the database when, for
    example, the database file is deleted or otherwise disappears. There
    is probably no way to recover from this error.
    """
    pass


class ParsingError(ValueError):
    """Abstract class for any unparseable user-requested album/query
    specification.
    """
    pass


class InvalidQueryError(ParsingError):
    """Represent any kind of invalid query.

    The query should be a unicode string or a list, which will be space-joined.
    """

    def __init__(self, query, explanation):
        if isinstance(query, list):
            query = " ".join(query)
        message = f"'{query}': {explanation}"
        super().__init__(message)


class InvalidQueryArgumentValueError(ParsingError):
    """Represent a query argument that could not be converted as expected.

    It exists to be caught in upper stack levels so a meaningful (i.e. with the
    query) InvalidQueryError can be raised.
    """

    def __init__(self, what, expected, detail=None):
        message = f"'{what}' is not {expected}"
        if detail is not None:
            message = f"{message}: {detail}"
        super().__init__(message)
