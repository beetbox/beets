"""Tests for dbcore query parsing helpers."""

import unittest

import pytest

from beets import dbcore
from beets.dbcore import ModelQuery, query, sort
from beets.test.fixtures import ModelFixture1, SortFixture


class QueryParseTest(unittest.TestCase):
    def pqp(self, part):
        term = dbcore.queryparse.QueryTerm.make(part)
        return term.field, term.pattern, term.get_query_cls(ModelFixture1)

    def test_one_basic_term(self):
        q = "test"
        r = (None, "test", query.SubstringQuery)
        assert self.pqp(q) == r

    def test_one_keyed_term(self):
        q = "test:val"
        r = ("test", "val", query.SubstringQuery)
        assert self.pqp(q) == r

    def test_colon_at_end(self):
        q = "test:"
        r = ("test", "", query.SubstringQuery)
        assert self.pqp(q) == r

    def test_one_basic_regexp(self):
        q = r":regexp"
        r = (None, "regexp", query.RegexpQuery)
        assert self.pqp(q) == r

    def test_keyed_regexp(self):
        q = r"test::regexp"
        r = ("test", "regexp", query.RegexpQuery)
        assert self.pqp(q) == r

    def test_escaped_colon(self):
        q = r"test\:val"
        r = (None, "test:val", query.SubstringQuery)
        assert self.pqp(q) == r

    def test_escaped_colon_in_regexp(self):
        q = r":test\:regexp"
        r = (None, "test:regexp", query.RegexpQuery)
        assert self.pqp(q) == r

    def test_single_year(self):
        q = "year:1999"
        r = ("year", "1999", query.NumericQuery)
        assert self.pqp(q) == r

    def test_multiple_years(self):
        q = "year:1999..2010"
        r = ("year", "1999..2010", query.NumericQuery)
        assert self.pqp(q) == r

    def test_empty_query_part(self):
        q = ""
        r = (None, "", query.SubstringQuery)
        assert self.pqp(q) == r

    def test_implicit_path(self):
        q = "/tmp"
        r = ("path", "/tmp", dbcore.query.PathQuery)
        assert self.pqp(q) == r


class QueryFromStringsTest(unittest.TestCase):
    def qfs(self, strings):
        return dbcore.queryparse.build_and_query(ModelFixture1, strings)

    def test_zero_parts(self):
        q = self.qfs([])
        assert isinstance(q, query.TrueQuery)

    def test_two_parts(self):
        q = self.qfs(["foo", "bar:baz"])
        assert isinstance(q, query.AndQuery)
        assert len(q.subqueries) == 2
        assert isinstance(q.subqueries[0], query.OrQuery)
        assert isinstance(q.subqueries[1], query.SubstringQuery)

    def test_parse_fixed_type_query(self):
        q = self.qfs(["field_one:2..3"])
        assert isinstance(q, query.NumericQuery)

    def test_parse_flex_type_query(self):
        q = self.qfs(["some_float_field:2..3"])
        assert isinstance(q, query.NumericQuery)

    def test_empty_query_part(self):
        q = self.qfs([""])
        assert isinstance(q, query.TrueQuery)


class SortFromStringsTest(unittest.TestCase):
    def sfs(self, strings):
        return dbcore.queryparse.sort_from_strings(ModelFixture1, strings)

    def test_zero_parts(self):
        s = self.sfs([])
        assert isinstance(s, sort.NullSort)
        assert s == sort.NullSort()

    def test_one_parts(self):
        s = self.sfs(["field+"])
        assert isinstance(s, sort.Sort)

    def test_two_parts(self):
        s = self.sfs(["field+", "another_field-"])
        assert isinstance(s, sort.MultipleSort)
        assert len(s.sorts) == 2

    def test_fixed_field_sort(self):
        s = self.sfs(["field_one+"])
        assert isinstance(s, sort.FixedFieldSort)
        assert s == sort.FixedFieldSort("field_one")

    def test_flex_field_sort(self):
        s = self.sfs(["flex_field+"])
        assert isinstance(s, sort.SlowFieldSort)
        assert s == sort.SlowFieldSort("flex_field")

    def test_special_sort(self):
        s = self.sfs(["some_sort+"])
        assert isinstance(s, SortFixture)


class ParseSortedQueryTest(unittest.TestCase):
    def psq(self, parts):
        return dbcore.parse_sorted_query(ModelFixture1, parts.split())

    def test_and_query(self):
        q, s = self.psq("foo bar")
        assert isinstance(q, query.AndQuery)
        assert isinstance(s, sort.NullSort)
        assert len(q.subqueries) == 2

    def test_or_query(self):
        q, s = self.psq("foo , bar")
        assert isinstance(q, query.OrQuery)
        assert isinstance(s, sort.NullSort)
        assert len(q.subqueries) == 4

    def test_no_space_before_comma_or_query(self):
        q, s = self.psq("foo, bar")
        assert isinstance(q, query.AndQuery)
        assert isinstance(q.subqueries[0], query.OrQuery)
        assert isinstance(q.subqueries[1], query.OrQuery)
        assert len(q.subqueries[0].subqueries) == 2
        assert len(q.subqueries[1].subqueries) == 2
        assert isinstance(s, sort.NullSort)

    def test_no_spaces_or_query(self):
        q, s = self.psq("foo,bar")
        assert isinstance(q, query.OrQuery)
        assert isinstance(s, sort.NullSort)
        assert len(q.subqueries) == 2

    def test_trailing_comma_or_query(self):
        q, s = self.psq("foo , bar ,")
        assert isinstance(q, query.OrQuery)
        assert isinstance(s, sort.NullSort)
        assert len(q.subqueries) == 5

    def test_leading_comma_or_query(self):
        q, s = self.psq(", foo , bar")
        assert isinstance(q, query.OrQuery)
        assert isinstance(s, sort.NullSort)
        assert len(q.subqueries) == 5

    def test_only_direction(self):
        q, s = self.psq("-")
        assert isinstance(q, query.NotQuery)
        assert isinstance(s, sort.NullSort)


class ParseQueryTest:
    def test_parse_invalid_query_string(self):
        with pytest.raises(dbcore.query.ParsingError):
            ModelQuery.parse(ModelFixture1, 'foo"')
