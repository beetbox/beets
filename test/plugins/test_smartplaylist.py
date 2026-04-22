# This file is part of beets.
# Copyright 2016, Bruno Cauet.
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

# TODO: Tests in this fire are very bad. Stop using Mocks in this module.

import os
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import MagicMock, Mock, PropertyMock

import pytest

from beets import config
from beets.dbcore.query import FixedFieldSort, MultipleSort, NullSort
from beets.library import Album, Item, parse_query_string
from beets.test._common import item
from beets.test.helper import BeetsTestCase, IOMixin, PluginTestCase
from beets.ui import UserError
from beets.util import CHAR_REPLACE, syspath
from beetsplug.smartplaylist import SmartPlaylistPlugin

_p = pytest.param


class SmartPlaylistTest(BeetsTestCase):
    def test_build_queries(self):
        spl = SmartPlaylistPlugin()
        assert spl._matched_playlists == set()
        assert spl._unmatched_playlists == set()

        config["smartplaylist"]["playlists"].set([])
        spl.build_queries()
        assert spl._matched_playlists == set()
        assert spl._unmatched_playlists == set()

        config["smartplaylist"]["playlists"].set(
            [
                {"name": "foo", "query": "FOO foo"},
                {"name": "bar", "album_query": ["BAR bar1", "BAR bar2"]},
                {"name": "baz", "query": "BAZ baz", "album_query": "BAZ baz"},
            ]
        )
        spl.build_queries()
        assert spl._matched_playlists == set()
        foo_foo = parse_query_string("FOO foo", Item)
        baz_baz = parse_query_string("BAZ baz", Item)
        baz_baz2 = parse_query_string("BAZ baz", Album)
        # Multiple queries are now stored as a tuple of (query, sort) tuples
        bar_queries = tuple(
            [
                parse_query_string("BAR bar1", Album),
                parse_query_string("BAR bar2", Album),
            ]
        )
        assert spl._unmatched_playlists == {
            ("foo", foo_foo, (None, None)),
            ("baz", baz_baz, baz_baz2),
            ("bar", (None, None), (bar_queries, None)),
        }

    def test_build_queries_with_sorts(self):
        spl = SmartPlaylistPlugin()
        config["smartplaylist"]["playlists"].set(
            [
                {"name": "no_sort", "query": "foo"},
                {"name": "one_sort", "query": "foo year+"},
                {"name": "only_empty_sorts", "query": ["foo", "bar"]},
                {"name": "one_non_empty_sort", "query": ["foo year+", "bar"]},
                {
                    "name": "multiple_sorts",
                    "query": ["foo year+", "bar genres-"],
                },
                {
                    "name": "mixed",
                    "query": ["foo year+", "bar", "baz genres+ id-"],
                },
            ]
        )

        spl.build_queries()

        # Multiple queries now return a tuple of (query, sort) tuples, not combined
        sorts = {}
        for name, (query_data, sort), _ in spl._unmatched_playlists:
            if isinstance(query_data, tuple):
                # Tuple of queries - each has its own sort
                sorts[name] = [s for _, s in query_data]
            else:
                sorts[name] = sort

        sort = FixedFieldSort  # short cut since we're only dealing with this
        assert sorts["no_sort"] == NullSort()
        assert sorts["one_sort"] == sort("year")
        # Multiple queries store individual sorts in the tuple
        assert all(isinstance(x, NullSort) for x in sorts["only_empty_sorts"])
        assert sorts["one_non_empty_sort"] == [sort("year"), NullSort()]
        assert sorts["multiple_sorts"] == [sort("year"), sort("genres", False)]
        assert sorts["mixed"] == [
            sort("year"),
            NullSort(),
            MultipleSort([sort("genres"), sort("id", False)]),
        ]

    def test_matches(self):
        spl = SmartPlaylistPlugin()

        a = MagicMock(Album)
        i = MagicMock(Item)

        assert not spl.matches(i, None, None)
        assert not spl.matches(a, None, None)

        query = Mock()
        query.match.side_effect = {i: True}.__getitem__
        assert spl.matches(i, query, None)
        assert not spl.matches(a, query, None)

        a_query = Mock()
        a_query.match.side_effect = {a: True}.__getitem__
        assert not spl.matches(i, None, a_query)
        assert spl.matches(a, None, a_query)

        assert spl.matches(i, query, a_query)
        assert spl.matches(a, query, a_query)

        # Test with list of queries
        q1 = Mock()
        q1.match.return_value = False
        q2 = Mock()
        q2.match.side_effect = {i: True}.__getitem__
        queries_list = [(q1, None), (q2, None)]
        assert spl.matches(i, queries_list, None)
        assert not spl.matches(a, queries_list, None)

    def test_db_changes(self):
        spl = SmartPlaylistPlugin()

        nones = None, None
        pl1 = "1", ("q1", None), nones
        pl2 = "2", ("q2", None), nones
        pl3 = "3", ("q3", None), nones

        spl._unmatched_playlists = {pl1, pl2, pl3}
        spl._matched_playlists = set()

        spl.matches = Mock(return_value=False)
        spl.db_change(None, "nothing")
        assert spl._unmatched_playlists == {pl1, pl2, pl3}
        assert spl._matched_playlists == set()

        spl.matches.side_effect = lambda _, q, __: q == "q3"
        spl.db_change(None, "matches 3")
        assert spl._unmatched_playlists == {pl1, pl2}
        assert spl._matched_playlists == {pl3}

        spl.matches.side_effect = lambda _, q, __: q == "q1"
        spl.db_change(None, "matches 3")
        assert spl._matched_playlists == {pl1, pl3}
        assert spl._unmatched_playlists == {pl2}

    def test_playlist_update(self):
        spl = SmartPlaylistPlugin()

        i = Mock(path=b"/tagada.mp3")
        i.evaluate_template.side_effect = lambda pl, *_: os.fsdecode(
            pl
        ).replace("$title", "ta:ga:da")

        lib = Mock()
        lib.replacements = CHAR_REPLACE
        lib.items.return_value = [i]
        lib.albums.return_value = []

        q = Mock()
        a_q = Mock()
        pl = b"$title-my<playlist>.m3u", (q, None), (a_q, None)
        spl._matched_playlists = {pl}

        dir = mkdtemp()
        config["smartplaylist"]["relative_to"] = False
        config["smartplaylist"]["playlist_dir"] = str(dir)
        try:
            spl.update_playlists(lib)
        except Exception:
            rmtree(syspath(dir))
            raise

        lib.items.assert_called_once_with(q, None)
        lib.albums.assert_called_once_with(a_q, None)

        m3u_filepath = Path(dir, "ta_ga_da-my_playlist_.m3u")
        assert m3u_filepath.exists()
        content = m3u_filepath.read_bytes()
        rmtree(syspath(dir))

        assert content == b"/tagada.mp3\n"

    def test_playlist_update_output_extm3u(self):
        spl = SmartPlaylistPlugin()

        i = MagicMock()
        type(i).artist = PropertyMock(return_value="fake artist")
        type(i).title = PropertyMock(return_value="fake title")
        type(i).length = PropertyMock(return_value=300.123)
        type(i).path = PropertyMock(return_value=b"/tagada.mp3")
        i.evaluate_template.side_effect = lambda pl, *_: os.fsdecode(
            pl
        ).replace("$title", "ta:ga:da")

        lib = Mock()
        lib.replacements = CHAR_REPLACE
        lib.items.return_value = [i]
        lib.albums.return_value = []

        q = Mock()
        a_q = Mock()
        pl = b"$title-my<playlist>.m3u", (q, None), (a_q, None)
        spl._matched_playlists = {pl}

        dir = mkdtemp()
        config["smartplaylist"]["output"] = "extm3u"
        config["smartplaylist"]["prefix"] = "http://beets:8337/files"
        config["smartplaylist"]["relative_to"] = False
        config["smartplaylist"]["playlist_dir"] = str(dir)
        try:
            spl.update_playlists(lib)
        except Exception:
            rmtree(syspath(dir))
            raise

        lib.items.assert_called_once_with(q, None)
        lib.albums.assert_called_once_with(a_q, None)

        m3u_filepath = Path(dir, "ta_ga_da-my_playlist_.m3u")
        assert m3u_filepath.exists()
        content = m3u_filepath.read_bytes()
        rmtree(syspath(dir))

        assert content == (
            b"#EXTM3U\n"
            b"#EXTINF:300,fake artist - fake title\n"
            b"http://beets:8337/files/tagada.mp3\n"
        )

    def test_playlist_update_output_extm3u_fields(self):
        spl = SmartPlaylistPlugin()

        i = MagicMock()
        type(i).artist = PropertyMock(return_value="Fake Artist")
        type(i).title = PropertyMock(return_value="fake Title")
        type(i).length = PropertyMock(return_value=300.123)
        type(i).path = PropertyMock(return_value=b"/tagada.mp3")
        a = {"id": 456, "genres": ["Rock", "Pop"]}
        i.__getitem__.side_effect = a.__getitem__
        i.evaluate_template.side_effect = lambda pl, *_: os.fsdecode(
            pl
        ).replace("$title", "ta:ga:da")

        lib = Mock()
        lib.replacements = CHAR_REPLACE
        lib.items.return_value = [i]
        lib.albums.return_value = []

        q = Mock()
        a_q = Mock()
        pl = b"$title-my<playlist>.m3u", (q, None), (a_q, None)
        spl._matched_playlists = {pl}

        dir = mkdtemp()
        config["smartplaylist"]["output"] = "extm3u"
        config["smartplaylist"]["relative_to"] = False
        config["smartplaylist"]["playlist_dir"] = str(dir)
        config["smartplaylist"]["fields"] = ["id", "genres"]
        try:
            spl.update_playlists(lib)
        except Exception:
            rmtree(syspath(dir))
            raise

        lib.items.assert_called_once_with(q, None)
        lib.albums.assert_called_once_with(a_q, None)

        m3u_filepath = Path(dir, "ta_ga_da-my_playlist_.m3u")
        assert m3u_filepath.exists()
        content = m3u_filepath.read_bytes()
        rmtree(syspath(dir))

        assert content == (
            b"#EXTM3U\n"
            b'#EXTINF:300 id="456" genres="Rock%3B%20Pop",Fake Artist - fake Title\n'
            b"/tagada.mp3\n"
        )

    def test_get_playlist_items(self):
        """Test get playlist items.

        - Items preserve their order in the playlist
        - There are no duplicates when items match multiple queries
        """
        self.add_item(path=b"/item1.mp3", id=1)
        self.add_item(path=b"/item2.mp3", id=2)
        self.add_item(path=b"/item3.mp3", id=3)
        queries_and_sorts = (("path::item id-", None), ("path::item3", None))

        actual_items = SmartPlaylistPlugin.get_playlist_items(
            self.lib, (queries_and_sorts, None), (None, None)
        )

        assert [i.id for i in actual_items] == [3, 2, 1]


