import datetime
import os

from beets.library import Album, Item
from beets.test.helper import PluginTestCase
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
