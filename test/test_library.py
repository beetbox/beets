"""Tests for non-query database functions of Item."""

from __future__ import annotations

import os
import os.path
import re
import shutil
import stat
import unittest
from unittest.mock import patch

import mutagen
import pytest
from mediafile import MediaFile, UnreadableFileError

import beets.dbcore.query
import beets.library
from beets import config, plugins, util
from beets.library import Album
from beets.test import _common
from beets.test._common import item
from beets.test.helper import TestHelper
from beets.util import (
    as_string,
    bytestring_path,
    normpath,
    path_as_posix,
    syspath,
)

# Shortcut to path normalization.
np = util.normpath


class PytestItemHelper(TestHelper):
    def get_first_item(self):
        """Retrieve first item from library."""
        return next(iter(self.lib.items()))

    @pytest.fixture
    def item(self):
        return _common.item()

    @pytest.fixture
    def item_in_db(self):
        return _common.item(self.lib)


class TestLoad(PytestItemHelper):
    def test_load_restores_data_from_db(self, item_in_db):
        original_title = item_in_db.title
        item_in_db.title = "something"
        item_in_db.load()
        assert original_title == item_in_db.title

    def test_load_clears_dirty_flags(self, item_in_db):
        item_in_db.artist = "something"
        assert "artist" in item_in_db._dirty
        item_in_db.load()
        assert "artist" not in item_in_db._dirty


class TestStore(PytestItemHelper):
    def test_store_changes_database_value(self, item_in_db):
        new_year = 1987
        item_in_db.year = new_year
        item_in_db.store()

        assert self.lib.get_item(item_in_db.id).year == new_year

    def test_store_only_writes_dirty_fields(self, item_in_db):
        new_year = 1987
        item_in_db._values_fixed["year"] = new_year  # change w/o dirtying
        item_in_db.store()

        assert self.lib.get_item(item_in_db.id).year != new_year

    def test_store_clears_dirty_flags(self, item_in_db):
        item_in_db.composers = ["tvp"]
        item_in_db.store()
        assert "composers" not in item_in_db._dirty

    def test_store_album_cascades_flex_deletes(self):
        album = Album(flex1="Flex-1")
        self.lib.add(album)
        item = _common.item()
        item.album_id = album.id
        item.flex1 = "Flex-1"
        self.lib.add(item)
        del album.flex1
        album.store()
        assert "flex1" not in album
        assert "flex1" not in album.items()[0]

    def test_store_does_not_propagate_artpath_to_items(self):
        item = _common.item()
        self.lib.add(item)
        album = self.lib.add_album([item])
        assert "artpath" not in Album.item_keys
        album.artpath = b"/abs/path/to/cover.jpg"
        album.store()
        stored = self.lib.get_item(item.id)
        assert not stored.get("artpath", with_album=False)


class TestAdd(PytestItemHelper):
    def test_item_add_inserts_row(self, item):
        self.lib.add(item)
        new_grouping = (
            self.lib._connection()
            .execute(
                "select grouping from items where composers = ?",
                (item._type("composers").to_sql(item.composers),),
            )
            .fetchone()["grouping"]
        )
        assert new_grouping == item.grouping

    def test_library_add_path_inserts_row(self):
        item = beets.library.Item.from_path(
            os.path.join(_common.RSRC, b"full.mp3")
        )
        self.lib.add(item)
        new_grouping = (
            self.lib._connection()
            .execute(
                "select grouping from items where composers = ?",
                (item._type("composers").to_sql(item.composers),),
            )
            .fetchone()["grouping"]
        )
        assert new_grouping == item.grouping

    def test_library_add_one_database_change_event(
        self, item, caplog: pytest.LogCaptureFixture
    ):
        """Test library.add emits only one database_change event."""

        item.path = beets.util.normpath(
            os.path.join(self.temp_dir, b"a", b"b.mp3")
        )
        item.album = "a"
        item.title = "b"

        with caplog.at_level("DEBUG", logger="beets"):
            self.lib.add(item)

        assert caplog.text.count("Sending event: database_change") == 1


class TestRemove(PytestItemHelper):
    def test_remove_deletes_from_db(self, item_in_db):
        item_in_db.remove()
        c = self.lib._connection().execute("select * from items")
        assert c.fetchone() is None


class TestGetSet(PytestItemHelper):
    def test_set_changes_value(self, item):
        item.bpm = 4915
        assert item.bpm == 4915

    def test_set_sets_dirty_flag(self, item):
        item.comp = not item.comp
        assert "comp" in item._dirty

    def test_set_does_not_dirty_if_value_unchanged(self, item):
        item.title = item.title
        assert "title" not in item._dirty

    def test_invalid_field_raises_attributeerror(self, item):
        with pytest.raises(AttributeError):
            item.xyzzy

    def test_album_fallback(self, item_in_db):
        # integration test of item-album fallback
        album = self.lib.add_album([item_in_db])
        album["flex"] = "foo"
        album.store()

        assert "flex" in item_in_db
        assert "flex" not in item_in_db.keys(with_album=False)
        assert item_in_db["flex"] == "foo"
        assert item_in_db.get("flex") == "foo"
        assert item_in_db.get("flex", with_album=False) is None
        assert item_in_db.get("flexx") is None


