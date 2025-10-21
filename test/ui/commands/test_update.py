import os

from mediafile import MediaFile

from beets import library, util
from beets.test import _common
from beets.test.helper import BeetsTestCase, IOMixin
from beets.ui.commands.update import update_items
from beets.util import MoveOperation, syspath


class UpdateTest(IOMixin, BeetsTestCase):
    def setUp(self):
        super().setUp()

        # Copy a file into the library.
        item_path = os.path.join(_common.RSRC, b"full.mp3")
        item_path_two = os.path.join(_common.RSRC, b"full.flac")
        self.i = library.Item.from_path(item_path)
        self.i2 = library.Item.from_path(item_path_two)
        self.lib.add(self.i)
        self.lib.add(self.i2)
        self.i.move(operation=MoveOperation.COPY)
        self.i2.move(operation=MoveOperation.COPY)
        self.album = self.lib.add_album([self.i, self.i2])

        # Album art.
        artfile = os.path.join(self.temp_dir, b"testart.jpg")
        _common.touch(artfile)
        self.album.set_art(artfile)
        self.album.store()
        util.remove(artfile)

    def _update(
        self,
        query=(),
        album=False,
        move=False,
        reset_mtime=True,
        fields=None,
        exclude_fields=None,
    ):
        self.io.addinput("y")
        if reset_mtime:
            self.i.mtime = 0
            self.i.store()
        update_items(
            self.lib,
            query,
            album,
            move,
            False,
            fields=fields,
            exclude_fields=exclude_fields,
        )

    def test_delete_removes_item(self):
        assert list(self.lib.items())
        util.remove(self.i.path)
        util.remove(self.i2.path)
        self._update()
        assert not list(self.lib.items())

    def test_delete_removes_album(self):
        assert self.lib.albums()
        util.remove(self.i.path)
        util.remove(self.i2.path)
        self._update()
        assert not self.lib.albums()

    def test_delete_removes_album_art(self):
        art_filepath = self.album.art_filepath
        assert art_filepath.exists()
        util.remove(self.i.path)
        util.remove(self.i2.path)
        self._update()
        assert not art_filepath.exists()

    def test_modified_metadata_detected(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.save()
        self._update()
        item = self.lib.items().get()
        assert item.title == "differentTitle"

    def test_modified_metadata_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.save()
        self._update(move=True)
        item = self.lib.items().get()
        assert b"differentTitle" in item.path

    def test_modified_metadata_not_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.save()
        self._update(move=False)
        item = self.lib.items().get()
        assert b"differentTitle" not in item.path

    def test_selective_modified_metadata_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.genre = "differentGenre"
        mf.save()
        self._update(move=True, fields=["title"])
        item = self.lib.items().get()
        assert b"differentTitle" in item.path
        assert item.genre != "differentGenre"

    def test_selective_modified_metadata_not_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.genre = "differentGenre"
        mf.save()
        self._update(move=False, fields=["title"])
        item = self.lib.items().get()
        assert b"differentTitle" not in item.path
        assert item.genre != "differentGenre"

    def test_modified_album_metadata_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.album = "differentAlbum"
        mf.save()
        self._update(move=True)
        item = self.lib.items().get()
        assert b"differentAlbum" in item.path

    def test_modified_album_metadata_art_moved(self):
        artpath = self.album.artpath
        mf = MediaFile(syspath(self.i.path))
        mf.album = "differentAlbum"
        mf.save()
        self._update(move=True)
        album = self.lib.albums()[0]
        assert artpath != album.artpath
        assert album.artpath is not None

    def test_selective_modified_album_metadata_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.album = "differentAlbum"
        mf.genre = "differentGenre"
        mf.save()
        self._update(move=True, fields=["album"])
        item = self.lib.items().get()
        assert b"differentAlbum" in item.path
        assert item.genre != "differentGenre"

    def test_selective_modified_album_metadata_not_moved(self):
        mf = MediaFile(syspath(self.i.path))
        mf.album = "differentAlbum"
        mf.genre = "differentGenre"
        mf.save()
        self._update(move=True, fields=["genre"])
        item = self.lib.items().get()
        assert b"differentAlbum" not in item.path
        assert item.genre == "differentGenre"

    def test_mtime_match_skips_update(self):
        mf = MediaFile(syspath(self.i.path))
        mf.title = "differentTitle"
        mf.save()

        # Make in-memory mtime match on-disk mtime.
        self.i.mtime = os.path.getmtime(syspath(self.i.path))
        self.i.store()

        self._update(reset_mtime=False)
        item = self.lib.items().get()
        assert item.title == "full"

    def test_multivalued_albumtype_roundtrip(self):
        # https://github.com/beetbox/beets/issues/4528

        # albumtypes is empty for our test fixtures, so populate it first
        album = self.album
        correct_albumtypes = ["album", "live"]

        # Setting albumtypes does not set albumtype, currently.
        # Using x[0] mirrors https://github.com/beetbox/mediafile/blob/057432ad53b3b84385e5582f69f44dc00d0a725d/mediafile.py#L1928  # noqa: E501
        correct_albumtype = correct_albumtypes[0]

        album.albumtype = correct_albumtype
        album.albumtypes = correct_albumtypes
        album.try_sync(write=True, move=False)

        album.load()
        assert album.albumtype == correct_albumtype
        assert album.albumtypes == correct_albumtypes

        self._update()

        album.load()
        assert album.albumtype == correct_albumtype
        assert album.albumtypes == correct_albumtypes

    def test_modified_metadata_excluded(self):
        mf = MediaFile(syspath(self.i.path))
        mf.lyrics = "new lyrics"
        mf.save()
        self._update(exclude_fields=["lyrics"])
        item = self.lib.items().get()
        assert item.lyrics != "new lyrics"
