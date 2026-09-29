import datetime
from pathlib import Path
from unittest import mock

import pytest

from beets.library import Album, Item
from beets.test.helper import PluginTestCase
from beets.util import FilesystemError
from beetsplug.importfeeds import ImportFeedsPlugin


class ImportFeedsTest(PluginTestCase):
    plugin = "importfeeds"

    def setUp(self):
        super().setUp()
        self.importfeeds = ImportFeedsPlugin()
        self.feeds_dir = self.temp_path / "importfeeds"
        self.config["importfeeds"]["dir"] = str(self.feeds_dir)

    def test_multi_format_album_playlist(self):
        self.config["importfeeds"]["formats"] = "m3u_multi"
        album = Album(album="album/name", id=1)
        item_path = Path("path") / "to" / "item"
        item = Item(title="song", album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        self.importfeeds.album_imported(self.lib, album)
        playlist_path = self.feeds_dir / next(self.feeds_dir.iterdir())
        assert str(playlist_path).endswith("album_name.m3u")
        assert str(item_path) in playlist_path.read_text()

    def test_playlist_in_subdir(self):
        self.config["importfeeds"]["formats"] = "m3u"
        self.config["importfeeds"]["m3u_name"] = str(
            Path("subdir") / "imported.m3u"
        )
        album = Album(album="album/name", id=1)
        item_path = Path("path") / "to" / "item"
        item = Item(title="song", album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        self.importfeeds.album_imported(self.lib, album)
        playlist = self.feeds_dir / self.config["importfeeds"]["m3u_name"].get()
        playlist_subdir = playlist.parent
        assert playlist_subdir.is_dir()
        assert playlist.is_file()

    def test_playlist_per_session(self):
        self.config["importfeeds"]["formats"] = "m3u_session"
        self.config["importfeeds"]["m3u_name"] = "imports.m3u"
        album = Album(album="album/name", id=1)
        item_path = Path("path") / "to" / "item"
        item = Item(title="song", album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        self.importfeeds.import_begin(self)
        self.importfeeds.album_imported(self.lib, album)
        date = datetime.datetime.now().strftime("%Y%m%d_%Hh%M")
        playlist = self.feeds_dir / f"imports_{date}.m3u"
        assert playlist.is_file()
        assert str(item_path) in playlist.read_text()

    def test_link_failure_warns_and_continues(self):
        """A symlink that can't be created is logged as a warning and
        skipped; remaining items are still processed (#840)."""
        self.config["importfeeds"]["formats"] = "link"
        album = Album(album="album/name", id=1)
        item1 = Item(title="one", album_id=1, path=Path("path") / "one")
        item2 = Item(title="two", album_id=1, path=Path("path") / "two")
        self.lib.add(album)
        self.lib.add(item1)
        self.lib.add(item2)

        with (
            mock.patch(
                "beetsplug.importfeeds.link",
                side_effect=[FilesystemError("x", "link", (b"a", b"b")), None],
            ) as mock_link,
            mock.patch.object(self.importfeeds, "_log") as log,
        ):
            self.importfeeds.album_imported(self.lib, album)

        log.warning.assert_called_once()
        assert mock_link.call_count == 2

    def test_non_filesystem_error_is_not_swallowed(self):
        """Only FilesystemError is caught; other errors still propagate."""
        self.config["importfeeds"]["formats"] = "link"
        album = Album(album="album/name", id=1)
        item_path = Path("path") / "to" / "item"
        item = Item(title="song", album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        with (
            mock.patch(
                "beetsplug.importfeeds.link",
                side_effect=ValueError("unexpected"),
            ),
            pytest.raises(ValueError, match="unexpected"),
        ):
            self.importfeeds.album_imported(self.lib, album)

    def test_link_creates_symlink(self):
        """The happy path still creates the symlink when it succeeds."""
        self.config["importfeeds"]["formats"] = "link"
        self.feeds_dir.mkdir(parents=True, exist_ok=True)
        album = Album(album="album/name", id=1)
        item_path = Path("path") / "to" / "item"
        item = Item(title="song", album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        self.importfeeds.album_imported(self.lib, album)

        linked = self.feeds_dir / item.filepath.name
        assert linked.is_symlink()
