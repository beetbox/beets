import os
from pathlib import Path
from shlex import quote

import beets
from beets.test import _common
from beets.test.helper import PluginTestCase


class PlaylistTestCase(PluginTestCase):
    plugin = "playlist"
    preload_plugin = False

    def setUp(self):
        super().setUp()

        self.music_dir = os.path.expanduser(os.path.join("~", "Music"))

        i1 = _common.item()
        i1.path = beets.util.normpath(
            os.path.join(self.music_dir, "a", "b", "c.mp3")
        )
        i1.title = "some item"
        i1.album = "some album"
        self.lib.add(i1)
        self.lib.add_album([i1])

        i2 = _common.item()
        i2.path = beets.util.normpath(
            os.path.join(self.music_dir, "d", "e", "f.mp3")
        )
        i2.title = "another item"
        i2.album = "another album"
        self.lib.add(i2)
        self.lib.add_album([i2])

        i3 = _common.item()
        i3.path = beets.util.normpath(
            os.path.join(self.music_dir, "x", "y", "z.mp3")
        )
        i3.title = "yet another item"
        i3.album = "yet another album"
        self.lib.add(i3)
        self.lib.add_album([i3])

        self.playlist_dir = self.temp_dir_path / "playlists"
        self.playlist_dir.mkdir(parents=True, exist_ok=True)
        self.config["directory"] = self.music_dir
        self.config["playlist"]["playlist_dir"] = str(self.playlist_dir)
        self.absolute_playlist_path = self.playlist_dir / "absolute.m3u"
        self.relative_playlist_path = self.playlist_dir / "relative.m3u"

        self.write_absolute_playlist()
        self.write_relative_playlist()
        self.setup_test()
        self.load_plugins()

    def write_absolute_playlist(self):
        lines = [
            os.path.join(self.music_dir, "a", "b", "c.mp3"),
            os.path.join(self.music_dir, "d", "e", "f.mp3"),
            os.path.join(self.music_dir, "nonexisting.mp3"),
        ]
        self.absolute_playlist_path.write_text("\n".join(lines) + "\n")

    def write_relative_playlist(self):
        lines = [
            os.path.join("a", "b", "c.mp3"),
            os.path.join("d", "e", "f.mp3"),
            "nonexisting.mp3",
        ]
        self.relative_playlist_path.write_text("\n".join(lines) + "\n")

    def setup_test(self):
        raise NotImplementedError


class PlaylistQueryTest:
    def test_name_query_with_absolute_paths_in_playlist(self):
        q = "playlist:absolute"
        results = self.lib.items(q)
        assert {i.title for i in results} == {"some item", "another item"}

    def test_path_query_with_absolute_paths_in_playlist(self):
        q = f"playlist:{self.absolute_playlist_path}"
        results = self.lib.items(q)
        assert {i.title for i in results} == {"some item", "another item"}

    def test_name_query_with_relative_paths_in_playlist(self):
        q = "playlist:relative"
        results = self.lib.items(q)
        assert {i.title for i in results} == {"some item", "another item"}

    def test_path_query_with_relative_paths_in_playlist(self):
        q = f"playlist:{self.relative_playlist_path}"
        results = self.lib.items(q)
        assert {i.title for i in results} == {"some item", "another item"}

    def test_name_query_with_nonexisting_playlist(self):
        q = "playlist:nonexisting"
        results = self.lib.items(q)
        assert set(results) == set()

    def test_path_query_with_nonexisting_playlist(self):
        q = f"playlist:{os.path.join(self.playlist_dir, 'nonexisting.m3u')!r}"
        results = self.lib.items(q)
        assert set(results) == set()


class PlaylistTestRelativeToLib(PlaylistQueryTest, PlaylistTestCase):
    def setup_test(self):
        self.config["playlist"]["relative_to"] = "library"


class PlaylistTestRelativeToDir(PlaylistQueryTest, PlaylistTestCase):
    def setup_test(self):
        self.config["playlist"]["relative_to"] = self.music_dir


