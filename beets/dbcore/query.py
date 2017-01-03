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

"""The Query type hierarchy for DBCore.
"""
from __future__ import division, absolute_import, print_function

import re
from operator import mul
from beets import util
from datetime import datetime, timedelta
import unicodedata
from functools import reduce
import six

if not six.PY2:
    buffer = memoryview  # sqlite won't accept memoryview in python 2


class ParsingError(ValueError):
    """Abstract class for any unparseable user-requested album/query
    specification.
    """


class InvalidQueryError(ParsingError):
    """Represent any kind of invalid query.

    The query should be a unicode string or a list, which will be space-joined.
    """
    def __init__(self, query, explanation):
        if isinstance(query, list):
            query = " ".join(query)
        message = u"'{0}': {1}".format(query, explanation)
        super(InvalidQueryError, self).__init__(message)


class InvalidQueryArgumentTypeError(ParsingError):
    """Represent a query argument that could not be converted as expected.

    It exists to be caught in upper stack levels so a meaningful (i.e. with the
    query) InvalidQueryError can be raised.
    """
    def __init__(self, what, expected, detail=None):
        message = u"'{0}' is not {1}".format(what, expected)
        if detail:
            message = u"{0}: {1}".format(message, detail)
        super(InvalidQueryArgumentTypeError, self).__init__(message)


class Query(object):
    """An abstract class representing a query into the item database.
    """
    def clause(self):
        """Generate an SQLite expression implementing the query.

        Return (clause, subvals) where clause is a valid sqlite
        WHERE clause implementing the query and subvals is a list of
        items to be substituted for ?s in the clause.
        """
        return None, ()

    def match(self, item):
        """Check whether this query matches a given Item. Can be used to
        perform queries on arbitrary sets of Items.
        """
        raise NotImplementedError

    def __repr__(self):
        return "{0.__class__.__name__}()".format(self)

    def __eq__(self, other):
        return type(self) == type(other)

    def __hash__(self):
        return 0


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

    def __repr__(self):
        return ("{0.__class__.__name__}({0.field!r}, {0.pattern!r}, "
                "{0.fast})".format(self))

    def __eq__(self, other):
        return super(FieldQuery, self).__eq__(other) and \
            self.field == other.field and self.pattern == other.pattern

    def __hash__(self):
        return hash((self.field, hash(self.pattern)))


class MatchQuery(FieldQuery):
    """A query that looks for exact matches in an item field."""
    def col_clause(self):
        return self.field + " = ?", [self.pattern]

    @classmethod
    def value_match(cls, pattern, value):
        return pattern == value


class NoneQuery(FieldQuery):

    def __init__(self, field, fast=True):
        super(NoneQuery, self).__init__(field, None, fast)

    def col_clause(self):
        return self.field + " IS NULL", ()

    @classmethod
    def match(cls, item):
        try:
            return item[cls.field] is None
        except KeyError:
            return True

    def __repr__(self):
        return "{0.__class__.__name__}({0.field!r}, {0.fast})".format(self)


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
        pattern = (self.pattern
                       .replace('\\', '\\\\')
                       .replace('%', '\\%')
                       .replace('_', '\\_'))
        search = '%' + pattern + '%'
        clause = self.field + " like ? escape '\\'"
        subvals = [search]
        return clause, subvals

    @classmethod
    def string_match(cls, pattern, value):
        return pattern.lower() in value.lower()


class RegexpQuery(StringFieldQuery):
    """A query that matches a regular expression in a specific item
    field.

    Raises InvalidQueryError when the pattern is not a valid regular
    expression.
    """
    def __init__(self, field, pattern, fast=True):
        super(RegexpQuery, self).__init__(field, pattern, fast)
        pattern = self._normalize(pattern)
        try:
            self.pattern = re.compile(self.pattern)
        except re.error as exc:
            # Invalid regular expression.
            raise InvalidQueryArgumentTypeError(pattern,
                                                u"a regular expression",
                                                format(exc))

    @staticmethod
    def _normalize(s):
        """Normalize a Unicode string's representation (used on both
        patterns and matched values).
        """
        return unicodedata.normalize('NFC', s)

    @classmethod
    def string_match(cls, pattern, value):
        return pattern.search(cls._normalize(value)) is not None


