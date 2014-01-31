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

"""The Query type hierarchy for DBCore.
"""
import re
from beets import util


class Query(object):
    """An abstract class representing a query into the item database.
    """
    def clause(self):
        """Generate an SQLite expression implementing the query.
        Return a clause string, a sequence of substitution values for
        the clause, and a Query object representing the "remainder"
        Returns (clause, subvals) where clause is a valid sqlite
        WHERE clause implementing the query and subvals is a list of
        items to be substituted for ?s in the clause.
        """
        return None, ()

    def match(self, item):
        """Check whether this query matches a given Item. Can be used to
        perform queries on arbitrary sets of Items.
        """
        raise NotImplementedError


class FieldQuery(Query):
    """An abstract query that searches in a specific field for a
    pattern. Subclasses must provide a `value_match` class method, which
    determines whether a certain pattern string matches a certain value
    string. Subclasses may also provide `col_clause` to implement the
    same matching functionality in SQLite.
    """
    def __init__(self, field, pattern, fast=True):
        self.field = field
        self.pattern = pattern
        self.fast = fast

    def col_clause(self):
        return None, ()

    def clause(self):
        if self.fast:
            return self.col_clause()
        else:
            # Matching a flexattr. This is a slow query.
            return None, ()

    @classmethod
    def value_match(cls, pattern, value):
        """Determine whether the value matches the pattern. Both
        arguments are strings.
        """
        raise NotImplementedError()

    def match(self, item):
        return self.value_match(self.pattern, item.get(self.field))


class MatchQuery(FieldQuery):
    """A query that looks for exact matches in an item field."""
    def col_clause(self):
        return self.field + " = ?", [self.pattern]

    @classmethod
    def value_match(cls, pattern, value):
        return pattern == value


class StringFieldQuery(FieldQuery):
    """A FieldQuery that converts values to strings before matching
    them.
    """
    @classmethod
    def value_match(cls, pattern, value):
        """Determine whether the value matches the pattern. The value
        may have any type.
        """
        return cls.string_match(pattern, util.as_string(value))

    @classmethod
    def string_match(cls, pattern, value):
        """Determine whether the value matches the pattern. Both
        arguments are strings. Subclasses implement this method.
        """
        raise NotImplementedError()


class SubstringQuery(StringFieldQuery):
    """A query that matches a substring in a specific item field."""
    def col_clause(self):
        search = '%' + (self.pattern.replace('\\','\\\\').replace('%','\\%')
                            .replace('_','\\_')) + '%'
        clause = self.field + " like ? escape '\\'"
        subvals = [search]
        return clause, subvals

    @classmethod
    def string_match(cls, pattern, value):
        return pattern.lower() in value.lower()


class RegexpQuery(StringFieldQuery):
    """A query that matches a regular expression in a specific item
    field.
    """
    @classmethod
    def string_match(cls, pattern, value):
        try:
            res = re.search(pattern, value)
        except re.error:
            # Invalid regular expression.
            return False
        return res is not None


class BooleanQuery(MatchQuery):
    """Matches a boolean field. Pattern should either be a boolean or a
    string reflecting a boolean.
    """
    def __init__(self, field, pattern, fast=True):
        super(BooleanQuery, self).__init__(field, pattern, fast)
        if isinstance(pattern, basestring):
            self.pattern = util.str2bool(pattern)
        self.pattern = int(self.pattern)


class BytesQuery(MatchQuery):
    """Match a raw bytes field (i.e., a path). This is a necessary hack
    to work around the `sqlite3` module's desire to treat `str` and
    `unicode` equivalently in Python 2. Always use this query instead of
    `MatchQuery` when matching on BLOB values.
    """
    def __init__(self, field, pattern):
        super(BytesQuery, self).__init__(field, pattern)

        # Use a buffer representation of the pattern for SQLite
        # matching. This instructs SQLite to treat the blob as binary
        # rather than encoded Unicode.
        if isinstance(self.pattern, bytes):
            self.buf_pattern = buffer(self.pattern)
        elif isinstance(self.pattern, buffer):
            self.buf_pattern = self.pattern
            self.pattern = bytes(self.pattern)

    def col_clause(self):
        return self.field + " = ?", [self.buf_pattern]


