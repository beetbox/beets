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
from operator import attrgetter
from beets import util
from datetime import datetime, timedelta


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
        if isinstance(self.pattern, basestring):
            # Implicitly coerce Unicode strings to their bytes
            # equivalents.
            if isinstance(self.pattern, unicode):
                self.pattern = self.pattern.encode('utf8')
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
                return '1', ()


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


class OrQuery(MutableCollectionQuery):
    """A conjunction of a list of other queries."""
    def clause(self):
        return self.clause_with_joiner('or')

    def match(self, item):
        return any([q.match(item) for q in self.subqueries])


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
    epoch = datetime.fromtimestamp(0)
    delta = date - epoch
    try:
        return int(delta.total_seconds())
    except AttributeError:
        # datetime.timedelta.total_seconds() is not available on Python 2.6
        return delta.seconds + delta.days * 24 * 3600


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
            raise ValueError('Invalid precision ' + str(precision))
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
            raise ValueError('date is not in one of the formats '
                             + ', '.join(cls.date_formats))
        date_format = cls.date_formats[ordinal]
        date = datetime.strptime(string, date_format)
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
            raise ValueError('unhandled precision ' + str(precision))


class DateInterval(object):
    """A closed-open interval of dates.

    A left endpoint of None means since the beginning of time.
    A right endpoint of None means towards infinity.
    """

    def __init__(self, start, end):
        if start is not None and end is not None and not start < end:
            raise ValueError("start date {0} is not before end date {1}"
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
        return'[{0}, {1})'.format(self.start, self.end)


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


class Sort(object):
    """An abstract class representing a sort operation for a query into the
    item database.
    """
    def select_clause(self):
        """ Generates a select sql fragment if the sort operation requires one,
        an empty string otherwise.
        """
        return ""

    def union_clause(self):
        """ Generates a union sql fragment if the sort operation requires one,
        an empty string otherwise.
        """
        return ""

    def order_clause(self):
        """Generates a sql fragment to be use in a ORDER BY clause or None if
        it's a slow query.
        """
        return None

    def sort(self, items):
        """Return a key function that can be used with the list.sort() method.
        Meant to be used with slow sort, it must be implemented even for sort
        that can be done with sql, as they might be used in conjunction with
        slow sort.
        """
        return sorted(items, key=lambda x: x)

    def is_slow(self):
        return False


class MultipleSort(Sort):
    """Sort class that combines several sort criteria.
    This implementation tries to implement as many sort operation in sql,
    falling back to python sort only when necessary.
    """

    def __init__(self):
        self.sorts = []

    def add_criteria(self, sort):
        self.sorts.append(sort)

    def _sql_sorts(self):
        """ Returns the list of sort for which sql can be used
        """
        # with several Sort, we can use SQL sorting only if there is only
        # SQL-capable Sort or if the list ends with SQl-capable Sort.
        sql_sorts = []
        for sort in reversed(self.sorts):
            if not sort.order_clause() is None:
                sql_sorts.append(sort)
            else:
                break
        sql_sorts.reverse()
        return sql_sorts

    def select_clause(self):
        sql_sorts = self._sql_sorts()
        select_strings = []
        for sort in sql_sorts:
            select = sort.select_clause()
            if select:
                select_strings.append(select)

        select_string = ",".join(select_strings)
        return select_string

    def union_clause(self):
        sql_sorts = self._sql_sorts()
        union_strings = []
        for sort in sql_sorts:
            union = sort.union_clause()
            union_strings.append(union)

        return "".join(union_strings)

    def order_clause(self):
        sql_sorts = self._sql_sorts()
        order_strings = []
        for sort in sql_sorts:
            order = sort.order_clause()
            order_strings.append(order)

        return ",".join(order_strings)

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


class FlexFieldSort(Sort):
    """Sort object to sort on a flexible attribute field
    """
    def __init__(self, model_cls, field, is_ascending):
        self.model_cls = model_cls
        self.field = field
        self.is_ascending = is_ascending

    def select_clause(self):
        """ Return a select sql fragment.
        """
        return "sort_flexattr{0!s}.value as flex_{0!s} ".format(self.field)

    def union_clause(self):
        """ Returns an union sql fragment.
        """
        union = ("LEFT JOIN {flextable} as sort_flexattr{index!s} "
                 "ON {table}.id = sort_flexattr{index!s}.entity_id "
                 "AND sort_flexattr{index!s}.key='{flexattr}' ").format(
            flextable=self.model_cls._flex_table,
            table=self.model_cls._table,
            index=self.field, flexattr=self.field)
        return union

    def order_clause(self):
        """ Returns an order sql fragment.
        """
        order = "ASC" if self.is_ascending else "DESC"
        return "flex_{0} {1} ".format(self.field, order)

    def sort(self, items):
        return sorted(items, key=attrgetter(self.field),
                      reverse=(not self.is_ascending))


class FixedFieldSort(Sort):
    """Sort object to sort on a fixed field
    """
    def __init__(self, field, is_ascending=True):
        self.field = field
        self.is_ascending = is_ascending

    def order_clause(self):
        order = "ASC" if self.is_ascending else "DESC"
        return "{0} {1}".format(self.field, order)

    def sort(self, items):
        return sorted(items, key=attrgetter(self.field),
                      reverse=(not self.is_ascending))


class SmartArtistSort(Sort):
    """ Sort Album or Item on artist sort fields, defaulting back on
        artist field if the sort specific field is empty.
    """
    def __init__(self, model_cls, is_ascending=True):
        self.model_cls = model_cls
        self.is_ascending = is_ascending

    def select_clause(self):
        return ""

    def union_clause(self):
        return ""

    def order_clause(self):
        order = "ASC" if self.is_ascending else "DESC"
        if 'albumartist_sort' in self.model_cls._fields:
            exp1 = 'albumartist_sort'
            exp2 = 'albumartist'
        elif 'artist_sort' in self.model_cls_fields:
            exp1 = 'artist_sort'
            exp2 = 'artist'
        else:
            return ""

        order_str = ('(CASE {0} WHEN NULL THEN {1} '
                     'WHEN "" THEN {1} '
                     'ELSE {0} END) {2} ').format(exp1, exp2, order)
        return order_str


class ComputedFieldSort(Sort):

    def __init__(self, model_cls, field, is_ascending=True):
        self.is_ascending = is_ascending
        self.field = field
        self._getters = model_cls._getters()

    def is_slow(self):
        return True

    def sort(self, items):
        return sorted(items, key=lambda x: self._getters[self.field](x),
                      reverse=(not self.is_ascending))

special_sorts = {'smartartist': SmartArtistSort}


def build_sql(model_cls, query, sort):
    """ Generate a sql statement (and the values that must be injected into it)
    from a query, sort and a model class. Query and sort objects are returned
    only for slow query and slow sort operation.
    """
    where, subvals = query.clause()
    if where is not None:
        query = None

    if not sort:
        sort_select = ""
        sort_union = ""
        sort_order = ""
        sort = None
    elif isinstance(sort, basestring):
        sort_select = ""
        sort_union = ""
        sort_order = " ORDER BY {0}".format(sort) \
            if sort else ""
        sort = None
    elif isinstance(sort, Sort):
        select_clause = sort.select_clause()
        sort_select = " ,{0} ".format(select_clause) \
            if select_clause else ""
        sort_union = sort.union_clause()
        order_clause = sort.order_clause()
        sort_order = " ORDER BY {0}".format(order_clause) \
            if order_clause else ""
        if sort.is_slow():
            sort = None

    sql = ("SELECT {table}.* {sort_select} FROM {table} {sort_union} WHERE "
           "{query_clause} {sort_order}").format(
        sort_select=sort_select,
        sort_union=sort_union,
        table=model_cls._table,
        query_clause=where or '1',
        sort_order=sort_order
    )

    return sql, subvals, query, sort
