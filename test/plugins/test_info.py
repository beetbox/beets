import os

from mediafile import MediaFile

from beets.test.helper import IOMixin, PluginTestCase


class InfoTest(IOMixin, PluginTestCase):
    plugin = "info"

    def test_path(self):
        path = self.create_mediafile_fixture()

        mediafile = MediaFile(path)
        mediafile.albumartist = "AAA"
        mediafile.disctitle = "DDD"
        mediafile.genres = ["a", "b", "c"]
        mediafile.composer = None
        mediafile.save()

        out = self.run_with_output("info", path)
        assert os.fsdecode(path) in out
        assert "albumartist: AAA" in out
        assert "disctitle: DDD" in out
        assert "genres: a; b; c" in out
        assert "composer:" not in out

    def test_item_query(self):
        item1, item2 = self.add_item_fixtures(count=2)
        item1.album = "xxxx"
        item1.write()
        item1.album = "yyyy"
        item1.store()

        out = self.run_with_output("info", "album:yyyy")
        assert str(item1.filepath) in out
        assert "album: xxxx" in out

        assert str(item2.filepath) not in out

    def test_item_library_query(self):
        (item,) = self.add_item_fixtures()
        item.album = "xxxx"
        item.store()

        out = self.run_with_output("info", "--library", "album:xxxx")
        assert str(item.filepath) in out
        assert "album: xxxx" in out

    def test_collect_item_and_path(self):
        path = self.create_mediafile_fixture()
        mediafile = MediaFile(path)
        (item,) = self.add_item_fixtures()

        item.album = mediafile.album = "AAA"
        item.tracktotal = mediafile.tracktotal = 5
        item.title = "TTT"
        mediafile.title = "SSS"

        item.write()
        item.store()
        mediafile.save()

        out = self.run_with_output("info", "--summarize", "album:AAA", path)
        assert "album: AAA" in out
        assert "tracktotal: 5" in out
        assert "title: [various]" in out

    def test_collect_item_and_path_with_multi_values(self):
        path = self.create_mediafile_fixture()
        mediafile = MediaFile(path)
        (item,) = self.add_item_fixtures()

        item.album = mediafile.album = "AAA"
        item.tracktotal = mediafile.tracktotal = 5
        item.title = "TTT"
        mediafile.title = "SSS"

        item.albumartists = ["Artist A", "Artist B"]
        mediafile.albumartists = ["Artist C", "Artist D"]

        item.artists = ["Artist A", "Artist Z"]
        mediafile.artists = ["Artist A", "Artist Z"]

        item.write()
        item.store()
        mediafile.save()

        out = self.run_with_output("info", "--summarize", "album:AAA", path)
        assert "album: AAA" in out
        assert "tracktotal: 5" in out
        assert "title: [various]" in out
        assert "albumartists: [various]" in out
        assert "artists: Artist A; Artist Z" in out

    def test_custom_format(self):
        self.add_item_fixtures()
        out = self.run_with_output(
            "info",
            "--library",
            "--format",
            "$track. $title - $artist ($length)",
        )
        assert "02. tïtle 0 - the artist (0:01)\n" == out