class BooleanQuery(MatchQuery):
    """Matches a boolean field. Pattern should either be a boolean or a
    string reflecting a boolean.
    """
    def __init__(self, field, pattern, fast=True):
        super(BooleanQuery, self).__init__(field, pattern, fast)
        if isinstance(pattern, six.string_types):
            self.pattern = util.str2bool(pattern)
        self.pattern = int(self.pattern)


class BytesQuery(MatchQuery):
    """Match a raw bytes field (i.e., a path). This is a necessary hack
    to work around the `sqlite3` module's desire to treat `bytes` and
    `unicode` equivalently in Python 2. Always use this query instead of
    `MatchQuery` when matching on BLOB values.
    """
    def __init__(self, field, pattern):
        super(BytesQuery, self).__init__(field, pattern)

        # Use a buffer/memoryview representation of the pattern for SQLite
        # matching. This instructs SQLite to treat the blob as binary
        # rather than encoded Unicode.
        if isinstance(self.pattern, (six.text_type, bytes)):
            if isinstance(self.pattern, six.text_type):
                self.pattern = self.pattern.encode('utf-8')
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

    Raises InvalidQueryError when the pattern does not represent an int or
    a float.
    """
    def _convert(self, s):
        """Convert a string to a numeric type (float or int).

        Return None if `s` is empty.
        Raise an InvalidQueryError if the string cannot be converted.
        """
        # This is really just a bit of fun premature optimization.
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                raise InvalidQueryArgumentTypeError(s, u"an int or a float")

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
        if self.field not in item:
            return False
        value = item[self.field]
        if isinstance(value, six.string_types):
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
                return u'1', ()


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
        """Return a clause created by joining together the clauses of
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

    def __repr__(self):
        return "{0.__class__.__name__}({0.subqueries!r})".format(self)

    def __eq__(self, other):
        return super(CollectionQuery, self).__eq__(other) and \
            self.subqueries == other.subqueries

    def __hash__(self):
        """Since subqueries are mutable, this object should not be hashable.
        However and for conveniences purposes, it can be hashed.
        """
        return reduce(mul, map(hash, self.subqueries), 1)


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

    def __repr__(self):
        return ("{0.__class__.__name__}({0.pattern!r}, {0.fields!r}, "
                "{0.query_class.__name__})".format(self))

    def __eq__(self, other):
        return super(AnyFieldQuery, self).__eq__(other) and \
            self.query_class == other.query_class

    def __hash__(self):
        return hash((self.pattern, tuple(self.fields), self.query_class))


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


class OrQuery(MutableCollectionQuery):
    """A conjunction of a list of other queries."""
    def clause(self):
        return self.clause_with_joiner('or')

    def match(self, item):
        return any([q.match(item) for q in self.subqueries])


class NotQuery(Query):
    """A query that matches the negation of its `subquery`, as a shorcut for
    performing `not(subquery)` without using regular expressions.
    """
    def __init__(self, subquery):
        self.subquery = subquery

    def clause(self):
        clause, subvals = self.subquery.clause()
        if clause:
            return 'not ({0})'.format(clause), subvals
        else:
            # If there is no clause, there is nothing to negate. All the logic
            # is handled by match() for slow queries.
            return clause, subvals

    def match(self, item):
        return not self.subquery.match(item)

    def __repr__(self):
        return "{0.__class__.__name__}({0.subquery!r})".format(self)

    def __eq__(self, other):
        return super(NotQuery, self).__eq__(other) and \
            self.subquery == other.subquery

    def __hash__(self):
        return hash(('not', hash(self.subquery)))


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


# Time/date queries.

def _to_epoch_time(date):
    """Convert a `datetime` object to an integer number of seconds since
    the (local) Unix epoch.
    """
    if hasattr(date, 'timestamp'):
        # The `timestamp` method exists on Python 3.3+.
        return int(date.timestamp())
    else:
        epoch = datetime.fromtimestamp(0)
        delta = date - epoch
        return int(delta.total_seconds())


def _parse_periods(pattern):
    """Parse a string containing two dates separated by two dots (..).
    Return a pair of `Period` objects.
    """
    parts = pattern.split('..', 1)
    if len(parts) == 1:
        instant = Period.parse(parts[0])
        return (instant, instant)
    else:
        start = Period.parse(parts[0])
        end = Period.parse(parts[1])
        return (start, end)


