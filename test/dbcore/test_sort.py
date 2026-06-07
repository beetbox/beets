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

import os

import pytest

import beets.library
from beets import util
from beets.dbcore import types
from beets.dbcore.query import TrueQuery
from beets.dbcore.sort import FixedFieldSort, SlowFieldSort
from beets.library import Album, Item
from beets.test import _common

_p = pytest.param


def abs_test_path(path: str) -> str:
    return os.fsdecode(util.normpath(path))


@pytest.fixture(scope="class")
def helper(class_helper):
    return class_helper


@pytest.fixture(scope="class")
def setup_library(request: pytest.FixtureRequest, helper):
    album_ids = [
        helper.lib.add(
            Album(
                id=id_,
                album=album,
                genres=genres,
                year=year,
                flex1=flex1,
                flex2=flex2,
                albumartist=albumartist,
            )
        )
        for id_, album, genres, year, flex1, flex2, albumartist in (
            [1, "Album A", ["Rock"], 2001, "Flex1-1", "Flex2-A", "Foo"],
            [2, "Album B", ["Rock"], 2002, "Flex1-2", "Flex2-A", "Bar"],
            [3, "Album C", ["Jazz"], 2005, "Flex1-1", "Flex2-B", "Baz"],
        )
    ]

    for item in [
        _common.item(
            id=1,
            title="first",
            artist="One",
            album="Album A",
            year=2001,
            flex1="Flex1-0",
            flex2="Flex2-A",
            album_id=album_ids[0],
            path=abs_test_path("/path0.mp3"),
            track=1,
        ),
        _common.item(
            id=2,
            title="second",
            artist="Two",
            album="Album A",
            year=2002,
            flex1="Flex1-1",
            flex2="Flex2-A",
            album_id=album_ids[0],
            path=abs_test_path("/patH1.mp3"),
            track=2,
        ),
        _common.item(
            id=3,
            title="third",
            artist="Three",
            album="Album B",
            year=2003,
            flex1="Flex1-2",
            flex2="Flex1-B",
            album_id=album_ids[1],
            path=abs_test_path("/paTH2.mp3"),
            track=3,
        ),
        _common.item(
            id=4,
            title="fourth",
            artist="Three",
            album="Album C",
            year=2004,
            flex1="Flex1-2",
            flex2="Flex1-C",
            album_id=album_ids[2],
            path=abs_test_path("/PATH3.mp3"),
            track=4,
        ),
    ]:
        helper.lib.add(item)

    request.cls.lib = helper.lib


@pytest.mark.usefixtures("setup_library")
class TestSort:
    @pytest.mark.parametrize(
        "model,query,expected_ids",
        [
            _p(Album, "year+", [1, 2, 3], id="album-fixed"),
            _p(Album, "flex1+", [1, 3, 2], id="album-flex"),
            _p(Album, "path+", [1, 2, 3], id="album-calculated"),
            _p(Album, "year-", [3, 2, 1], id="album-fixed-desc"),
            _p(Album, "flex1-", [2, 1, 3], id="album-flex-desc"),
            _p(Album, "path-", [1, 2, 3], id="album-calculated-desc"),
            _p(Album, "genres+ album+", [3, 1, 2], id="multi-album-fixed-field-asc"),
            _p(Album, "flex2+ flex1+", [1, 2, 3], id="multi-album-flex-field-asc"),
            _p(Album, "path+ year+", [1, 2, 3], id="computed"),
            _p(Album, "year+ path+", [1, 2, 3], id="computed-reverse"),
            _p(Item, "year+", [1, 2, 3, 4], id="item-fixed"),
            _p(Item, "flex1+", [1, 2, 3, 4], id="item-flex"),
            _p(Item, "year-", [4, 3, 2, 1], id="item-fixed-desc"),
            _p(Item, "flex1-", [3, 4, 2, 1], id="item-flex-desc"),
            _p(Item, "album+ year+", [1, 2, 3, 4], id="multi-item-fixed-field-asc"),
            _p(Item, "flex2- flex1+", [1, 2, 4, 3], id="multi-flex-field-mixed"),
        ],
    )  # fmt: skip
    def test_sort(self, model, query, expected_ids):
        results = self.lib._fetch(model, query, None)
        assert [r.id for r in results] == expected_ids

    def test_sort_path_field(self):
        results = self.lib.items("", FixedFieldSort("path", True))
        expected_paths = [
            b"/path0.mp3",
            b"/patH1.mp3",
            b"/paTH2.mp3",
            b"/PATH3.mp3",
        ]
        expected_paths_with_prefix = list(map(util.normpath, expected_paths))
        assert [i.path for i in results] == expected_paths_with_prefix

    def test_config_defaults(self):
        artists = [r.artist for r in self.lib.items()]
        albumartists = [r.albumartist for r in self.lib.albums()]

        assert artists == ["One", "Three", "Three", "Two"]
        assert albumartists == ["Bar", "Baz", "Foo"]

    def test_config_overrides(self, config):
        config.set({"sort_item": "artist-", "sort_album": "albumartist-"})

        artists = [r.artist for r in self.lib.items()]
        albumartists = [r.albumartist for r in self.lib.albums()]

        assert artists == ["Two", "Three", "Three", "One"]
        assert albumartists == ["Foo", "Baz", "Bar"]