class TestDestination(PytestItemHelper):
    """Confirm tests handle temporary directory path containing '.'"""

    def create_temp_dir(self, **kwargs):
        kwargs["prefix"] = "."
        return super().create_temp_dir(**kwargs)

    def test_directory_works_with_trailing_slash(self, item_in_db):
        self.lib.directory = b"one/"
        self.lib.path_formats = [("default", "two")]
        assert item_in_db.destination() == np("one/two")

    def test_directory_works_without_trailing_slash(self, item_in_db):
        self.lib.directory = b"one"
        self.lib.path_formats = [("default", "two")]
        assert item_in_db.destination() == np("one/two")

    def test_destination_substitutes_metadata_values(self, item_in_db):
        self.lib.directory = b"base"
        self.lib.path_formats = [("default", "$album/$artist $title")]
        item_in_db.title = "three"
        item_in_db.artist = "two"
        item_in_db.album = "one"
        assert item_in_db.destination() == np("base/one/two three")

    def test_destination_preserves_extension(self, item_in_db):
        self.lib.directory = b"base"
        self.lib.path_formats = [("default", "$title")]
        item_in_db.path = "hey.audioformat"
        assert item_in_db.destination() == np("base/the title.audioformat")

    def test_lower_case_extension(self, item_in_db):
        self.lib.directory = b"base"
        self.lib.path_formats = [("default", "$title")]
        item_in_db.path = "hey.MP3"
        assert item_in_db.destination() == np("base/the title.mp3")

    def test_destination_pads_some_indices(self, item_in_db):
        self.lib.directory = b"base"
        self.lib.path_formats = [
            ("default", "$track $tracktotal $disc $disctotal $bpm")
        ]
        item_in_db.track = 1
        item_in_db.tracktotal = 2
        item_in_db.disc = 3
        item_in_db.disctotal = 4
        item_in_db.bpm = 5
        assert item_in_db.destination() == np("base/01 02 03 04 5")

    def test_destination_pads_date_values(self, item_in_db):
        self.lib.directory = b"base"
        self.lib.path_formats = [("default", "$year-$month-$day")]
        item_in_db.year = 1
        item_in_db.month = 2
        item_in_db.day = 3
        assert item_in_db.destination() == np("base/0001-02-03")

    def test_destination_escapes_slashes(self, item_in_db):
        self.lib.path_formats = [("default", "$artist/$album/$track $title")]
        item_in_db.album = "one/two"
        dest = item_in_db.destination()
        assert b"one" in dest
        assert b"two" in dest
        assert b"one/two" not in dest

    def test_destination_escapes_leading_dot(self, item_in_db):
        self.lib.path_formats = [("default", "$artist/$album/$track $title")]
        item_in_db.album = ".something"
        dest = item_in_db.destination()
        assert b"something" in dest
        assert b"/.something" not in dest

    def test_destination_preserves_legitimate_slashes(self, item_in_db):
        self.lib.path_formats = [("default", "$artist/$album/$track $title")]
        item_in_db.artist = "one"
        item_in_db.album = "two"
        dest = item_in_db.destination()
        assert os.path.join(b"one", b"two") in dest

    def test_destination_long_names_truncated(self, item_in_db):
        item_in_db.title = "X" * 300
        item_in_db.artist = "Y" * 300
        for c in item_in_db.destination().split(util.PATH_SEP):
            assert len(c) <= 255

    def test_destination_long_names_keep_extension(self, item_in_db):
        item_in_db.title = "X" * 300
        item_in_db.path = b"something.extn"
        dest = item_in_db.destination()
        assert dest[-5:] == b".extn"

    def test_distination_windows_removes_both_separators(self, item_in_db):
        item_in_db.title = "one \\ two / three.mp3"
        with _common.platform_windows():
            p = item_in_db.destination()
        assert b"one \\ two" not in p
        assert b"one / two" not in p
        assert b"two \\ three" not in p
        assert b"two / three" not in p

    def test_path_with_format(self, item_in_db):
        self.lib.path_formats = [("default", "$artist/$album ($format)")]
        p = item_in_db.destination()
        assert b"(FLAC)" in p

    def test_heterogeneous_album_gets_single_directory(self):
        i1, i2 = _common.item(self.lib), _common.item(self.lib)
        self.lib.add_album([i1, i2])
        i1.year, i2.year = 2009, 2010
        self.lib.path_formats = [("default", "$album ($year)/$track $title")]
        dest1, dest2 = i1.destination(), i2.destination()
        assert os.path.dirname(dest1) == os.path.dirname(dest2)

    def test_default_path_for_non_compilations(self, item_in_db):
        item_in_db.comp = False
        self.lib.add_album([item_in_db])
        self.lib.directory = b"one"
        self.lib.path_formats = [("default", "two"), ("comp:true", "three")]
        assert item_in_db.destination() == np("one/two")

    def test_singleton_path(self, item_in_db):
        self.lib.directory = b"one"
        self.lib.path_formats = [
            ("default", "two"),
            ("singleton:true", "four"),
            ("comp:true", "three"),
        ]
        assert item_in_db.destination() == np("one/four")

    def test_comp_before_singleton_path(self, item_in_db):
        item_in_db.comp = True
        self.lib.directory = b"one"
        self.lib.path_formats = [
            ("default", "two"),
            ("comp:true", "three"),
            ("singleton:true", "four"),
        ]
        assert item_in_db.destination() == np("one/three")

    def test_comp_path(self, item_in_db):
        item_in_db.comp = True
        self.lib.add_album([item_in_db])
        self.lib.directory = b"one"
        self.lib.path_formats = [("default", "two"), ("comp:true", "three")]
        assert item_in_db.destination() == np("one/three")

    def test_multi_value_string_query_path(self, item_in_db):
        item_in_db.genres = ["Classical"]
        self.lib.directory = b"one"
        self.lib.path_formats = [
            ("default", "two"),
            ("genres:=~Classical", "three"),
        ]
        assert item_in_db.destination() == np("one/three")

    def test_multi_value_match_query_path(self, item_in_db):
        item_in_db.genres = ["Classical"]
        self.lib.directory = b"one"
        self.lib.path_formats = [
            ("default", "two"),
            ("genres:=Classical", "three"),
        ]
        assert item_in_db.destination() == np("one/three")

    def test_multi_value_string_query_path_no_substring_match(self, item_in_db):
        item_in_db.genres = ["Neoclassical"]
        self.lib.directory = b"one"
        self.lib.path_formats = [
            ("default", "two"),
            ("genres:=~Classical", "three"),
        ]
        assert item_in_db.destination() == np("one/two")

    def test_albumtype_query_path(self, item_in_db):
        item_in_db.comp = True
        self.lib.add_album([item_in_db])
        item_in_db.albumtype = "sometype"
        self.lib.directory = b"one"
        self.lib.path_formats = [
            ("default", "two"),
            ("albumtype:sometype", "four"),
            ("comp:true", "three"),
        ]
        assert item_in_db.destination() == np("one/four")

    def test_albumtype_path_fallback_to_comp(self, item_in_db):
        item_in_db.comp = True
        self.lib.add_album([item_in_db])
        item_in_db.albumtype = "sometype"
        self.lib.directory = b"one"
        self.lib.path_formats = [
            ("default", "two"),
            ("albumtype:anothertype", "four"),
            ("comp:true", "three"),
        ]
        assert item_in_db.destination() == np("one/three")

    def test_get_formatted_does_not_replace_separators(self, item_in_db):
        with _common.platform_posix():
            name = os.path.join("a", "b")
            item_in_db.title = name
            newname = item_in_db.formatted().get("title")
        assert name == newname

    def test_get_formatted_pads_with_zero(self, item_in_db):
        with _common.platform_posix():
            item_in_db.track = 1
            name = item_in_db.formatted().get("track")
        assert name.startswith("0")

    def test_get_formatted_uses_kbps_bitrate(self, item_in_db):
        with _common.platform_posix():
            item_in_db.bitrate = 12345
            val = item_in_db.formatted().get("bitrate")
        assert val == "12kbps"

    def test_get_formatted_uses_khz_samplerate(self, item_in_db):
        with _common.platform_posix():
            item_in_db.samplerate = 12345
            val = item_in_db.formatted().get("samplerate")
        assert val == "12kHz"

    def test_get_formatted_datetime(self, item_in_db):
        with _common.platform_posix():
            item_in_db.added = 1368302461.210265
            val = item_in_db.formatted().get("added")
        assert val.startswith("2013")

    def test_get_formatted_none(self, item_in_db):
        with _common.platform_posix():
            item_in_db.some_other_field = None
            val = item_in_db.formatted().get("some_other_field")
        assert val == ""

    def test_artist_falls_back_to_albumartist(self, item_in_db):
        item_in_db.artist = ""
        item_in_db.albumartist = "something"
        self.lib.path_formats = [("default", "$artist")]
        p = item_in_db.destination()
        assert p.rsplit(util.PATH_SEP, 1)[1] == b"something"

    def test_albumartist_falls_back_to_artist(self, item_in_db):
        item_in_db.artist = "trackartist"
        item_in_db.albumartist = ""
        self.lib.path_formats = [("default", "$albumartist")]
        p = item_in_db.destination()
        assert p.rsplit(util.PATH_SEP, 1)[1] == b"trackartist"

    def test_artist_overrides_albumartist(self, item_in_db):
        item_in_db.artist = "theartist"
        item_in_db.albumartist = "something"
        self.lib.path_formats = [("default", "$artist")]
        p = item_in_db.destination()
        assert p.rsplit(util.PATH_SEP, 1)[1] == b"theartist"

    def test_albumartist_overrides_artist(self, item_in_db):
        item_in_db.artist = "theartist"
        item_in_db.albumartist = "something"
        self.lib.path_formats = [("default", "$albumartist")]
        p = item_in_db.destination()
        assert p.rsplit(util.PATH_SEP, 1)[1] == b"something"

    def test_unicode_extension_in_fragment(self, item_in_db):
        self.lib.path_formats = [("default", "foo")]
        item_in_db.path = util.bytestring_path("bar.caf\xe9")
        with patch("sys.platform", "linux"):
            dest = item_in_db.destination(relative_to_libdir=True)
        assert as_string(dest) == "foo.caf\xe9"

    def test_asciify_character_expanding_to_slash(self, item_in_db):
        config["asciify_paths"] = True
        self.lib.directory = b"lib"
        self.lib.path_formats = [("default", "$title")]
        item_in_db.title = "ab\xa2\xbdd"
        assert item_in_db.destination() == np("lib/abC_ 1_2d")

    def test_destination_with_replacements(self, item_in_db):
        self.lib.directory = b"base"
        self.lib.replacements = [(re.compile(r"a"), "e")]
        self.lib.path_formats = [("default", "$album/$title")]
        item_in_db.title = "foo"
        item_in_db.album = "bar"
        assert item_in_db.destination() == np("base/ber/foo")

    @unittest.skip("unimplemented: #359")
    def test_destination_with_empty_component(self, item_in_db):
        self.lib.directory = b"base"
        self.lib.replacements = [(re.compile(r"^$"), "_")]
        self.lib.path_formats = [("default", "$album/$artist/$title")]
        item_in_db.title = "three"
        item_in_db.artist = ""
        item_in_db.albumartist = ""
        item_in_db.album = "one"
        assert item_in_db.destination() == np("base/one/_/three")

    @unittest.skip("unimplemented: #359")
    def test_destination_with_empty_final_component(self, item_in_db):
        self.lib.directory = b"base"
        self.lib.replacements = [(re.compile(r"^$"), "_")]
        self.lib.path_formats = [("default", "$album/$title")]
        item_in_db.title = ""
        item_in_db.album = "one"
        item_in_db.path = "foo.mp3"
        assert item_in_db.destination() == np("base/one/_.mp3")

    def test_album_field_query(self, item_in_db):
        self.lib.directory = b"one"
        self.lib.path_formats = [("default", "two"), ("flex:foo", "three")]
        album = self.lib.add_album([item_in_db])
        assert item_in_db.destination() == np("one/two")
        album["flex"] = "foo"
        album.store()
        assert item_in_db.destination() == np("one/three")

    def test_album_field_in_template(self, item_in_db):
        self.lib.directory = b"one"
        self.lib.path_formats = [("default", "$flex/two")]
        album = self.lib.add_album([item_in_db])
        album["flex"] = "foo"
        album.store()
        assert item_in_db.destination() == np("one/foo/two")


