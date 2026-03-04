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

"""Various tests for querying the library database."""

import sys
from functools import partial
from pathlib import Path

import pytest

from beets.dbcore import types
from beets.dbcore.query import (
    AndQuery,
    BooleanQuery,
    DateQuery,
    FalseQuery,
    MatchQuery,
    NoneQuery,
    NotQuery,
    NumericQuery,
    OrQuery,
    ParsingError,
    PathQuery,
    RegexpQuery,
    StringFieldQuery,
    StringQuery,
    SubstringQuery,
    TrueQuery,
)
from beets.library import Item
from beets.test import _common
from beets.test.helper import TestHelper

# Because the absolute path begins with something like C:, we
# can't disambiguate it from an ordinary query.
WIN32_NO_IMPLICIT_PATHS = "Implicit paths are not supported on Windows"

_p = pytest.param


@pytest.fixture(scope="class")
def helper():
    helper = TestHelper()
    helper.setup_beets()

    yield helper

    helper.teardown_beets()


class TestGet:
    @pytest.fixture(scope="class")
    def lib(self, helper):
        album_items = [
            helper.create_item(
                title="first",
                artist="one",
                artists=["one", "eleven"],
                album="baz",
                year=2001,
                comp=True,
                genres=["rock"],
            ),
            helper.create_item(
                title="second",
                artist="two",
                artists=["two", "twelve"],
                album="baz",
                year=2002,
                comp=True,
                genres=["Rock"],
            ),
        ]
        album = helper.lib.add_album(album_items)
        album.albumflex = "foo"
        album.store()

        helper.add_item(
            title="third",
            artist="three",
            artists=["three", "one"],
            album="foo",
            year=2003,
            comp=False,
            genres=["Hard Rock"],
            comments="caf\xe9",
        )

        return helper.lib

    @pytest.mark.parametrize(
        "q, expected_titles",
        [
            ("", ["first", "second", "third"]),
            (None, ["first", "second", "third"]),
            (":oNE", []),
            (":one", ["first"]),
            (":sec :ond", ["second"]),
            (":second", ["second"]),
            ("=rock", ["first"]),
            ('=~"hard rock"', ["third"]),
            (":t$", ["first"]),
            ("oNE", ["first"]),
            ("baz", ["first", "second"]),
            ("sec ond", ["second"]),
            ("three", ["third"]),
            ("albumflex:foo", ["first", "second"]),
            ("artist::t.+r", ["third"]),
            ("artist:thrEE", ["third"]),
            ("artists::eleven", ["first"]),
            ("artists::one", ["first", "third"]),
            ("ArTiST:three", ["third"]),
            ("comments:caf\xe9", ["third"]),
            ("comp:true", ["first", "second"]),
            ("comp:false", ["third"]),
            ("genres:=rock", ["first"]),
            ("genres:=Rock", ["second"]),
            ('genres:="Hard Rock"', ["third"]),
            ('genres:=~"hard rock"', ["third"]),
            ("genres:=~rock", ["first", "second"]),
            ('genres:="hard rock"', []),
            ("popebear", []),
            ("pope:bear", []),
            ("singleton:true", ["third"]),
            ("singleton:1", ["third"]),
            ("singleton:false", ["first", "second"]),
            ("singleton:0", ["first", "second"]),
            ("title:ond", ["second"]),
            ("title::sec", ["second"]),
            ("year:2001", ["first"]),
            ("year:2000..2002", ["first", "second"]),
            ("xyzzy:nonsense", []),
        ],
    )
    def test_get_query(self, lib, q, expected_titles):
        assert {i.title for i in lib.items(q)} == set(expected_titles)

    @pytest.mark.parametrize(
        "q, expected_titles",
        [
            (BooleanQuery("comp", True), ("third",)),
            (DateQuery("added", "2000-01-01"), ("first", "second", "third")),
            (FalseQuery(), ("first", "second", "third")),
            (MatchQuery("year", "2003"), ("first", "second")),
            (NoneQuery("rg_track_gain"), ()),
            (NumericQuery("year", "2001..2002"), ("third",)),
            (
                AndQuery(
                    [BooleanQuery("comp", True), NumericQuery("year", "2002")]
                ),
                ("first", "third"),
            ),
            (
                OrQuery(
                    [BooleanQuery("comp", True), NumericQuery("year", "2002")]
                ),
                ("third",),
            ),
            (RegexpQuery("artist", "^t"), ("first",)),
            (SubstringQuery("album", "ba"), ("third",)),
            (TrueQuery(), ()),
        ],
    )
    def test_query_logic(self, lib, q, expected_titles):
        def get_results(*args):
            return {i.title for i in lib.items(*args)}

        # not(a and b) <-> not(a) or not(b)
        not_q = NotQuery(q)
        not_q_results = get_results(not_q)
        assert not_q_results == set(expected_titles)

        # assert using OrQuery, AndQuery
        q_or = OrQuery([q, not_q])

        q_and = AndQuery([q, not_q])
        assert get_results(q_or) == {"first", "second", "third"}
        assert get_results(q_and) == set()

        # assert manually checking the item titles
        all_titles = get_results()
        q_results = get_results(q)
        assert q_results.union(not_q_results) == all_titles
        assert q_results.intersection(not_q_results) == set()

        # round trip
        not_not_q = NotQuery(not_q)
        assert get_results(q) == get_results(not_not_q)

    @pytest.mark.parametrize(
        "q, expected_titles",
        [
            ("-artist::t.+r", ["first", "second"]),
            ("-:t$", ["second", "third"]),
            ("sec -bar", ["second"]),
            ("sec -title:bar", ["second"]),
            ("-ond", ["first", "third"]),
            ("^ond", ["first", "third"]),
            ("^title:sec", ["first", "third"]),
            ("-title:sec", ["first", "third"]),
        ],
    )
    def test_negation_prefix(self, lib, q, expected_titles):
        actual_titles = {i.title for i in lib.items(q)}
        assert actual_titles == set(expected_titles)

    @pytest.mark.parametrize(
        "make_q",
        [
            partial(DateQuery, "added", "2001-01-01"),
            partial(MatchQuery, "artist", "one"),
            partial(NoneQuery, "rg_track_gain"),
            partial(NumericQuery, "year", "2002"),
            partial(StringQuery, "year", "2001"),
            partial(RegexpQuery, "album", "^.a"),
            partial(SubstringQuery, "title", "x"),
        ],
    )
    def test_fast_vs_slow(self, lib, make_q):
        """Test that the results are the same regardless of the `fast` flag
        for negated `FieldQuery`s.
        """
        q_fast = make_q(True)
        q_slow = make_q(False)

        assert list(map(dict, lib.items(q_fast))) == list(
            map(dict, lib.items(q_slow))
        )