class TestGetItemURI:
    @pytest.fixture
    def plugin_config(self):
        return {}

    @pytest.fixture
    def plugin(self, config, plugin_config):
        plugin_config = {
            "prefix": "http://beets:8337/files",
            **plugin_config,
        }
        config["smartplaylist"].set(plugin_config)

        return SmartPlaylistPlugin()

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setattr(Item, "destination", lambda _: b"/tagada.mp3")

    @pytest.fixture
    def item(self):
        return item(
            id=3,
            artist="fake artist",
            title="fake title",
            length=300.123,
            path=b"/imported/path/with/dont/move/tagada.mp3",
        )

    @pytest.mark.parametrize(
        "plugin_config, expected_uri",
        [
            _p(
                {},
                b"http://beets:8337/files/imported/path/with/dont/move/tagada.mp3",
                id="path by default",
            ),
            _p(
                {"dest_regen": True},
                b"http://beets:8337/files/tagada.mp3",
                id="dest_regen uses item destination",
            ),
            _p(
                {
                    "uri_format": "http://beets:8337/item/$id/file",
                    "dest_regen": True,
                },
                b"http://beets:8337/item/3/file",
                id="uri_format takes precedence",
            ),
        ],
    )
    def test_get_item_uri(self, plugin, item, expected_uri):
        assert plugin.get_item_uri(item) == expected_uri