class PlaylistTestRelativeToPls(PlaylistQueryTest, PlaylistTestCase):
    def write_relative_playlist(self):
        lines = [
            os.path.relpath(
                os.path.join(self.music_dir, "a", "b", "c.mp3"),
                self.playlist_dir,
            ),
            os.path.relpath(
                os.path.join(self.music_dir, "d", "e", "f.mp3"),
                self.playlist_dir,
            ),
            os.path.relpath(
                os.path.join(self.music_dir, "nonexisting.mp3"),
                self.playlist_dir,
            ),
        ]
        self.relative_playlist_path.write_text("\n".join(lines) + "\n")

    def setup_test(self):
        self.config["playlist"]["relative_to"] = "playlist"
        self.config["playlist"]["playlist_dir"] = str(self.playlist_dir)


class PlaylistUpdateTest:
    def setup_test(self):
        self.config["playlist"]["auto"] = True
        self.config["playlist"]["relative_to"] = "library"


class PlaylistTestItemMoved(PlaylistUpdateTest, PlaylistTestCase):
    def test_item_moved(self):
        # Emit item_moved event for an item that is in a playlist
        results = self.lib.items(
            f"path:{quote(os.path.join(self.music_dir, 'd', 'e', 'f.mp3'))}"
        )
        item = results[0]
        beets.plugins.send(
            "item_moved",
            item=item,
            source=item.path,
            destination=beets.util.bytestring_path(
                os.path.join(self.music_dir, "g", "h", "i.mp3")
            ),
        )

        # Emit item_moved event for an item that is not in a playlist
        results = self.lib.items(
            f"path:{quote(os.path.join(self.music_dir, 'x', 'y', 'z.mp3'))}"
        )
        item = results[0]
        beets.plugins.send(
            "item_moved",
            item=item,
            source=item.path,
            destination=beets.util.bytestring_path(
                os.path.join(self.music_dir, "u", "v", "w.mp3")
            ),
        )

        # Emit cli_exit event
        beets.plugins.send("cli_exit", lib=self.lib)

        # Check playlist with absolute paths
        playlist_path = os.path.join(self.playlist_dir, "absolute.m3u")
        with open(playlist_path) as f:
            lines = [line.strip() for line in f.readlines()]

        assert lines == [
            os.path.join(self.music_dir, "a", "b", "c.mp3"),
            os.path.join(self.music_dir, "g", "h", "i.mp3"),
            os.path.join(self.music_dir, "nonexisting.mp3"),
        ]

        # Check playlist with relative paths
        lines = self.relative_playlist_path.read_text().splitlines()

        assert lines == [
            os.path.join("a", "b", "c.mp3"),
            os.path.join("g", "h", "i.mp3"),
            "nonexisting.mp3",
        ]


class PlaylistTestItemRemoved(PlaylistUpdateTest, PlaylistTestCase):
    def test_item_removed(self):
        # Emit item_removed event for an item that is in a playlist
        results = self.lib.items(
            f"path:{quote(os.path.join(self.music_dir, 'd', 'e', 'f.mp3'))}"
        )
        item = results[0]
        beets.plugins.send("item_removed", item=item)

        # Emit item_removed event for an item that is not in a playlist
        results = self.lib.items(
            f"path:{quote(os.path.join(self.music_dir, 'x', 'y', 'z.mp3'))}"
        )
        item = results[0]
        beets.plugins.send("item_removed", item=item)

        # Emit cli_exit event
        beets.plugins.send("cli_exit", lib=self.lib)

        # Check playlist with absolute paths
        lines = self.absolute_playlist_path.read_text().splitlines()

        assert lines == [
            os.path.join(self.music_dir, "a", "b", "c.mp3"),
            os.path.join(self.music_dir, "nonexisting.mp3"),
        ]

        # Check playlist with relative paths
        lines = self.relative_playlist_path.read_text().splitlines()

        assert lines == [os.path.join("a", "b", "c.mp3"), "nonexisting.mp3"]