class TestMatch:
    @pytest.fixture(scope="class")
    def item(self):
        return _common.item(album="the album", disc=6, year=1, bitrate=128000)

    @pytest.mark.parametrize(
        "q, should_match",
        [
            (RegexpQuery("album", "^the album$"), True),
            (RegexpQuery("album", "^album$"), False),
            (RegexpQuery("disc", "^6$"), True),
            (SubstringQuery("album", "album"), True),
            (SubstringQuery("album", "ablum"), False),
            (SubstringQuery("disc", "6"), True),
            (StringQuery("album", "the album"), True),
            (StringQuery("album", "THE ALBUM"), True),
            (StringQuery("album", "album"), False),
            (NumericQuery("year", "1"), True),
            (NumericQuery("year", "10"), False),
            (NumericQuery("bitrate", "100000..200000"), True),
            (NumericQuery("bitrate", "200000..300000"), False),
            (NumericQuery("bitrate", "100000.."), True),
        ],
    )
    def test_match(self, item, q, should_match):
        assert q.match(item) == should_match
        assert not NotQuery(q).match(item) == should_match


class TestPathQuery:
    """Tests for path-based querying functionality in the database system.

    Verifies that path queries correctly match items by their file paths,
    handling special characters, case sensitivity, parent directories,
    and path separator detection across different platforms.
    """

    @pytest.fixture(scope="class")
    def lib(self, helper):
        helper.add_item(path=b"/aaa/bb/c.mp3", title="path item")
        helper.add_item(path=b"/x/y/z.mp3", title="another item")
        helper.add_item(path=b"/c/_/title.mp3", title="with underscore")
        helper.add_item(path=b"/c/%/title.mp3", title="with percent")
        helper.add_item(path=rb"/c/\x/title.mp3", title="with backslash")
        helper.add_item(path=b"/A/B/C2.mp3", title="caps path")

        return helper.lib

    @pytest.mark.parametrize(
        "q, expected_titles",
        [
            _p("path:/aaa/bb/c.mp3", ["path item"], id="exact-match"),
            _p("path:/aaa", ["path item"], id="parent-dir-no-slash"),
            _p("path:/aaa/", ["path item"], id="parent-dir-with-slash"),
            _p("path:/aa", [], id="no-match-does-not-match-parent-dir"),
            _p("path:/xyzzy/", [], id="no-match"),
            _p("path:/b/", [], id="fragment-no-match"),
            _p("path:/x/../aaa/bb", ["path item"], id="non-normalized"),
            _p("path::c\\.mp3$", ["path item"], id="regex"),
            _p("path:/c/_", ["with underscore"], id="underscore-escaped"),
            _p("path:/c/%", ["with percent"], id="percent-escaped"),
            _p("path:/c/\\\\x", ["with backslash"], id="backslash-escaped"),
        ],
    )
    def test_explicit(self, monkeypatch, lib, q, expected_titles):
        """Test explicit path queries with different path specifications."""
        monkeypatch.setattr("beets.util.case_sensitive", lambda *_: True)

        assert {i.title for i in lib.items(q)} == set(expected_titles)

    @pytest.mark.skipif(sys.platform == "win32", reason=WIN32_NO_IMPLICIT_PATHS)
    @pytest.mark.parametrize(
        "q, expected_titles",
        [
            _p("/aaa/bb", ["path item"], id="slashed-query"),
            _p("/aaa/bb , /aaa", ["path item"], id="path-in-or-query"),
            _p("c.mp3", [], id="no-slash-no-match"),
            _p("title:/a/b", [], id="slash-with-explicit-field-no-match"),
        ],
    )
    def test_implicit(self, monkeypatch, lib, q, expected_titles):
        """Test implicit path detection when queries contain path separators."""
        monkeypatch.setattr(
            "beets.dbcore.query.PathQuery.is_path_query", lambda path: True
        )

        assert {i.title for i in lib.items(q)} == set(expected_titles)

    @pytest.mark.parametrize(
        "case_sensitive, expected_titles",
        [
            _p(True, [], id="non-caps-dont-match-caps"),
            _p(False, ["caps path"], id="non-caps-match-caps"),
        ],
    )
    def test_case_sensitivity(
        self, lib, monkeypatch, case_sensitive, expected_titles
    ):
        """Test path matching with different case sensitivity settings."""
        q = "path:/a/b/c2.mp3"
        monkeypatch.setattr(
            "beets.util.case_sensitive", lambda *_: case_sensitive
        )

        assert {i.title for i in lib.items(q)} == set(expected_titles)

    # FIXME: Also create a variant of this test for windows, which tests
    # both os.sep and os.altsep
    @pytest.mark.skipif(sys.platform == "win32", reason=WIN32_NO_IMPLICIT_PATHS)
    @pytest.mark.parametrize(
        "q, is_path_query",
        [
            ("/foo/bar", True),
            ("foo/bar", True),
            ("foo/", True),
            ("foo", False),
            ("foo/:bar", True),
            ("foo:bar/", False),
            ("foo:/bar", False),
        ],
    )
    def test_path_sep_detection(self, monkeypatch, tmp_path, q, is_path_query):
        """Test detection of path queries based on the presence of path separators."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "foo").mkdir()
        (tmp_path / "foo" / "bar").touch()
        if Path(q).is_absolute():
            q = str(tmp_path / q[1:])

        assert PathQuery.is_path_query(q) == is_path_query


class TestQuery:
    ALBUM = "album title"
    SINGLE = "singleton"

    @pytest.fixture(scope="class")
    def lib(self, helper):
        helper.add_album(
            title=self.ALBUM,
            comp=True,
            flexbool=True,
            bpm=120,
            flexint=2,
            rg_track_gain=0,
        )
        helper.add_item(
            title=self.SINGLE, comp=False, flexbool=False, rg_track_gain=None
        )

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                Item,
                "_types",
                {"flexbool": types.Boolean(), "flexint": types.Integer()},
            )
            yield helper.lib

    @pytest.mark.parametrize("query_class", [MatchQuery, StringFieldQuery])
    def test_equality(self, query_class):
        assert query_class("foo", "bar") == query_class("foo", "bar")

    @pytest.mark.parametrize(
        "make_q, expected_msg",
        [
            (lambda: NumericQuery("year", "199a"), "not an int"),
            (lambda: RegexpQuery("year", "199("), r"not a regular expression.*unterminated subpattern"),  # noqa: E501
        ]
    )  # fmt: skip
    def test_invalid_query(self, make_q, expected_msg):
        with pytest.raises(ParsingError, match=expected_msg):
            make_q()

    @pytest.mark.parametrize(
        "q, expected_titles",
        [
            # Boolean value
            _p("comp:true", {ALBUM}, id="parse-true"),
            _p("flexbool:true", {ALBUM}, id="flex-parse-true"),
            _p("flexbool:false", {SINGLE}, id="flex-parse-false"),
            _p("flexbool:1", {ALBUM}, id="flex-parse-1"),
            _p("flexbool:0", {SINGLE}, id="flex-parse-0"),
            # TODO: shouldn't this match 1 / true instead?
            _p("flexbool:something", {SINGLE}, id="flex-parse-true"),
            # Integer value
            _p("bpm:120", {ALBUM}, id="int-exact-value"),
            _p("bpm:110..125", {ALBUM}, id="int-range"),
            _p("flexint:2", {ALBUM}, id="int-flex"),
            _p("flexint:3", set(), id="int-no-match"),
            _p("bpm:12", set(), id="int-dont-match-substring"),
            # None value
            _p(NoneQuery("album_id"), {SINGLE}, id="none-match-singleton"),
            _p(NoneQuery("rg_track_gain"), {SINGLE}, id="none-value"),
        ],
    )
    def test_value_type(self, lib, q, expected_titles):
        assert {i.title for i in lib.items(q)} == expected_titles


class TestDefaultSearchFields:
    @pytest.fixture(scope="class")
    def lib(self, helper):
        helper.add_album(
            title="title",
            album="album",
            albumartist="albumartist",
            catalognum="catalognum",
            year=2001,
        )

        return helper.lib

    @pytest.mark.parametrize(
        "entity, q, should_match",
        [
            _p("albums", "album", True, id="album-match-album"),
            _p("albums", "albumartist", True, id="album-match-albumartist"),
            _p("albums", "catalognum", False, id="album-dont-match-catalognum"),
            _p("items", "title", True, id="item-match-title"),
            _p("items", "2001", False, id="item-dont-match-year"),
        ],
    )
    def test_search(self, lib, entity, q, should_match):
        assert bool(getattr(lib, entity)(q)) == should_match


class TestRelatedQueries:
    """Test album-level queries with track-level filters and vice-versa."""

    @pytest.fixture(scope="class")
    def lib(self, helper):
        for album_idx in range(1, 3):
            album_name = f"Album{album_idx}"
            items = [
                helper.create_item(
                    album=album_name, title=f"{album_name} Item{idx}"
                )
                for idx in range(1, 3)
            ]
            album = helper.lib.add_album(items)
            album.artpath = f"{album_name} Artpath"
            album.catalognum = "ABC"
            album.store()

        return helper.lib

    @pytest.mark.parametrize(
        "q, expected_titles, expected_albums",
        [
            _p(
                "title:Album1",
                ["Album1 Item1", "Album1 Item2"],
                ["Album1"],
                id="match-album-with-item-field-query",
            ),
            _p(
                "title:Item2",
                ["Album1 Item2", "Album2 Item2"],
                ["Album1", "Album2"],
                id="match-albums-with-item-field-query",
            ),
            _p(
                "artpath::Album1",
                ["Album1 Item1", "Album1 Item2"],
                ["Album1"],
                id="match-items-with-album-field-query",
            ),
            _p(
                "catalognum:ABC Album1",
                ["Album1 Item1", "Album1 Item2"],
                ["Album1"],
                id="query-field-common-to-album-and-item",
            ),
        ],
    )
    def test_related_query(self, lib, q, expected_titles, expected_albums):
        assert {i.album for i in lib.albums(q)} == set(expected_albums)
        assert {i.title for i in lib.items(q)} == set(expected_titles)
