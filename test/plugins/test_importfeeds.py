import datetime
import os
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
        self.feeds_dir = self.temp_dir_path / "importfeeds"
        self.config["importfeeds"]["dir"] = str(self.feeds_dir)

    def test_multi_format_album_playlist(self):
        self.config["importfeeds"]["formats"] = "m3u_multi"
        album = Album(album="album/name", id=1)
        item_path = os.path.join("path", "to", "item")
        item = Item(title="song", album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        self.importfeeds.album_imported(self.lib, album)
        playlist_path = self.feeds_dir / next(self.feeds_dir.iterdir())
        assert str(playlist_path).endswith("album_name.m3u")
        with open(playlist_path) as playlist:
            assert item_path in playlist.read()

    def test_playlist_in_subdir(self):
        self.config["importfeeds"]["formats"] = "m3u"
        self.config["importfeeds"]["m3u_name"] = os.path.join(
            "subdir", "imported.m3u"
        )
        album = Album(album="album/name", id=1)
        item_path = os.path.join("path", "to", "item")
        item = Item(title="song", album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        self.importfeeds.album_imported(self.lib, album)
        playlist = self.feeds_dir / self.config["importfeeds"]["m3u_name"].get()
        playlist_subdir = os.path.dirname(playlist)
        assert os.path.isdir(playlist_subdir)
        assert os.path.isfile(playlist)

    def test_playlist_per_session(self):
        self.config["importfeeds"]["formats"] = "m3u_session"
        self.config["importfeeds"]["m3u_name"] = "imports.m3u"
        album = Album(album="album/name", id=1)
        item_path = os.path.join("path", "to", "item")
        item = Item(title="song", album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        self.importfeeds.import_begin(self)
        self.importfeeds.album_imported(self.lib, album)
        date = datetime.datetime.now().strftime("%Y%m%d_%Hh%M")
        playlist = self.feeds_dir / f"imports_{date}.m3u"
        assert os.path.isfile(playlist)
        with open(playlist) as playlist_contents:
            assert item_path in playlist_contents.read()

    def test_link_failure_does_not_abort_import(self):
        """A symlink that can't be created is skipped, not fatal (#840)."""
        self.config["importfeeds"]["formats"] = "link"
        album = Album(album="album/name", id=1)
        item = Item(
            title="song", album_id=1, path=os.path.join("path", "to", "item")
        )
        self.lib.add(album)
        self.lib.add(item)

        with mock.patch(
            "beetsplug.importfeeds.link",
            side_effect=FilesystemError("no permission", "link", (b"a", b"b")),
        ):
            self.importfeeds.album_imported(self.lib, album)

    def test_link_failure_logs_warning(self):
        """A failed symlink is reported via a warning, not dropped silently."""
        self.config["importfeeds"]["formats"] = "link"
        album = Album(album="album/name", id=1)
        item = Item(
            title="song", album_id=1, path=os.path.join("path", "to", "item")
        )
        self.lib.add(album)
        self.lib.add(item)

        with (
            mock.patch(
                "beetsplug.importfeeds.link",
                side_effect=FilesystemError(
                    "no permission", "link", (b"a", b"b")
                ),
            ),
            mock.patch.object(self.importfeeds, "_log") as log,
        ):
            self.importfeeds.album_imported(self.lib, album)

        log.warning.assert_called_once()

    def test_link_failure_continues_to_remaining_items(self):
        """One item's symlink failing must not skip the remaining items."""
        self.config["importfeeds"]["formats"] = "link"
        album = Album(album="album/name", id=1)
        item1 = Item(title="one", album_id=1, path=os.path.join("path", "one"))
        item2 = Item(title="two", album_id=1, path=os.path.join("path", "two"))
        self.lib.add(album)
        self.lib.add(item1)
        self.lib.add(item2)

        with mock.patch(
            "beetsplug.importfeeds.link",
            side_effect=[FilesystemError("x", "link", (b"a", b"b")), None],
        ) as mock_link:
            self.importfeeds.album_imported(self.lib, album)

        assert mock_link.call_count == 2

    def test_non_filesystem_error_is_not_swallowed(self):
        """Only FilesystemError is caught; other errors still propagate."""
        self.config["importfeeds"]["formats"] = "link"
        album = Album(album="album/name", id=1)
        item = Item(
            title="song", album_id=1, path=os.path.join("path", "to", "item")
        )
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
        item_path = os.path.join("path", "to", "item")
        item = Item(title="song", album_id=1, path=item_path)
        self.lib.add(album)
        self.lib.add(item)

        self.importfeeds.album_imported(self.lib, album)

        linked = self.feeds_dir / os.path.basename(item_path)
        assert os.path.islink(linked)