class Period(object):
    """A period of time given by a date, time and precision.

    Example: 2014-01-01 10:50:30 with precision 'month' represents all
    instants of time during January 2014.
    """

    precisions = ('year', 'month', 'day')
    date_formats = ('%Y', '%Y-%m', '%Y-%m-%d')

    def __init__(self, date, precision):
        """Create a period with the given date (a `datetime` object) and
        precision (a string, one of "year", "month", or "day").
        """
        if precision not in Period.precisions:
            raise ValueError(u'Invalid precision {0}'.format(precision))
        self.date = date
        self.precision = precision

    @classmethod
    def parse(cls, string):
        """Parse a date and return a `Period` object or `None` if the
        string is empty.
        """
        if not string:
            return None
        ordinal = string.count('-')
        if ordinal >= len(cls.date_formats):
            # Too many components.
            return None
        date_format = cls.date_formats[ordinal]
        try:
            date = datetime.strptime(string, date_format)
        except ValueError:
            # Parsing failed.
            return None
        precision = cls.precisions[ordinal]
        return cls(date, precision)

    def open_right_endpoint(self):
        """Based on the precision, convert the period to a precise
        `datetime` for use as a right endpoint in a right-open interval.
        """
        precision = self.precision
        date = self.date
        if 'year' == self.precision:
            return date.replace(year=date.year + 1, month=1)
        elif 'month' == precision:
            if (date.month < 12):
                return date.replace(month=date.month + 1)
            else:
                return date.replace(year=date.year + 1, month=1)
        elif 'day' == precision:
            return date + timedelta(days=1)
        else:
            raise ValueError(u'unhandled precision {0}'.format(precision))


class DateInterval(object):
    """A closed-open interval of dates.

    A left endpoint of None means since the beginning of time.
    A right endpoint of None means towards infinity.
    """

    def __init__(self, start, end):
        if start is not None and end is not None and not start < end:
            raise ValueError(u"start date {0} is not before end date {1}"
                             .format(start, end))
        self.start = start
        self.end = end

    @classmethod
    def from_periods(cls, start, end):
        """Create an interval with two Periods as the endpoints.
        """
        end_date = end.open_right_endpoint() if end is not None else None
        start_date = start.date if start is not None else None
        return cls(start_date, end_date)

    def contains(self, date):
        if self.start is not None and date < self.start:
            return False
        if self.end is not None and date >= self.end:
            return False
        return True

    def __str__(self):
        return '[{0}, {1})'.format(self.start, self.end)


class DateQuery(FieldQuery):
    """Matches date fields stored as seconds since Unix epoch time.

    Dates can be specified as ``year-month-day`` strings where only year
    is mandatory.

    The value of a date field can be matched against a date interval by
    using an ellipsis interval syntax similar to that of NumericQuery.
    """
    def __init__(self, field, pattern, fast=True):
        super(DateQuery, self).__init__(field, pattern, fast)
        start, end = _parse_periods(pattern)
        self.interval = DateInterval.from_periods(start, end)

    def match(self, item):
        if self.field not in item:
            return False
        timestamp = float(item[self.field])
        date = datetime.utcfromtimestamp(timestamp)
        return self.interval.contains(date)

    _clause_tmpl = "{0} {1} ?"

    def col_clause(self):
        clause_parts = []
        subvals = []

        if self.interval.start:
            clause_parts.append(self._clause_tmpl.format(self.field, ">="))
            subvals.append(_to_epoch_time(self.interval.start))

        if self.interval.end:
            clause_parts.append(self._clause_tmpl.format(self.field, "<"))
            subvals.append(_to_epoch_time(self.interval.end))

        if clause_parts:
            # One- or two-sided interval.
            clause = ' AND '.join(clause_parts)
        else:
            # Match any date.
            clause = '1'
        return clause, subvals