class TestItemFormattedMapping(PytestItemHelper):
    def test_formatted_item_value(self, item_in_db):
        formatted = item_in_db.formatted()
        assert formatted["artist"] == "the artist"

    def test_get_unset_field(self, item_in_db):
        formatted = item_in_db.formatted()
        with pytest.raises(KeyError):
            formatted["other_field"]

    def test_get_method_with_default(self, item_in_db):
        formatted = item_in_db.formatted()
        assert formatted.get("other_field") == ""

    def test_get_method_with_specified_default(self, item_in_db):
        formatted = item_in_db.formatted()
        assert formatted.get("other_field", "default") == "default"

    def test_item_precedence(self, item_in_db):
        album = self.lib.add_album([item_in_db])
        album["artist"] = "foo"
        album.store()
        assert "foo" != item_in_db.formatted().get("artist")

    def test_album_flex_field(self, item_in_db):
        album = self.lib.add_album([item_in_db])
        album["flex"] = "foo"
        album.store()
        assert "foo" == item_in_db.formatted().get("flex")

    def test_album_field_overrides_item_field_for_path(self, item_in_db):
        # Make the album inconsistent with the item.
        album = self.lib.add_album([item_in_db])
        album.album = "foo"
        album.store()
        item_in_db.album = "bar"
        item_in_db.store()

        # Ensure the album takes precedence.
        formatted = item_in_db.formatted(for_path=True)
        assert formatted["album"] == "foo"

    def test_artist_falls_back_to_albumartist(self, item_in_db):
        item_in_db.artist = ""
        formatted = item_in_db.formatted()
        assert formatted["artist"] == "the album artist"

    def test_albumartist_falls_back_to_artist(self, item_in_db):
        item_in_db.albumartist = ""
        formatted = item_in_db.formatted()
        assert formatted["albumartist"] == "the artist"

    def test_both_artist_and_albumartist_empty(self, item_in_db):
        item_in_db.artist = ""
        item_in_db.albumartist = ""
        formatted = item_in_db.formatted()
        assert formatted["albumartist"] == ""


