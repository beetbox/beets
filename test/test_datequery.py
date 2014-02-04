import unittest
from datetime import datetime
from beets.dbcore.query import _parse_periods, DateInterval

def _date(string):
    return datetime.strptime(string, '%Y-%m-%dT%H:%M:%S')

class TestDateQuery(unittest.TestCase):

    def test_year_precision_intervals(self):
        self.assertContains('2000..2001', '2000-01-01T00:00:00')
        self.assertContains('2000..2001', '2001-06-20T14:15:16')
        self.assertContains('2000..2001', '2001-12-31T23:59:59')
        self.assertExcludes('2000..2001', '1999-12-31T23:59:59')
        self.assertExcludes('2000..2001', '2002-01-01T00:00:00')

        self.assertContains('2000..', '2000-01-01T00:00:00')
        self.assertContains('2000..', '2099-10-11T00:00:00')
        self.assertExcludes('2000..', '1999-12-31T23:59:59')

        self.assertContains('..2001', '2001-12-31T23:59:59')
        self.assertExcludes('..2001', '2002-01-01T00:00:00')

    def test_day_precision_intervals(self):
        self.assertContains('2000-06-20..2000-06-20', '2000-06-20T00:00:00')
        self.assertContains('2000-06-20..2000-06-20', '2000-06-20T10:20:30')
        self.assertContains('2000-06-20..2000-06-20', '2000-06-20T23:59:59')
        self.assertExcludes('2000-06-20..2000-06-20', '2000-06-19T23:59:59')
        self.assertExcludes('2000-06-20..2000-06-20', '2000-06-21T00:00:00')

    def test_month_precision_intervals(self):
        self.assertContains('1999-12..2000-02', '1999-12-01T00:00:00')
        self.assertContains('1999-12..2000-02', '2000-02-15T05:06:07')
        self.assertContains('1999-12..2000-02', '2000-02-29T23:59:59')
        self.assertExcludes('1999-12..2000-02', '1999-11-30T23:59:59')
        self.assertExcludes('1999-12..2000-02', '2000-03-01T00:00:00')

    def test_unbounded_endpoints(self):
        self.assertContains('..', date=datetime.max)
        self.assertContains('..', date=datetime.min)
        self.assertContains('..', '1000-01-01T00:00:00')

    def assertContains(self, interval_pattern, date_pattern=None, date=None):
        if date is None:
            date = _date(date_pattern)
        (start, end) = _parse_periods(interval_pattern)
        interval = DateInterval.from_periods(start, end)
        self.assertTrue(interval.contains(date))

    def assertExcludes(self, interval_pattern, date_pattern):
        date = _date(date_pattern)
        (start, end) = _parse_periods(interval_pattern)
        interval = DateInterval.from_periods(start, end)
        self.assertFalse(interval.contains(date))

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