class DurationQuery(NumericQuery):
    """NumericQuery that allow human-friendly (M:SS) time interval formats.

    Converts the range(s) to a float value, and delegates on NumericQuery.

    Raises InvalidQueryError when the pattern does not represent an int, float
    or M:SS time interval.
    """
    def _convert(self, s):
        """Convert a M:SS or numeric string to a float.

        Return None if `s` is empty.
        Raise an InvalidQueryError if the string cannot be converted.
        """
        if not s:
            return None
        try:
            return util.raw_seconds_short(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                raise InvalidQueryArgumentTypeError(
                    s,
                    u"a M:SS string or a float")


# Sorting.

class Sort(object):
    """An abstract class representing a sort operation for a query into
    the item database.
    """

    def order_clause(self):
        """Generates a SQL fragment to be used in a ORDER BY clause, or
        None if no fragment is used (i.e., this is a slow sort).
        """
        return None

    def sort(self, items):
        """Sort the list of objects and return a list.
        """
        return sorted(items)

    def is_slow(self):
        """Indicate whether this query is *slow*, meaning that it cannot
        be executed in SQL and must be executed in Python.
        """
        return False

    def __hash__(self):
        return 0

    def __eq__(self, other):
        return type(self) == type(other)


class MultipleSort(Sort):
    """Sort that encapsulates multiple sub-sorts.
    """

    def __init__(self, sorts=None):
        self.sorts = sorts or []

    def add_sort(self, sort):
        self.sorts.append(sort)

    def _sql_sorts(self):
        """Return the list of sub-sorts for which we can be (at least
        partially) fast.

        A contiguous suffix of fast (SQL-capable) sub-sorts are
        executable in SQL. The remaining, even if they are fast
        independently, must be executed slowly.
        """
        sql_sorts = []
        for sort in reversed(self.sorts):
            if not sort.order_clause() is None:
                sql_sorts.append(sort)
            else:
                break
        sql_sorts.reverse()
        return sql_sorts

    def order_clause(self):
        order_strings = []
        for sort in self._sql_sorts():
            order = sort.order_clause()
            order_strings.append(order)

        return ", ".join(order_strings)

    def is_slow(self):
        for sort in self.sorts:
            if sort.is_slow():
                return True
        return False

    def sort(self, items):
        slow_sorts = []
        switch_slow = False
        for sort in reversed(self.sorts):
            if switch_slow:
                slow_sorts.append(sort)
            elif sort.order_clause() is None:
                switch_slow = True
                slow_sorts.append(sort)
            else:
                pass

        for sort in slow_sorts:
            items = sort.sort(items)
        return items

    def __repr__(self):
        return 'MultipleSort({!r})'.format(self.sorts)

    def __hash__(self):
        return hash(tuple(self.sorts))

    def __eq__(self, other):
        return super(MultipleSort, self).__eq__(other) and \
            self.sorts == other.sorts


class FieldSort(Sort):
    """An abstract sort criterion that orders by a specific field (of
    any kind).
    """
    def __init__(self, field, ascending=True, case_insensitive=True):
        self.field = field
        self.ascending = ascending
        self.case_insensitive = case_insensitive

    def sort(self, objs):
        # TODO: Conversion and null-detection here. In Python 3,
        # comparisons with None fail. We should also support flexible
        # attributes with different types without falling over.

        def key(item):
            field_val = item.get(self.field, '')
            if self.case_insensitive and isinstance(field_val, six.text_type):
                field_val = field_val.lower()
            return field_val

        return sorted(objs, key=key, reverse=not self.ascending)

    def __repr__(self):
        return '<{0}: {1}{2}>'.format(
            type(self).__name__,
            self.field,
            '+' if self.ascending else '-',
        )

    def __hash__(self):
        return hash((self.field, self.ascending))

    def __eq__(self, other):
        return super(FieldSort, self).__eq__(other) and \
            self.field == other.field and \
            self.ascending == other.ascending


class FixedFieldSort(FieldSort):
    """Sort object to sort on a fixed field.
    """
    def order_clause(self):
        order = "ASC" if self.ascending else "DESC"
        if self.case_insensitive:
            field = '(CASE ' \
                    'WHEN TYPEOF({0})="text" THEN LOWER({0}) ' \
                    'WHEN TYPEOF({0})="blob" THEN LOWER({0}) ' \
                    'ELSE {0} END)'.format(self.field)
        else:
            field = self.field
        return "{0} {1}".format(field, order)


class SlowFieldSort(FieldSort):
    """A sort criterion by some model field other than a fixed field:
    i.e., a computed or flexible field.
    """
    def is_slow(self):
        return True


class NullSort(Sort):
    """No sorting. Leave results unsorted."""
    def sort(self, items):
        return items

    def __nonzero__(self):
        return self.__bool__()

    def __bool__(self):
        return False

    def __eq__(self, other):
        return type(self) == type(other) or other is None

    def __hash__(self):
        return 0