class PathFormattingMixin:
    """Utilities for testing path formatting."""

    lib: beets.library.Library

    def _setf(self, fmt):
        self.lib.path_formats.insert(0, ("default", fmt))

    def _assert_dest(self, dest, item):
        # Handle paths on Windows.
        if os.path.sep != "/":
            dest = dest.replace(b"/", os.path.sep.encode())

            # Paths are normalized based on the CWD.
            dest = normpath(dest)

        actual = item.destination()

        assert actual == dest


class TestDestinationFunction(TestHelper, PathFormattingMixin):
    @pytest.fixture(autouse=True)
    def item(self, setup):
        self.lib.directory = b"/base"
        self.lib.path_formats = [("default", "path")]
        return item(self.lib)

    def test_upper_case_literal(self, item):
        self._setf("%upper{foo}")
        self._assert_dest(b"/base/FOO", item)

    def test_upper_case_variable(self, item):
        self._setf("%upper{$title}")
        self._assert_dest(b"/base/THE TITLE", item)

    def test_capitalize_variable(self, item):
        self._setf("%capitalize{$title}")
        self._assert_dest(b"/base/The title", item)

    def test_title_case_variable(self, item):
        self._setf("%title{$title}")
        self._assert_dest(b"/base/The Title", item)

    def test_title_case_variable_aphostrophe(self, item):
        self._setf("%title{I can't}")
        self._assert_dest(b"/base/I Can't", item)

    def test_asciify_variable(self, item):
        self._setf("%asciify{ab\xa2\xbdd}")
        self._assert_dest(b"/base/abC_ 1_2d", item)

    def test_left_variable(self, item):
        self._setf("%left{$title, 3}")
        self._assert_dest(b"/base/the", item)

    def test_right_variable(self, item):
        self._setf("%right{$title,3}")
        self._assert_dest(b"/base/tle", item)

    def test_if_false(self, item):
        self._setf("x%if{,foo}")
        self._assert_dest(b"/base/x", item)

    def test_if_false_value(self, item):
        self._setf("x%if{false,foo}")
        self._assert_dest(b"/base/x", item)

    def test_if_true(self, item):
        self._setf("%if{bar,foo}")
        self._assert_dest(b"/base/foo", item)

    def test_if_else_false(self, item):
        self._setf("%if{,foo,baz}")
        self._assert_dest(b"/base/baz", item)

    def test_if_else_false_value(self, item):
        self._setf("%if{false,foo,baz}")
        self._assert_dest(b"/base/baz", item)

    def test_if_int_value(self, item):
        self._setf("%if{0,foo,baz}")
        self._assert_dest(b"/base/baz", item)

    def test_nonexistent_function(self, item):
        self._setf("%foo{bar}")
        self._assert_dest(b"/base/%foo{bar}", item)

    def test_if_def_field_return_self(self, item):
        item.bar = 3
        self._setf("%ifdef{bar}")
        self._assert_dest(b"/base/3", item)

    def test_if_def_field_not_defined(self, item):
        self._setf(" %ifdef{bar}/$artist")
        self._assert_dest(b"/base/the artist", item)

    def test_if_def_field_not_defined_2(self, item):
        self._setf("$artist/%ifdef{bar}")
        self._assert_dest(b"/base/the artist", item)

    def test_if_def_true(self, item):
        self._setf("%ifdef{artist,cool}")
        self._assert_dest(b"/base/cool", item)

    def test_if_def_true_complete(self, item):
        item.series = "Now"
        self._setf("%ifdef{series,$series Series,Albums}/$album")
        self._assert_dest(b"/base/Now Series/the album", item)

    def test_if_def_false_complete(self, item):
        self._setf("%ifdef{plays,$plays,not_played}")
        self._assert_dest(b"/base/not_played", item)

    def test_first(self, item):
        item.albumtypes = ["album", "compilation"]
        self._setf("%first{$albumtypes}")
        self._assert_dest(b"/base/album", item)

    def test_first_skip(self, item):
        item.albumtype = "album; ep; compilation"
        self._setf("%first{$albumtype,1,2}")
        self._assert_dest(b"/base/compilation", item)

    def test_first_different_sep(self, item):
        self._setf("%first{Alice / Bob / Eve,2,0, / , & }")
        self._assert_dest(b"/base/Alice & Bob", item)