class SmartPlaylistCLITest(IOMixin, PluginTestCase):
    plugin = "smartplaylist"

    def setUp(self):
        super().setUp()

        self.item = self.add_item()
        config["smartplaylist"]["playlists"].set(
            [
                {"name": "my_playlist.m3u", "query": self.item.title},
                {"name": "all.m3u", "query": ""},
            ]
        )
        config["smartplaylist"]["playlist_dir"].set(str(self.temp_dir_path))

    def test_splupdate(self):
        with pytest.raises(UserError):
            self.run_with_output("splupdate", "tagada")

        self.run_with_output("splupdate", "my_playlist")
        m3u_path = self.temp_dir_path / "my_playlist.m3u"
        assert m3u_path.exists()
        assert m3u_path.read_bytes() == self.item.path + b"\n"
        os.remove(syspath(m3u_path))

        self.run_with_output("splupdate", "my_playlist.m3u")
        assert m3u_path.read_bytes() == self.item.path + b"\n"
        os.remove(syspath(m3u_path))

        self.run_with_output("splupdate")
        for name in (b"my_playlist.m3u", b"all.m3u"):
            with open(os.path.join(self.temp_dir, name), "rb") as f:
                assert f.read() == self.item.path + b"\n"

    def test_splupdate_unknown_playlist_error_is_sorted_and_quoted(self):
        config["smartplaylist"]["playlists"].set(
            [
                {"name": "z last.m3u", "query": self.item.title},
                {"name": "rock'n roll.m3u", "query": self.item.title},
                {"name": "a one.m3u", "query": self.item.title},
            ]
        )

        with pytest.raises(UserError) as exc_info:
            self.run_with_output("splupdate", "tagada")

        assert str(exc_info.value) == (
            "No playlist matching any of "
            "'a one.m3u' 'rock'\"'\"'n roll.m3u' 'z last.m3u' found"
        )

    def test_splupdate_log_output(self):
        with self.assertLogs("beets.smartplaylist", level="INFO") as logs:
            self.run_with_output("splupdate", "my_playlist")

        output = "\n".join(logs.output)
        assert "Updating 1 smart playlists..." in output
        assert "Creating playlist my_playlist.m3u: 1 tracks." in output
        assert "1 playlists updated" in output

    def test_splupdate_verbose_log_output(self):
        with self.assertLogs("beets.smartplaylist", level="DEBUG") as logs:
            self.run_with_output("splupdate", "my_playlist")

        output = "\n".join(logs.output)
        assert "Updating 1 smart playlists..." in output
        assert "Creating playlist my_playlist.m3u: 1 tracks." in output
        assert "the ärtist - " in output
        assert "1 playlists updated" in output

    def test_splupdate_pretend_log_output(self):
        with self.assertLogs("beets.smartplaylist", level="INFO") as logs:
            self.run_with_output("splupdate", "--pretend", "my_playlist")

        output = "\n".join(logs.output)
        assert "Updating 1 smart playlists..." in output
        assert "Creating playlist my_playlist.m3u: 1 tracks." in output
        assert "1 playlists would be updated" in output
