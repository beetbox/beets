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

"""Test for dbcore's date-based queries."""

import time
import unittest
from datetime import datetime, timedelta

import pytest

from beets.dbcore.query import (
    DateInterval,
    DateQuery,
    InvalidQueryArgumentValueError,
    _parse_periods,
)
from beets.test.helper import ItemInDBTestCase


class TestDateInterval:
    now = datetime.now().replace(microsecond=0, second=0).isoformat()

    @pytest.mark.parametrize(
        "pattern, datestr, include",
        [
            # year precision
            ("2000..2001", "2000-01-01T00:00:00", True),
            ("2000..2001", "2001-06-20T14:15:16", True),
            ("2000..2001", "2001-12-31T23:59:59", True),
            ("2000..2001", "1999-12-31T23:59:59", False),
            ("2000..2001", "2002-01-01T00:00:00", False),
            ("2000..", "2000-01-01T00:00:00", True),
            ("2000..", "2099-10-11T00:00:00", True),
            ("2000..", "1999-12-31T23:59:59", False),
            ("..2001", "2001-12-31T23:59:59", True),
            ("..2001", "2002-01-01T00:00:00", False),
            ("-1d..1d", now, True),
            ("-2d..-1d", now, False),
            # month precision
            ("2000-06-20..2000-06-20", "2000-06-20T00:00:00", True),
            ("2000-06-20..2000-06-20", "2000-06-20T10:20:30", True),
            ("2000-06-20..2000-06-20", "2000-06-20T23:59:59", True),
            ("2000-06-20..2000-06-20", "2000-06-19T23:59:59", False),
            ("2000-06-20..2000-06-20", "2000-06-21T00:00:00", False),
            # day precision
            ("1999-12..2000-02", "1999-12-01T00:00:00", True),
            ("1999-12..2000-02", "2000-02-15T05:06:07", True),
            ("1999-12..2000-02", "2000-02-29T23:59:59", True),
            ("1999-12..2000-02", "1999-11-30T23:59:59", False),
            ("1999-12..2000-02", "2000-03-01T00:00:00", False),
            # hour precision with 'T' separator
            ("2000-01-01T12..2000-01-01T13", "2000-01-01T11:59:59", False),
            ("2000-01-01T12..2000-01-01T13", "2000-01-01T12:00:00", True),
            ("2000-01-01T12..2000-01-01T13", "2000-01-01T12:30:00", True),
            ("2000-01-01T12..2000-01-01T13", "2000-01-01T13:30:00", True),
            ("2000-01-01T12..2000-01-01T13", "2000-01-01T13:59:59", True),
            ("2000-01-01T12..2000-01-01T13", "2000-01-01T14:00:00", False),
            ("2000-01-01T12..2000-01-01T13", "2000-01-01T14:30:00", False),
            # hour precision non-range query
            ("2008-12-01T22", "2008-12-01T22:30:00", True),
            ("2008-12-01T22", "2008-12-01T23:30:00", False),
            # minute precision
            ("2000-01-01T12:30..2000-01-01T12:31", "2000-01-01T12:29:59", False),
            ("2000-01-01T12:30..2000-01-01T12:31", "2000-01-01T12:30:00", True),
            ("2000-01-01T12:30..2000-01-01T12:31", "2000-01-01T12:30:30", True),
            ("2000-01-01T12:30..2000-01-01T12:31", "2000-01-01T12:31:59", True),
            ("2000-01-01T12:30..2000-01-01T12:31", "2000-01-01T12:32:00", False),
            # second precision
            ("2000-01-01T12:30:50..2000-01-01T12:30:55", "2000-01-01T12:30:49", False),
            ("2000-01-01T12:30:50..2000-01-01T12:30:55", "2000-01-01T12:30:50", True),
            ("2000-01-01T12:30:50..2000-01-01T12:30:55", "2000-01-01T12:30:55", True),
            ("2000-01-01T12:30:50..2000-01-01T12:30:55", "2000-01-01T12:30:56", False), # unbounded  # noqa: E501
            ("..", datetime.max.isoformat(), True),
            ("..", datetime.min.isoformat(), True),
            ("..", "1000-01-01T00:00:00", True),
        ],
    )  # fmt: skip
    def test_intervals(self, pattern, datestr, include):
        (start, end) = _parse_periods(pattern)
        interval = DateInterval.from_periods(start, end)
        assert interval.contains(datetime.fromisoformat(datestr)) == include


def _parsetime(s):
    return time.mktime(datetime.strptime(s, "%Y-%m-%d %H:%M").timetuple())


class DateQueryTest(ItemInDBTestCase):
    def setUp(self):
        super().setUp()
        self.i.added = _parsetime("2013-03-30 22:21")
        self.i.store()

    def test_single_month_match_fast(self):
        query = DateQuery("added", "2013-03")
        matched = self.lib.items(query)
        assert len(matched) == 1

    def test_single_month_nonmatch_fast(self):
        query = DateQuery("added", "2013-04")
        matched = self.lib.items(query)
        assert len(matched) == 0

    def test_single_month_match_slow(self):
        query = DateQuery("added", "2013-03")
        assert query.match(self.i)

    def test_single_month_nonmatch_slow(self):
        query = DateQuery("added", "2013-04")
        assert not query.match(self.i)

    def test_single_day_match_fast(self):
        query = DateQuery("added", "2013-03-30")
        matched = self.lib.items(query)
        assert len(matched) == 1

    def test_single_day_nonmatch_fast(self):
        query = DateQuery("added", "2013-03-31")
        matched = self.lib.items(query)
        assert len(matched) == 0