class TestDisambiguation(TestHelper, PathFormattingMixin):
    @pytest.fixture(autouse=True)
    def items(self, setup):
        self.lib.directory = b"/base"
        self.lib.path_formats = [("default", "path")]

        i1 = item()
        i1.year = 2001
        self.lib.add_album([i1])
        i2 = item()
        i2.year = 2002
        self.lib.add_album([i2])
        self.lib._connection().commit()

        self._setf("foo%aunique{albumartist album,year}/$title")
        return i1, i2

    def test_unique_expands_to_disambiguating_year(self, items):
        i1, _i2 = items
        self._assert_dest(b"/base/foo [2001]/the title", i1)

    def test_unique_with_default_arguments_uses_albumtype(self, items):
        i1, _i2 = items
        album2 = self.lib.get_album(i1)
        album2.albumtype = "bar"
        album2.store()
        self._setf("foo%aunique{}/$title")
        self._assert_dest(b"/base/foo [bar]/the title", i1)

    def test_unique_expands_to_nothing_for_distinct_albums(self, items):
        i1, i2 = items
        album2 = self.lib.get_album(i2)
        album2.album = "different album"
        album2.store()

        self._assert_dest(b"/base/foo/the title", i1)

    def test_use_fallback_numbers_when_identical(self, items):
        i1, i2 = items
        album2 = self.lib.get_album(i2)
        album2.year = 2001
        album2.store()

        self._assert_dest(b"/base/foo [1]/the title", i1)
        self._assert_dest(b"/base/foo [2]/the title", i2)

    def test_unique_falls_back_to_second_distinguishing_field(self, items):
        i1, _i2 = items
        self._setf("foo%aunique{albumartist album,month year}/$title")
        self._assert_dest(b"/base/foo [2001]/the title", i1)

    def test_unique_sanitized(self, items):
        i1, i2 = items
        album2 = self.lib.get_album(i2)
        album2.year = 2001
        album1 = self.lib.get_album(i1)
        album1.albumtype = "foo/bar"
        album2.store()
        album1.store()
        self._setf("foo%aunique{albumartist album,albumtype}/$title")
        self._assert_dest(b"/base/foo [foo_bar]/the title", i1)

    def test_drop_empty_disambig_string(self, items):
        i1, i2 = items
        album1 = self.lib.get_album(i1)
        album1.albumdisambig = None
        album2 = self.lib.get_album(i2)
        album2.albumdisambig = "foo"
        album1.store()
        album2.store()
        self._setf("foo%aunique{albumartist album,albumdisambig}/$title")
        self._assert_dest(b"/base/foo/the title", i1)

    def test_change_brackets(self, items):
        i1, _i2 = items
        self._setf("foo%aunique{albumartist album,year,()}/$title")
        self._assert_dest(b"/base/foo (2001)/the title", i1)

    def test_remove_brackets(self, items):
        i1, _i2 = items
        self._setf("foo%aunique{albumartist album,year,}/$title")
        self._assert_dest(b"/base/foo 2001/the title", i1)

    def test_key_flexible_attribute(self, items):
        i1, i2 = items
        album1 = self.lib.get_album(i1)
        album1.flex = "flex1"
        album2 = self.lib.get_album(i2)
        album2.flex = "flex2"
        album1.store()
        album2.store()
        self._setf("foo%aunique{albumartist album flex,year}/$title")
        self._assert_dest(b"/base/foo/the title", i1)


class TestSingletonDisambiguation(TestHelper, PathFormattingMixin):
    @pytest.fixture(autouse=True)
    def items(self, setup):
        self.lib.directory = b"/base"
        self.lib.path_formats = [("default", "path")]

        i1 = item()
        i1.year = 2001
        self.lib.add(i1)
        i2 = item()
        i2.year = 2002
        self.lib.add(i2)
        self.lib._connection().commit()

        self._setf("foo/$title%sunique{artist title,year}")
        return i1, i2

    def test_sunique_expands_to_disambiguating_year(self, items):
        i1, _i2 = items
        self._assert_dest(b"/base/foo/the title [2001]", i1)

    def test_sunique_with_default_arguments_uses_trackdisambig(self, items):
        i1, i2 = items
        i1.trackdisambig = "live version"
        i1.year = i2.year
        i1.store()
        self._setf("foo/$title%sunique{}")
        self._assert_dest(b"/base/foo/the title [live version]", i1)

    def test_sunique_expands_to_nothing_for_distinct_singletons(self, items):
        i1, i2 = items
        i2.title = "different track"
        i2.store()

        self._assert_dest(b"/base/foo/the title", i1)

    def test_sunique_does_not_match_album(self, items):
        i1, i2 = items
        self.lib.add_album([i2])
        self._assert_dest(b"/base/foo/the title", i1)

    def test_sunique_use_fallback_numbers_when_identical(self, items):
        i1, i2 = items
        i2.year = i1.year
        i2.store()

        self._assert_dest(b"/base/foo/the title [1]", i1)
        self._assert_dest(b"/base/foo/the title [2]", i2)

    def test_sunique_falls_back_to_second_distinguishing_field(self, items):
        i1, _i2 = items
        self._setf("foo/$title%sunique{albumartist album,month year}")
        self._assert_dest(b"/base/foo/the title [2001]", i1)

    def test_sunique_sanitized(self, items):
        i1, i2 = items
        i2.year = i1.year
        i1.trackdisambig = "foo/bar"
        i2.store()
        i1.store()
        self._setf("foo/$title%sunique{artist title,trackdisambig}")
        self._assert_dest(b"/base/foo/the title [foo_bar]", i1)

    def test_drop_empty_disambig_string(self, items):
        i1, i2 = items
        i1.trackdisambig = None
        i2.trackdisambig = "foo"
        i1.store()
        i2.store()
        self._setf("foo/$title%sunique{albumartist album,trackdisambig}")
        self._assert_dest(b"/base/foo/the title", i1)

    def test_change_brackets(self, items):
        i1, _i2 = items
        self._setf("foo/$title%sunique{artist title,year,()}")
        self._assert_dest(b"/base/foo/the title (2001)", i1)

    def test_remove_brackets(self, items):
        i1, _i2 = items
        self._setf("foo/$title%sunique{artist title,year,}")
        self._assert_dest(b"/base/foo/the title 2001", i1)

    def test_key_flexible_attribute(self, items):
        i1, i2 = items
        i1.flex = "flex1"
        i2.flex = "flex2"
        i1.store()
        i2.store()
        self._setf("foo/$title%sunique{artist title flex,year}")
        self._assert_dest(b"/base/foo/the title", i1)


