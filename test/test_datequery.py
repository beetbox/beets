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

"""Test for dbcore's date-based queries.
"""
from __future__ import division, absolute_import, print_function

from test import _common
from datetime import datetime
import unittest
import time
from beets.dbcore.query import _parse_periods, DateInterval, DateQuery,\
    InvalidQueryArgumentValueError


def _date(string):
    return datetime.strptime(string, '%Y-%m-%dT%H:%M:%S')


class DateIntervalTest(unittest.TestCase):
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

    def assertContains(self, interval_pattern, date_pattern=None, date=None):  # noqa
        if date is None:
            date = _date(date_pattern)
        (start, end) = _parse_periods(interval_pattern)
        interval = DateInterval.from_periods(start, end)
        self.assertTrue(interval.contains(date))

    def assertExcludes(self, interval_pattern, date_pattern):  # noqa
        date = _date(date_pattern)
        (start, end) = _parse_periods(interval_pattern)
        interval = DateInterval.from_periods(start, end)
        self.assertFalse(interval.contains(date))


def _parsetime(s):
    return time.mktime(datetime.strptime(s, '%Y-%m-%d %H:%M').timetuple())


class DateQueryTest(_common.LibTestCase):
    def setUp(self):
        super(DateQueryTest, self).setUp()
        self.i.added = _parsetime('2013-03-30 22:21')
        self.i.store()

    def test_single_month_match_fast(self):
        query = DateQuery('added', '2013-03')
        matched = self.lib.items(query)
        self.assertEqual(len(matched), 1)

    def test_single_month_nonmatch_fast(self):
        query = DateQuery('added', '2013-04')
        matched = self.lib.items(query)
        self.assertEqual(len(matched), 0)

    def test_single_month_match_slow(self):
        query = DateQuery('added', '2013-03')
        self.assertTrue(query.match(self.i))

    def test_single_month_nonmatch_slow(self):
        query = DateQuery('added', '2013-04')
        self.assertFalse(query.match(self.i))

    def test_single_day_match_fast(self):
        query = DateQuery('added', '2013-03-30')
        matched = self.lib.items(query)
        self.assertEqual(len(matched), 1)

    def test_single_day_nonmatch_fast(self):
        query = DateQuery('added', '2013-03-31')
        matched = self.lib.items(query)
        self.assertEqual(len(matched), 0)


class DateQueryConstructTest(unittest.TestCase):
    def test_long_numbers(self):
        with self.assertRaises(InvalidQueryArgumentValueError):
            DateQuery('added', '1409830085..1412422089')

    def test_too_many_components(self):
        with self.assertRaises(InvalidQueryArgumentValueError):
            DateQuery('added', '12-34-56-78')

    def test_invalid_date_query(self):
        q_list = [
            '2001-01-0a',
            '2001-0a',
            '200a',
            '2001-01-01..2001-01-0a',
            '2001-0a..2001-01',
            '200a..2002',
            '20aa..',
            '..2aa'
        ]
        for q in q_list:
            with self.assertRaises(InvalidQueryArgumentValueError):
                DateQuery('added', q)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