class DateQueryTestRelative(ItemInDBTestCase):
    def setUp(self):
        super().setUp()

        # We pick a date near a month changeover, which can reveal some time
        # zone bugs.
        self._now = datetime(2017, 12, 31, 22, 55, 4, 101332)

        self.i.added = _parsetime(self._now.strftime("%Y-%m-%d %H:%M"))
        self.i.store()

    def test_single_month_match_fast(self):
        query = DateQuery("added", self._now.strftime("%Y-%m"))
        matched = self.lib.items(query)
        assert len(matched) == 1

    def test_single_month_nonmatch_fast(self):
        query = DateQuery(
            "added", (self._now + timedelta(days=30)).strftime("%Y-%m")
        )
        matched = self.lib.items(query)
        assert len(matched) == 0

    def test_single_month_match_slow(self):
        query = DateQuery("added", self._now.strftime("%Y-%m"))
        assert query.match(self.i)

    def test_single_month_nonmatch_slow(self):
        query = DateQuery(
            "added", (self._now + timedelta(days=30)).strftime("%Y-%m")
        )
        assert not query.match(self.i)

    def test_single_day_match_fast(self):
        query = DateQuery("added", self._now.strftime("%Y-%m-%d"))
        matched = self.lib.items(query)
        assert len(matched) == 1

    def test_single_day_nonmatch_fast(self):
        query = DateQuery(
            "added", (self._now + timedelta(days=1)).strftime("%Y-%m-%d")
        )
        matched = self.lib.items(query)
        assert len(matched) == 0


class DateQueryTestRelativeMore(ItemInDBTestCase):
    def setUp(self):
        super().setUp()
        self.i.added = _parsetime(datetime.now().strftime("%Y-%m-%d %H:%M"))
        self.i.store()

    def test_relative(self):
        for timespan in ["d", "w", "m", "y"]:
            query = DateQuery("added", f"-4{timespan}..+4{timespan}")
            matched = self.lib.items(query)
            assert len(matched) == 1

    def test_relative_fail(self):
        for timespan in ["d", "w", "m", "y"]:
            query = DateQuery("added", f"-2{timespan}..-1{timespan}")
            matched = self.lib.items(query)
            assert len(matched) == 0

    def test_start_relative(self):
        for timespan in ["d", "w", "m", "y"]:
            query = DateQuery("added", f"-4{timespan}..")
            matched = self.lib.items(query)
            assert len(matched) == 1

    def test_start_relative_fail(self):
        for timespan in ["d", "w", "m", "y"]:
            query = DateQuery("added", f"4{timespan}..")
            matched = self.lib.items(query)
            assert len(matched) == 0

    def test_end_relative(self):
        for timespan in ["d", "w", "m", "y"]:
            query = DateQuery("added", f"..+4{timespan}")
            matched = self.lib.items(query)
            assert len(matched) == 1

    def test_end_relative_fail(self):
        for timespan in ["d", "w", "m", "y"]:
            query = DateQuery("added", f"..-4{timespan}")
            matched = self.lib.items(query)
            assert len(matched) == 0


class DateQueryConstructTest(unittest.TestCase):
    def test_long_numbers(self):
        with pytest.raises(InvalidQueryArgumentValueError):
            DateQuery("added", "1409830085..1412422089")

    def test_too_many_components(self):
        with pytest.raises(InvalidQueryArgumentValueError):
            DateQuery("added", "12-34-56-78")

    def test_invalid_date_query(self):
        q_list = [
            "2001-01-0a",
            "2001-0a",
            "200a",
            "2001-01-01..2001-01-0a",
            "2001-0a..2001-01",
            "200a..2002",
            "20aa..",
            "..2aa",
        ]
        for q in q_list:
            with pytest.raises(InvalidQueryArgumentValueError):
                DateQuery("added", q)

    def test_datetime_uppercase_t_separator(self):
        date_query = DateQuery("added", "2000-01-01T12")
        assert date_query.interval.start == datetime(2000, 1, 1, 12)
        assert date_query.interval.end == datetime(2000, 1, 1, 13)

    def test_datetime_lowercase_t_separator(self):
        date_query = DateQuery("added", "2000-01-01t12")
        assert date_query.interval.start == datetime(2000, 1, 1, 12)
        assert date_query.interval.end == datetime(2000, 1, 1, 13)

    def test_datetime_space_separator(self):
        date_query = DateQuery("added", "2000-01-01 12")
        assert date_query.interval.start == datetime(2000, 1, 1, 12)
        assert date_query.interval.end == datetime(2000, 1, 1, 13)

    def test_datetime_invalid_separator(self):
        with pytest.raises(InvalidQueryArgumentValueError):
            DateQuery("added", "2000-01-01x12")