class TestPluginDestination(TestHelper):
    @pytest.fixture(autouse=True)
    def item(self, setup):
        # Mock beets.plugins.item_field_getters.
        self._tv_map = {}

        def field_getters():
            getters = {}
            for key, value in self._tv_map.items():
                getters[key] = lambda _: value
            return getters

        self.old_field_getters = plugins.item_field_getters
        plugins.item_field_getters = field_getters

        self.lib.directory = b"/base"
        self.lib.path_formats = [("default", "$artist $foo")]

        yield _common.item(self.lib)

        plugins.item_field_getters = self.old_field_getters

    def _assert_dest(self, dest, item):
        with _common.platform_posix():
            the_dest = item.destination()
        assert the_dest == b"/base/" + dest

    def test_undefined_value_not_substituted(self, item):
        self._assert_dest(b"the artist $foo", item)

    def test_plugin_value_not_substituted(self, item):
        self._tv_map = {"foo": "bar"}
        self._assert_dest(b"the artist bar", item)

    def test_plugin_value_overrides_attribute(self, item):
        self._tv_map = {"artist": "bar"}
        self._assert_dest(b"bar $foo", item)

    def test_plugin_value_sanitized(self, item):
        self._tv_map = {"foo": "bar/baz"}
        self._assert_dest(b"the artist bar_baz", item)


class TestAlbumInfo(PytestItemHelper):
    @pytest.fixture
    def item_in_album(self, item):
        self.lib.add_album((item,))
        return item

    def test_albuminfo_reflects_metadata(self, item_in_album):
        ai = self.lib.get_album(item_in_album)
        assert ai.mb_albumartistid == item_in_album.mb_albumartistid
        assert ai.albumartist == item_in_album.albumartist
        assert ai.album == item_in_album.album
        assert ai.year == item_in_album.year

    def test_albuminfo_stores_art(self, item_in_album):
        ai = self.lib.get_album(item_in_album)
        ai.artpath = os.fsdecode(np("/my/great/art"))
        ai.store()
        new_ai = self.lib.get_album(item_in_album)
        assert new_ai.artpath == np("/my/great/art")

    def test_albuminfo_for_two_items_doesnt_duplicate_row(self, item_in_album):
        i2 = _common.item(self.lib)
        self.lib.get_album(item_in_album)
        self.lib.get_album(i2)

        c = self.lib._connection().cursor()
        c.execute("select * from albums where album=?", (item_in_album.album,))
        # Cursor should only return one row.
        assert c.fetchone() is not None
        assert c.fetchone() is None

    def test_individual_tracks_have_no_albuminfo(self):
        i2 = _common.item()
        i2.album = "aTotallyDifferentAlbum"
        self.lib.add(i2)
        ai = self.lib.get_album(i2)
        assert ai is None

    def test_get_album_by_id(self, item_in_album):
        ai = self.lib.get_album(item_in_album)
        ai = self.lib.get_album(item_in_album.id)
        assert ai is not None

    def test_album_items_consistent(self, item_in_album):
        ai = self.lib.get_album(item_in_album)
        assert item_in_album.id in {i.id for i in ai.items()}

    def test_albuminfo_changes_affect_items(self, item_in_album):
        ai = self.lib.get_album(item_in_album)
        ai.album = "myNewAlbum"
        ai.store()
        assert self.get_first_item().album == "myNewAlbum"

    def test_albuminfo_change_albumartist_changes_items(self, item_in_album):
        ai = self.lib.get_album(item_in_album)
        ai.albumartist = "myNewArtist"
        ai.store()
        item = self.get_first_item()
        assert item.albumartist == "myNewArtist"
        assert item.artist != "myNewArtist"

    def test_albuminfo_change_artist_does_change_items(self, item_in_album):
        ai = self.lib.get_album(item_in_album)
        ai.artist = "myNewArtist"
        ai.store(inherit=True)
        assert self.get_first_item().artist == "myNewArtist"

    def test_albuminfo_change_artist_does_not_change_items(self, item_in_album):
        ai = self.lib.get_album(item_in_album)
        ai.artist = "myNewArtist"
        ai.store(inherit=False)
        assert self.get_first_item().artist != "myNewArtist"

    def test_albuminfo_remove_removes_items(self, item_in_album):
        item_id = item_in_album.id
        self.lib.get_album(item_in_album).remove()
        c = self.lib._connection().execute(
            "SELECT id FROM items WHERE id=?", (item_id,)
        )
        assert c.fetchone() is None

    def test_removing_last_item_removes_album(self, item_in_album):
        assert len(self.lib.albums()) == 1
        item_in_album.remove()
        assert len(self.lib.albums()) == 0

    def test_noop_albuminfo_changes_affect_items(self, item_in_album):
        item = self.get_first_item()
        item.album = "foobar"
        item.store()
        ai = self.lib.get_album(item_in_album)
        ai.album = ai.album
        ai.store()
        item = self.get_first_item()
        assert item.album == ai.album


class TestArtDestination(TestHelper):
    @pytest.fixture(autouse=True)
    def item_and_album(self, setup):
        config["art_filename"] = "artimage"
        config["replace"] = {"X": "Y"}
        self.lib.replacements = [(re.compile("X"), "Y")]
        self.lib.path_formats = [("default", "$artist/$album/$track $title")]
        item = _common.item(self.lib)
        item.path = item.destination()
        ai = self.lib.add_album((item,))
        return item, ai

    def test_art_filename_respects_setting(self, item_and_album):
        _i, ai = item_and_album
        art = ai.art_destination("something.jpg")
        new_art = bytestring_path(f"{os.path.sep}artimage.jpg")
        assert new_art in art

    def test_art_path_in_item_dir(self, item_and_album):
        i, ai = item_and_album
        art = ai.art_destination("something.jpg")
        track = i.destination()
        assert os.path.dirname(art) == os.path.dirname(track)

    def test_art_path_sanitized(self, item_and_album):
        _i, ai = item_and_album
        config["art_filename"] = "artXimage"
        art = ai.art_destination("something.jpg")
        assert b"artYimage" in art