class NumericQuery(FieldQuery):
    """Matches numeric fields. A syntax using Ruby-style range ellipses
    (``..``) lets users specify one- or two-sided ranges. For example,
    ``year:2001..`` finds music released since the turn of the century.
    """
    def _convert(self, s):
        """Convert a string to a numeric type (float or int). If the
        string cannot be converted, return None.
        """
        # This is really just a bit of fun premature optimization.
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return None

    def __init__(self, field, pattern, fast=True):
        super(NumericQuery, self).__init__(field, pattern, fast)

        parts = pattern.split('..', 1)
        if len(parts) == 1:
            # No range.
            self.point = self._convert(parts[0])
            self.rangemin = None
            self.rangemax = None
        else:
            # One- or two-sided range.
            self.point = None
            self.rangemin = self._convert(parts[0])
            self.rangemax = self._convert(parts[1])

    def match(self, item):
        value = getattr(item, self.field)
        if isinstance(value, basestring):
            value = self._convert(value)

        if self.point is not None:
            return value == self.point
        else:
            if self.rangemin is not None and value < self.rangemin:
                return False
            if self.rangemax is not None and value > self.rangemax:
                return False
            return True

    def col_clause(self):
        if self.point is not None:
            return self.field + '=?', (self.point,)
        else:
            if self.rangemin is not None and self.rangemax is not None:
                return (u'{0} >= ? AND {0} <= ?'.format(self.field),
                        (self.rangemin, self.rangemax))
            elif self.rangemin is not None:
                return u'{0} >= ?'.format(self.field), (self.rangemin,)
            elif self.rangemax is not None:
                return u'{0} <= ?'.format(self.field), (self.rangemax,)
            else:
                return '1'


class CollectionQuery(Query):
    """An abstract query class that aggregates other queries. Can be
    indexed like a list to access the sub-queries.
    """
    def __init__(self, subqueries=()):
        self.subqueries = subqueries

    # Act like a sequence.
    def __len__(self):
        return len(self.subqueries)
    def __getitem__(self, key):
        return self.subqueries[key]
    def __iter__(self):
        return iter(self.subqueries)
    def __contains__(self, item):
        return item in self.subqueries

    def clause_with_joiner(self, joiner):
        """Returns a clause created by joining together the clauses of
        all subqueries with the string joiner (padded by spaces).
        """
        clause_parts = []
        subvals = []
        for subq in self.subqueries:
            subq_clause, subq_subvals = subq.clause()
            if not subq_clause:
                # Fall back to slow query.
                return None, ()
            clause_parts.append('(' + subq_clause + ')')
            subvals += subq_subvals
        clause = (' ' + joiner + ' ').join(clause_parts)
        return clause, subvals


class AnyFieldQuery(CollectionQuery):
    """A query that matches if a given FieldQuery subclass matches in
    any field. The individual field query class is provided to the
    constructor.
    """
    def __init__(self, pattern, fields, cls):
        self.pattern = pattern
        self.fields = fields
        self.query_class = cls

        subqueries = []
        for field in self.fields:
            subqueries.append(cls(field, pattern, True))
        super(AnyFieldQuery, self).__init__(subqueries)

    def clause(self):
        return self.clause_with_joiner('or')

    def match(self, item):
        for subq in self.subqueries:
            if subq.match(item):
                return True
        return False


class MutableCollectionQuery(CollectionQuery):
    """A collection query whose subqueries may be modified after the
    query is initialized.
    """
    def __setitem__(self, key, value):
        self.subqueries[key] = value

    def __delitem__(self, key):
        del self.subqueries[key]


class AndQuery(MutableCollectionQuery):
    """A conjunction of a list of other queries."""
    def clause(self):
        return self.clause_with_joiner('and')

    def match(self, item):
        return all([q.match(item) for q in self.subqueries])


class TrueQuery(Query):
    """A query that always matches."""
    def clause(self):
        return '1', ()

    def match(self, item):
        return True


class FalseQuery(Query):
    """A query that never matches."""
    def clause(self):
        return '0', ()

    def match(self, item):
        return False
