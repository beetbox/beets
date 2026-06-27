"""Tests for dbcore query parsing helpers."""

import pytest

from beets.dbcore import ModelQuery, query, sort
from beets.dbcore.queryparse import QueryTerm
from beets.test.fixtures import ModelFixture1, SortFixture

_p = pytest.param


def _parse_query_parts(parts: list[str]):
    return ModelFixture1.parse_query(parts).query


def _parse_sort_parts(parts: list[str]):
    return ModelFixture1.parse_query(parts).sort


class TestQueryTermParsing:
    @pytest.mark.parametrize(
        "query_string,expected",
        [
            ("test", (None, "test", query.SubstringQuery)),
            ("test:val", ("test", "val", query.SubstringQuery)),
            ("test:", ("test", "", query.SubstringQuery)),
            (r":regexp", (None, "regexp", query.RegexpQuery)),
            (r"test::regexp", ("test", "regexp", query.RegexpQuery)),
            (r"test\:val", (None, "test:val", query.SubstringQuery)),
            (r":test\:regexp", (None, "test:regexp", query.RegexpQuery)),
            ("year:1999", ("year", "1999", query.NumericQuery)),
            ("year:1999..2010", ("year", "1999..2010", query.NumericQuery)),
            ("", (None, "", query.SubstringQuery)),
            ("/tmp", ("path", "/tmp", query.PathQuery)),
        ],
    )
    def test_query_term_parsing(self, query_string, expected):
        """Test that various query strings are parsed correctly."""
        term = QueryTerm.make(query_string)
        result = term.field, term.pattern, term.get_query_cls(ModelFixture1)
        assert result == expected


class TestQueryFromParts:
    @pytest.mark.parametrize(
        "query_parts,expected_type",
        [
            _p([], query.TrueQuery, id="zero_parts"),
            _p([""], query.TrueQuery, id="empty_query_part"),
            _p(["field_one:2..3"], query.NumericQuery, id="fixed_type_query"),
            _p(
                ["some_float_field:2..3"],
                query.NumericQuery,
                id="flex_type_query",
            ),
        ],
    )
    def test_query_from_parts_types(self, query_parts, expected_type):
        q = _parse_query_parts(query_parts)
        assert isinstance(q, expected_type)

    def test_query_from_two_parts_builds_and_query(self):
        q = _parse_query_parts(["foo", "bar:baz"])
        assert isinstance(q, query.AndQuery)
        assert len(q.subqueries) == 2
        assert isinstance(q.subqueries[0], query.OrQuery)
        assert isinstance(q.subqueries[1], query.SubstringQuery)


class TestSortFromParts:
    def test_sort_from_zero_parts(self):
        s = _parse_sort_parts([])
        assert isinstance(s, sort.NullSort)
        assert s == sort.NullSort()

    def test_sort_from_one_part(self):
        s = _parse_sort_parts(["field+"])
        assert isinstance(s, sort.Sort)

    def test_sort_from_two_parts(self):
        s = _parse_sort_parts(["field+", "another_field-"])
        assert isinstance(s, sort.MultipleSort)
        assert len(s.sorts) == 2

    @pytest.mark.parametrize(
        "sort_parts,expected_type,expected_sort",
        [
            _p(
                ["field_one+"],
                sort.FixedFieldSort,
                sort.FixedFieldSort("field_one"),
                id="fixed_field_sort",
            ),
            _p(
                ["flex_field+"],
                sort.SlowFieldSort,
                sort.SlowFieldSort("flex_field"),
                id="flex_field_sort",
            ),
            _p(["some_sort+"], SortFixture, None, id="special_sort"),
        ],
    )
    def test_sort_from_parts_types(
        self, sort_parts, expected_type, expected_sort
    ):
        s = _parse_sort_parts(sort_parts)
        assert isinstance(s, expected_type)
        if expected_sort is not None:
            assert s == expected_sort


class TestParseSortedQuery:
    @pytest.mark.parametrize(
        "query_str,expected_type,expected_subqueries",
        [
            _p("foo bar", query.AndQuery, 2, id="and_query"),
            _p("foo , bar", query.OrQuery, 4, id="or_query"),
            _p("foo, bar", query.OrQuery, 4, id="no_space_before_comma_or_query"),
            _p("foo,bar", query.OrQuery, 2, id="no_spaces_or_query"),
            _p("foo , bar ,", query.OrQuery, 5, id="trailing_comma_or_query"),
            _p(", foo , bar", query.OrQuery, 5, id="leading_comma_or_query"),
            _p("-", query.NotQuery, None, id="only_direction"),
        ],
    )  # fmt: skip
    def test_parse_sorted_query(
        self, query_str, expected_type, expected_subqueries
    ):
        """Verify that query strings are parsed into the correct query type."""
        q = _parse_query_parts(query_str.split())
        assert isinstance(q, expected_type)
        if expected_subqueries is not None:
            assert len(q.subqueries) == expected_subqueries


class TestModelQueryErrors:
    def test_parse_invalid_query_string(self):
        with pytest.raises(query.ParsingError):
            ModelQuery.parse(ModelFixture1, 'foo"')