class TestPathString(PytestItemHelper):
    def test_item_path_is_bytestring(self, item_in_db):
        assert isinstance(item_in_db.path, bytes)

    def test_fetched_item_path_is_bytestring(self, item_in_db):
        assert isinstance(self.get_first_item().path, bytes)

    def test_unicode_path_becomes_bytestring(self, item_in_db):
        item_in_db.path = "unicodepath"
        assert isinstance(item_in_db.path, bytes)

    def test_unicode_in_database_becomes_bytestring(self, item_in_db):
        self.lib._connection().execute(
            """
        update items set path=? where id=?
        """,
            (item_in_db.id, "somepath"),
        )
        assert isinstance(self.get_first_item().path, bytes)

    def test_special_chars_preserved_in_database(self, item_in_db):
        path = "b\xe1r".encode()
        item_in_db.path = path
        item_in_db.store()
        assert self.get_first_item().path == os.path.join(self.libdir, path)

    def test_special_char_path_added_to_database(self, item, item_in_db):
        item_in_db.remove()
        path = "b\xe1r".encode()
        item = _common.item()
        item.path = path
        self.lib.add(item)
        assert self.get_first_item().path == os.path.join(self.libdir, path)

    def test_destination_returns_bytestring(self, item_in_db):
        item_in_db.artist = "b\xe1r"
        dest = item_in_db.destination()
        assert isinstance(dest, bytes)

    def test_art_destination_returns_bytestring(self, item_in_db):
        item_in_db.artist = "b\xe1r"
        alb = self.lib.add_album([item_in_db])
        dest = alb.art_destination("image.jpg")
        assert isinstance(dest, bytes)

    def test_artpath_stores_special_chars(self, item_in_db):
        path = bytestring_path("b\xe1r")
        alb = self.lib.add_album([item_in_db])
        alb.artpath = path
        alb.store()
        stored_path = (
            self.lib._connection()
            .execute("select artpath from albums where id=?", (alb.id,))
            .fetchone()[0]
        )
        alb = self.lib.get_album(item_in_db)
        assert stored_path == path
        assert alb.artpath == os.path.join(self.libdir, path)

    def test_sanitize_path_with_special_chars(self):
        path = "b\xe1r?"
        new_path = util.sanitize_path(path)
        assert new_path.startswith("b\xe1r")

    def test_sanitize_path_returns_unicode(self):
        path = "b\xe1r?"
        new_path = util.sanitize_path(path)
        assert isinstance(new_path, str)

    def test_unicode_artpath_becomes_bytestring(self, item_in_db):
        alb = self.lib.add_album([item_in_db])
        alb.artpath = "somep\xe1th"
        assert isinstance(alb.artpath, bytes)

    def test_unicode_artpath_in_database_decoded(self, item_in_db):
        alb = self.lib.add_album([item_in_db])
        self.lib._connection().execute(
            "update albums set artpath=? where id=?", ("somep\xe1th", alb.id)
        )
        alb = self.lib.get_album(alb.id)
        assert isinstance(alb.artpath, bytes)

    def test_relative_path_is_stored(self, item_in_db):
        relative_path = os.path.join(b"abc", b"foo.mp3")
        absolute_path = os.path.join(self.libdir, relative_path)
        item_in_db.path = absolute_path
        item_in_db.store()
        stored_path = (
            self.lib._connection()
            .execute("select path from items where id=?", (item_in_db.id,))
            .fetchone()[0]
        )
        album = self.lib.add_album([item_in_db])

        assert item_in_db.path == absolute_path
        assert stored_path == path_as_posix(relative_path)
        assert album.path == os.path.dirname(absolute_path)


class TestMtime(TestHelper):
    @pytest.fixture(autouse=True)
    def item(self, setup):
        self.ipath = os.path.join(self.temp_dir, b"testfile.mp3")
        shutil.copy(
            syspath(os.path.join(_common.RSRC, b"full.mp3")),
            syspath(self.ipath),
        )
        item = beets.library.Item.from_path(self.ipath)
        self.lib.add(item)
        yield item
        if os.path.exists(self.ipath):
            os.remove(self.ipath)

    def _mtime(self):
        return int(os.path.getmtime(self.ipath))

    def test_mtime_initially_up_to_date(self, item):
        assert item.mtime >= self._mtime()

    def test_mtime_reset_on_db_modify(self, item):
        item.title = "something else"
        assert item.mtime < self._mtime()

    def test_mtime_up_to_date_after_write(self, item):
        item.title = "something else"
        item.write()
        assert item.mtime >= self._mtime()

    def test_mtime_up_to_date_after_read(self, item):
        item.title = "something else"
        item.read()
        assert item.mtime >= self._mtime()


class TestImportTime(TestHelper):
    def added(self):
        self.track = item()
        self.album = self.lib.add_album((self.track,))
        assert self.album.added > 0
        assert self.track.added > 0

    def test_atime_for_singleton(self):
        self.singleton = item(self.lib)
        assert self.singleton.added > 0


class TestTemplate(PytestItemHelper):
    def test_year_formatted_in_template(self, item_in_db):
        item_in_db.year = 123
        item_in_db.store()
        assert item_in_db.evaluate_template("$year") == "0123"

    def test_album_flexattr_appears_in_item_template(self, item_in_db):
        self.album = self.lib.add_album([item_in_db])
        self.album.foo = "baz"
        self.album.store()
        assert item_in_db.evaluate_template("$foo") == "baz"

    def test_album_and_item_format(self, item_in_db):
        config["format_album"] = "foö $foo"
        album = beets.library.Album()
        album.foo = "bar"
        album.tagada = "togodo"
        assert f"{album}" == "foö bar"
        assert f"{album:$tagada}" == "togodo"
        assert str(album) == "foö bar"
        assert bytes(album) == b"fo\xc3\xb6 bar"

        config["format_item"] = "bar $foo"
        item = beets.library.Item()
        item.foo = "bar"
        item.tagada = "togodo"
        assert f"{item}" == "bar bar"
        assert f"{item:$tagada}" == "togodo"


class TestUnicodePath(PytestItemHelper):
    def test_unicode_path(self, item_in_db):
        item_in_db.path = os.path.join(
            _common.RSRC, "unicode\u2019d.mp3".encode()
        )
        # If there are any problems with unicode paths, we will raise
        # here and fail.
        item_in_db.read()
        item_in_db.write()


