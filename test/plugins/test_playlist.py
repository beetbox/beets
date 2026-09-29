import os
from pathlib import Path
from shlex import quote

import beets
from beets.test.helper import PluginTestCase


class PlaylistTestCase(PluginTestCase):
    plugin = "playlist"
    preload_plugin = False
    c_track_path = Path("a") / "b" / "c.mp3"
    f_track_path = Path("d") / "e" / "f.mp3"
    i_track_path = Path("g") / "h" / "i.mp3"
    w_track_path = Path("u") / "v" / "w.mp3"
    z_track_path = Path("x") / "y" / "z.mp3"
    nonexisting_track_path = Path("nonexisting.mp3")

    def setUp(self):
        super().setUp()

        self.music_dir = (Path("~") / "Music").expanduser()

        for p, title, album in [
            (self.c_track_path, "some item", "some album"),
            (self.f_track_path, "another item", "another album"),
            (self.z_track_path, "yet another item", "yet another album"),
        ]:
            self.add_album(path=self.music_dir / p, title=title, album=album)

        self.playlist_dir = self.temp_path / "playlists"
        self.playlist_dir.mkdir(parents=True, exist_ok=True)
        self.config["directory"] = str(self.music_dir)
        self.config["playlist"]["playlist_dir"] = str(self.playlist_dir)
        self.absolute_playlist_path = self.playlist_dir / "absolute.m3u"
        self.relative_playlist_path = self.playlist_dir / "relative.m3u"

        self.write_absolute_playlist()
        self.write_relative_playlist()
        self.setup_test()
        self.load_plugins()

    def write_absolute_playlist(self):
        lines = [
            self.music_dir / self.c_track_path,
            self.music_dir / self.f_track_path,
            self.music_dir / self.nonexisting_track_path,
        ]
        self.absolute_playlist_path.write_text("\n".join(map(str, lines)))

    def write_relative_playlist(self):
        lines = [
            self.c_track_path,
            self.f_track_path,
            self.nonexisting_track_path,
        ]
        self.relative_playlist_path.write_text("\n".join(map(str, lines)))

    def setup_test(self):
        raise NotImplementedError


class PlaylistQueryTest:
    def test_name_query_with_absolute_paths_in_playlist(self):
        q = "playlist:absolute"
        results = self.lib.items(q)
        assert {i.title for i in results} == {"some item", "another item"}

    def test_path_query_with_absolute_paths_in_playlist(self):
        q = f"playlist:{quote(str(self.absolute_playlist_path))}"
        results = self.lib.items(q)
        assert {i.title for i in results} == {"some item", "another item"}

    def test_name_query_with_relative_paths_in_playlist(self):
        q = "playlist:relative"
        results = self.lib.items(q)
        assert {i.title for i in results} == {"some item", "another item"}

    def test_path_query_with_relative_paths_in_playlist(self):
        q = f"playlist:{quote(str(self.relative_playlist_path))}"
        results = self.lib.items(q)
        assert {i.title for i in results} == {"some item", "another item"}

    def test_name_query_with_nonexisting_playlist(self):
        q = "playlist:nonexisting"
        results = self.lib.items(q)
        assert set(results) == set()

    def test_path_query_with_nonexisting_playlist(self):
        q = f"playlist:{quote(str(self.nonexisting_track_path))}"
        results = self.lib.items(q)
        assert set(results) == set()


class PlaylistTestRelativeToLib(PlaylistQueryTest, PlaylistTestCase):
    def setup_test(self):
        self.config["playlist"]["relative_to"] = "library"


class PlaylistTestRelativeToDir(PlaylistQueryTest, PlaylistTestCase):
    def setup_test(self):
        self.config["playlist"]["relative_to"] = str(self.music_dir)


class PlaylistTestRelativeToPls(PlaylistQueryTest, PlaylistTestCase):
    def write_relative_playlist(self):
        lines = [
            os.path.relpath(
                self.music_dir / self.c_track_path, self.playlist_dir
            ),
            os.path.relpath(
                self.music_dir / self.f_track_path, self.playlist_dir
            ),
            os.path.relpath(
                self.music_dir / self.nonexisting_track_path, self.playlist_dir
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
        q = f"path:{quote(str(self.music_dir / self.f_track_path))}"
        results = self.lib.items(q)
        item = results[0]
        beets.plugins.send(
            "item_moved",
            item=item,
            source=item.path,
            destination=os.fsencode(self.music_dir / self.i_track_path),
        )

        # Emit item_moved event for an item that is not in a playlist
        results = self.lib.items(
            f"path:{quote(str(self.music_dir / self.z_track_path))}"
        )
        item = results[0]
        beets.plugins.send(
            "item_moved",
            item=item,
            source=item.path,
            destination=os.fsencode(self.music_dir / self.w_track_path),
        )

        # Emit cli_exit event
        beets.plugins.send("cli_exit", lib=self.lib)

        expected_paths = [
            self.c_track_path,
            self.i_track_path,
            self.nonexisting_track_path,
        ]
        # Check playlist with absolute paths
        lines = list(
            map(Path, self.absolute_playlist_path.read_text().splitlines())
        )
        assert lines == [self.music_dir / p for p in expected_paths]

        # Check playlist with relative paths
        lines = list(
            map(Path, self.relative_playlist_path.read_text().splitlines())
        )
        assert lines == expected_paths


class PlaylistTestItemRemoved(PlaylistUpdateTest, PlaylistTestCase):
    def test_item_removed(self):
        # Emit item_removed event for an item that is in a playlist
        q = f"path:{quote(str(self.music_dir / self.f_track_path))}"
        results = self.lib.items(q)
        item = results[0]
        beets.plugins.send("item_removed", item=item)

        # Emit item_removed event for an item that is not in a playlist
        q = f"path:{quote(str(self.music_dir / self.z_track_path))}"
        results = self.lib.items(q)
        item = results[0]
        beets.plugins.send("item_removed", item=item)

        # Emit cli_exit event
        beets.plugins.send("cli_exit", lib=self.lib)

        expected_paths = [self.c_track_path, self.nonexisting_track_path]
        # Check playlist with absolute paths
        lines = list(
            map(Path, self.absolute_playlist_path.read_text().splitlines())
        )
        assert lines == [self.music_dir / p for p in expected_paths]

        # Check playlist with relative paths
        lines = list(
            map(Path, self.relative_playlist_path.read_text().splitlines())
        )
        assert lines == expected_paths