class TestCaseSensitivity:
    """If case_insensitive is false, lower-case values should be placed
    after all upper-case values. E.g., `Foo Qux bar`
    """

    @pytest.fixture(autouse=True, scope="class")
    def setup(self, helper):
        helper.lib.add(Album(album="album", albumartist="bar"))
        helper.lib.add(Album(album="Album", albumartist="Bar"))
        helper.add_item(artist="artist", flex1="flex1", track=10)
        helper.add_item(artist="Artist", flex1="Flex1", track=2)

    @pytest.mark.parametrize(
        "getter,query,attr,expected_insensitive,expected_sensitive",
        [
            _p(
                "items",
                "artist+",
                "artist",
                ["artist", "Artist"],
                ["Artist", "artist"],
                id="smart-artist-case",
            ),
            _p(
                "albums",
                "album+",
                "album",
                ["album", "Album"],
                ["Album", "album"],
                id="fixed-field-case",
            ),
            _p(
                "items",
                "flex1+",
                "flex1",
                ["flex1", "Flex1"],
                ["Flex1", "flex1"],
                id="flex-field-case",
            ),
        ],
    )
    def test_text_field_case_sorting(
        self,
        config,
        getter,
        query,
        attr,
        expected_insensitive,
        expected_sensitive,
        helper,
    ):
        config["sort_case_insensitive"] = True
        results = getattr(helper.lib, getter)(query)
        assert [r[attr] for r in results] == expected_insensitive

        config["sort_case_insensitive"] = False
        results = getattr(helper.lib, getter)(query)
        assert [r[attr] for r in results] == expected_sensitive

    def test_case_sensitive_only_affects_text(self, config, helper):
        config["sort_case_insensitive"] = True
        results = helper.lib.items("track+")
        # If the numerical values were sorted as strings,
        # then ['10', '2'] would be valid.
        assert [r.track for r in results] == [2, 10]


@pytest.mark.usefixtures("setup_library")
class TestNonExistingField:
    """Test sorting by non-existing fields"""

    @pytest.mark.parametrize(
        "q", ["foo+", "foo-", "--", "-+", "+-", "++", "-foo-", "-foo+", "---"]
    )
    def test_non_existing_fields_not_fail(self, q):
        expected_ids = [i.id for i in self.lib.items("foo+")]

        actual_ids = [i.id for i in self.lib.items(q)]

        assert actual_ids == expected_ids

    @pytest.mark.parametrize("q", ["foo+ id+", "foo- id+"], ids=["asc", "desc"])
    def test_combined_non_existing_field(self, q):
        expected_ids = [i.id for i in self.lib.items("id+")]

        actual_ids = [i.id for i in self.lib.items(q)]

        assert actual_ids == expected_ids

    @pytest.mark.parametrize(
        "field,values",
        [_p("myint", (2, 10), id="int"), _p("foo", ("bar1", "bar2"), id="str")],
    )
    def test_field_present_in_some_items(self, monkeypatch, field, values):
        """Test ordering by an int-type field not present on all items."""
        monkeypatch.setitem(Item._types, "myint", types.Integer())

        lower_item, higher_item, *items_without_val = self.lib.items("id+")
        for item, value in zip((lower_item, higher_item), values):
            setattr(item, field, value)
            item.store()

        null_values_ids = [i.id for i in items_without_val]

        ids_asc = [i.id for i in self.lib.items(f"{field}+ id+")]
        ids_desc = [i.id for i in self.lib.items(f"{field}- id+")]

        assert ids_asc == [*null_values_ids, lower_item.id, higher_item.id]
        assert ids_desc == [higher_item.id, lower_item.id, *null_values_ids]

    def test_negation_interaction(self):
        """Test the handling of negation and sorting together.

        If a string ends with a sorting suffix, it takes precedence over the
        NotQuery parsing.
        """
        query, sort = beets.library.parse_query_string(
            "-bar+", beets.library.Item
        )
        assert len(query.subqueries) == 1
        assert isinstance(query.subqueries[0], TrueQuery)
        assert isinstance(sort, SlowFieldSort)
        assert sort.field == "-bar"