class TestWrite(TestHelper):
    def test_write_nonexistant(self):
        item = self.create_item()
        item.path = b"/path/does/not/exist"
        with pytest.raises(beets.library.ReadError):
            item.write()

    def test_no_write_permission(self):
        item = self.add_item_fixture()
        path = syspath(item.path)
        os.chmod(path, stat.S_IRUSR)

        try:
            with pytest.raises(beets.library.WriteError) as exc_info:
                item.write()
            assert "super:" not in str(exc_info.value)

        finally:
            # Restore write permissions so the file can be cleaned up.
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)

    def test_write_with_custom_path(self):
        item = self.add_item_fixture()
        custom_path = os.path.join(self.temp_dir, b"custom.mp3")
        shutil.copy(syspath(item.path), syspath(custom_path))

        item["artist"] = "new artist"
        assert MediaFile(syspath(custom_path)).artist != "new artist"
        assert MediaFile(syspath(item.path)).artist != "new artist"

        item.write(custom_path)
        assert MediaFile(syspath(custom_path)).artist == "new artist"
        assert MediaFile(syspath(item.path)).artist != "new artist"

    def test_write_custom_tags(self):
        item = self.add_item_fixture(artist="old artist")
        item.write(tags={"artist": "new artist"})
        assert item.artist != "new artist"
        assert MediaFile(syspath(item.path)).artist == "new artist"

    def test_write_multi_tags(self):
        item = self.add_item_fixture(artist="old artist")
        item.write(tags={"artists": ["old artist", "another artist"]})

        assert MediaFile(syspath(item.path)).artists == [
            "old artist",
            "another artist",
        ]

    def test_write_multi_tags_id3v23(self):
        item = self.add_item_fixture(artist="old artist")
        item.write(
            tags={"artists": ["old artist", "another artist"]}, id3v23=True
        )

        assert MediaFile(syspath(item.path)).artists == [
            "old artist/another artist"
        ]

    def test_write_date_field(self):
        # Since `date` is not a MediaField, this should do nothing.
        item = self.add_item_fixture()
        clean_year = item.year
        item.date = "foo"
        item.write()
        assert MediaFile(syspath(item.path)).year == clean_year

    @pytest.mark.parametrize("file_format", ["MP3", "FLAC"])
    def test_no_write_when_file_has_the_tags(self, file_format):
        item = self.add_item_fixture(format=file_format)
        # The file keeps six decimal places of the peak, so the value read
        # back from it never equals the one stored in the database.
        item.rg_track_peak = 10 ** (-1.2 / 20)
        item.write()
        os.utime(syspath(item.path), (1000000000, 1000000000))

        item.write()

        assert item.current_mtime() == 1000000000

    def test_write_list_tag_that_drops_an_empty_value(self):
        # An empty value the file happens to hold is still a value there, so
        # the file no longer holds the tags once it is gone.
        item = self.add_item_fixture(format="FLAC")
        item.write()
        mediafile = MediaFile(syspath(item.path))
        mediafile.artists = ["the artist", "", "another artist"]
        mediafile.save()
        item.artists = ["the artist", "another artist"]
        os.utime(syspath(item.path), (1000000000, 1000000000))

        item.write()

        assert item.current_mtime() != 1000000000
        assert MediaFile(syspath(item.path)).artists == [
            "the artist",
            "another artist",
        ]

    def test_write_file_with_an_unreadable_image(self):
        # The images are not read, so a file beets cannot parse one from is
        # written like any other.
        path = os.path.join(self.temp_dir, b"unreadable_image.ogg")
        shutil.copy(os.path.join(_common.RSRC, b"full.ogg"), path)
        mediafile = mutagen.File(syspath(path))
        mediafile["metadata_block_picture"] = ["not base64"]
        mediafile.save()
        item = beets.library.Item.from_path(path)
        item.title = "another title"

        item.write()

        assert MediaFile(syspath(path)).title == "another title"


class TestItemRead(PytestItemHelper):
    def test_unreadable_raise_read_error(self, item_in_db):
        unreadable = os.path.join(_common.RSRC, b"image-2x3.png")
        with pytest.raises(beets.library.ReadError) as exc_info:
            item_in_db.read(unreadable)
        assert isinstance(exc_info.value.reason, UnreadableFileError)

    def test_nonexistent_raise_read_error(self, item_in_db):
        with pytest.raises(beets.library.ReadError):
            item_in_db.read("/thisfiledoesnotexist")

    def test_read_error_str_includes_reason(self, item_in_db):
        unreadable = os.path.join(_common.RSRC, b"image-2x3.png")
        with pytest.raises(beets.library.ReadError) as exc_info:
            item_in_db.read(unreadable)
        message = str(exc_info.value)
        assert "super:" not in message
        assert str(exc_info.value.reason) in message


class TestItemReadGenre(TestHelper):
    def test_read_semicolon_delimited_genres(self):
        """Semicolon-delimited genre tags are split into individual genres on read."""
        path = self.create_mediafile_fixture()
        mf = MediaFile(syspath(path))
        mf.genres = ["Jazz; Funk; Soul"]
        mf.save()
        item = beets.library.Item.from_path(path)
        assert item.genres == ["Jazz", "Funk", "Soul"]


class TestFilesize(TestHelper):
    def test_filesize(self):
        item = self.add_item_fixture()
        assert item.filesize != 0

    def test_nonexistent_file(self):
        item = beets.library.Item()
        assert item.filesize == 0


class TestItemPruneDirsClutter(TestHelper):
    """Regression tests: prune_dirs respects config["clutter"] during move/remove."""

    def _drop_clutter(self, directory, filename=b"unwanted.log"):
        """Create a clutter file in *directory* (bytes path)."""
        path = os.path.join(directory, filename)
        with open(syspath(path), "w"):
            pass
        return path

    def test_move_prunes_dir_with_config_clutter(self):
        """After moving an item, old dir is removed even when only clutter remains."""
        config["clutter"] = ["*.log"]
        item = self.add_item_fixture()
        old_dir = os.path.dirname(item.path)
        self._drop_clutter(old_dir)

        # Change artist so the destination path differs, forcing a real move.
        item.artist = "new artist"
        item.store()
        item.move()

        assert not os.path.exists(syspath(old_dir))

    def test_remove_prunes_dir_with_config_clutter(self):
        """After deleting an item, its dir is removed even when only clutter remains."""
        config["clutter"] = ["*.log"]
        item = self.add_item_fixture()
        old_dir = os.path.dirname(item.path)
        self._drop_clutter(old_dir)

        item.remove(delete=True)

        assert not os.path.exists(syspath(old_dir))


class TestParseQuery:
    def test_parse_invalid_query_string(self):
        with pytest.raises(beets.dbcore.query.ParsingError):
            beets.library.parse_query_string('foo"', None)

    def test_parse_bytes(self):
        with pytest.raises(AssertionError):
            beets.library.parse_query_string(b"query", None)
