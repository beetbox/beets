"""Matches date fields stored as seconds since Unix epoch time.

Dates can be specified as year-month-day where only year is mandatory.

The value of a date field can be matched against a date interval by using an
ellipses interval syntax similar to that of NumericQuery.
"""

from __future__ import unicode_literals, absolute_import, print_function
from beets.plugins import BeetsPlugin
from beets.dbcore import FieldQuery
from datetime import datetime, timedelta
from beets.library import ITEM_FIELDS, DateType

_DATE_FIELDS = [fieldname for (fieldname, typedef, _, _)
                in ITEM_FIELDS if isinstance(typedef, DateType) ]

def _queryable(fieldname):
    """Determine whether a field can by queried as a date.
    """
    return fieldname in _DATE_FIELDS

def _to_epoch_time(date):
    epoch = datetime.utcfromtimestamp(0)
    return int((date - epoch).total_seconds())

def _parse_periods(pattern):
    """Parse two Periods separated by '..'
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

    Example:
    2014-01-01 10:50:30 with precision 'month' represent all instants of time
    during January 2014.
    """

    precisions = ('year', 'month', 'day')
    date_formats = ('%Y', '%Y-%m', '%Y-%m-%d')

    def __init__(self, date, precision):
        if precision not in Period.precisions:
            raise ValueError('Invalid precision ' + str(precision))
        self.date = date
        self.precision = precision

    @classmethod
    def parse(cls, string):
        """Parse a date into a period.
        """
        if not string: return None
        ordinal = string.count('-')
        if ordinal >= len(cls.date_formats):
            raise ValueError('Date is not in one of the formats '
                                + ', '.join(cls.date_formats))
        date_format = cls.date_formats[ordinal]
        date = datetime.strptime(string, date_format)
        precision = cls.precisions[ordinal]
        return cls(date, precision)

    def open_right_endpoint(self):
        """Based on the precision, convert the period to a precise datetime
        for use as a right endpoint in a right-open interval.
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
            raise ValueError('Unhandled precision ' + str(precision))

class DateInterval(object):
    """A closed-open interval of dates.

    A left endpoint of None means since the beginning of time.
    A right endpoint of None means towards infinity.
    """

    def __init__(self, start, end):
        if start is not None and end is not None and not start < end:
            raise ValueError("Start date {} is not before end date {}"
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
        return'[{}, {})'.format(self.start, self.end)

class DateQuery(FieldQuery):
    def __init__(self, field, pattern, fast=True):
        super(DateQuery, self).__init__(field, pattern, fast)
        if not _queryable(field):
            raise ValueError('Field {} cannot be queried as a date'.format(field))

        (start, end) = _parse_periods(pattern)
        self.interval = DateInterval.from_periods(start, end)

    def match(self, item):
        timestamp = float(item[self.field])
        date = datetime.utcfromtimestamp(timestamp)
        return self.interval.contains(date)

    def col_clause(self):
        if self.interval.start is not None and self.interval.end is not None:
            start_epoch_time = _to_epoch_time(self.interval.start)
            end_epoch_time = _to_epoch_time(self.interval.end)
            template = ("date({}, 'unixepoch') >= date(?, 'unixepoch')"
                        " AND date({}, 'unixepoch') < date(?, 'unixepoch')")
            clause = template.format(self.field, self.field)
            return (clause, (start_epoch_time, end_epoch_time))
        elif self.interval.start is not None:
            epoch_time = _to_epoch_time(self.interval.start)
            template = "date({}, 'unixepoch') >= date(?, 'unixepoch')"
            clause = template.format(self.field)
            return clause.format(self.field), (epoch_time,)
        elif self.interval.end is not None:
            epoch_time = _to_epoch_time(self.interval.end)
            template = "date({}, 'unixepoch') < date(?, 'unixepoch')"
            clause = template.format(self.field)
            return clause.format(self.field), (epoch_time,)
        else:
            return '1 = ?', (1,) # match any date

class DateQueryPlugin(BeetsPlugin):
    def queries(self):
        return {'T': DateQuery}
