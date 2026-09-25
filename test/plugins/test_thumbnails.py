from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from beets.test.helper import BeetsTestCase
from beetsplug.thumbnails import (
    LARGE_DIR,
    NORMAL_DIR,
    GioURI,
    PathlibURI,
    ThumbnailsPlugin,
)


class ThumbnailsTest(BeetsTestCase):
    @patch("beetsplug.thumbnails.ArtResizer")
    @patch("beetsplug.thumbnails.ThumbnailsPlugin._check_local_ok", Mock())
    @patch("pathlib.Path.stat")
    def test_add_tags(self, path_stat, mock_artresizer):
        artpath = Path("/path/to/cover")
        plugin = ThumbnailsPlugin()
        plugin.get_uri = Mock(side_effect={artpath: "COVER_URI"}.__getitem__)
        image_path = Path("/path/to/thumbnail")
        path_stat.return_value.st_mtime = 12345

        plugin.add_tags(artpath, image_path)

        metadata = {"Thumb::URI": "COVER_URI", "Thumb::MTime": "12345"}
        mock_artresizer.shared.write_metadata.assert_called_once_with(
            image_path, metadata
        )
        path_stat.assert_called_once()

    @patch("beetsplug.thumbnails.ArtResizer")
    @patch("beetsplug.thumbnails.GioURI")
    def test_check_local_ok(self, mock_giouri, mock_artresizer):
        # test local resizing capability
        mock_artresizer.shared.local = False
        mock_artresizer.shared.can_write_metadata = False
        plugin = ThumbnailsPlugin()
        assert not plugin._check_local_ok()

        # test dirs creation
        mock_artresizer.shared.local = True
        mock_artresizer.shared.can_write_metadata = True

        def exists(self):
            if self == NORMAL_DIR:
                return False
            if self == LARGE_DIR:
                return True
            raise ValueError(f"unexpected path {self!r}")

        plugin = ThumbnailsPlugin()
        assert NORMAL_DIR.exists()
        assert LARGE_DIR.exists()
        assert plugin._check_local_ok()

        with patch("pathlib.Path.exists", autospec=True, side_effect=exists):
            mock_artresizer.shared.local = True
            mock_artresizer.shared.can_write_metadata = False
            with pytest.raises(RuntimeError):
                ThumbnailsPlugin()

        mock_artresizer.shared.local = True
        mock_artresizer.shared.can_write_metadata = True
        assert ThumbnailsPlugin()._check_local_ok()

        # test URI getter function
        giouri_inst = mock_giouri.return_value
        giouri_inst.available = True
        assert ThumbnailsPlugin().get_uri == giouri_inst.uri

        giouri_inst.available = False
        assert ThumbnailsPlugin().get_uri.__self__.__class__ == PathlibURI

    @patch("beetsplug.thumbnails.ThumbnailsPlugin._check_local_ok", Mock())
    @patch("beetsplug.thumbnails.ArtResizer")
    @patch("beets.util.syspath", Mock(side_effect=lambda x: x))
    @patch("beetsplug.thumbnails.shutil")
    def test_make_cover_thumbnail(self, mock_shutils, mock_artresizer):
        thumbnail_dir = Path("/thumbnail/dir")
        md5_file = thumbnail_dir / "md5"
        artpath = Path("/path/to/art")
        path_to_resized_art = Path("/path/to/resized/artwork")

        plugin = ThumbnailsPlugin()
        plugin.add_tags = Mock()

        album = Mock(artpath=artpath)
        plugin.thumbnail_file_name = Mock(return_value="md5")
        with patch(
            "pathlib.Path.exists", autospec=True, return_value=False
        ) as mock_exists:
            mock_resize = mock_artresizer.shared.resize
            mock_resize.return_value = path_to_resized_art

            plugin.make_cover_thumbnail(album, artpath, 12345, thumbnail_dir)

            mock_exists.assert_called_once_with(md5_file)

            mock_resize.assert_called_once_with(12345, artpath, md5_file)
            plugin.add_tags.assert_called_once_with(
                artpath, path_to_resized_art
            )
            mock_shutils.move.assert_called_once_with(
                path_to_resized_art, md5_file
            )

        # now test with recent thumbnail & with force
        def stat(self):
            if self == md5_file:
                return Mock(st_mtime=3)
            if self == artpath:
                return Mock(st_mtime=2)
            raise ValueError(f"invalid target {self}")

        with (
            patch("pathlib.Path.exists", autospec=True, return_value=True),
            patch("pathlib.Path.stat", autospec=True, side_effect=stat),
        ):
            plugin.force = False
            mock_resize.reset_mock()

            plugin.make_cover_thumbnail(album, artpath, 12345, thumbnail_dir)
            assert mock_resize.call_count == 0

        # and with force
        plugin.config["force"] = True
        plugin.make_cover_thumbnail(album, artpath, 12345, thumbnail_dir)
        mock_resize.assert_called_once_with(12345, artpath, md5_file)

    @patch("beetsplug.thumbnails.ThumbnailsPlugin._check_local_ok", Mock())
    def test_make_dolphin_cover_thumbnail(self):
        plugin = ThumbnailsPlugin()
        tmp = self.temp_path
        album = Mock(filepath=tmp, art_filepath=tmp / "cover.jpg")
        plugin.make_dolphin_cover_thumbnail(album.filepath, album.art_filepath)
        filename = tmp / ".directory"
        assert filename.read_text() == "[Desktop Entry]\nIcon=./cover.jpg"

        # not rewritten when it already exists (yup that's a big limitation)
        album.artpath = b"/my/awesome/art.tiff"
        plugin.make_dolphin_cover_thumbnail(album.filepath, album.art_filepath)
        assert filename.read_text() == "[Desktop Entry]\nIcon=./cover.jpg"

    @patch("beetsplug.thumbnails.ThumbnailsPlugin._check_local_ok", Mock())
    @patch("beetsplug.thumbnails.ArtResizer")
    def test_process_album(self, mock_artresizer):
        get_size = mock_artresizer.shared.get_size

        plugin = ThumbnailsPlugin()
        make_cover = plugin.make_cover_thumbnail = Mock(return_value=True)
        make_dolphin = plugin.make_dolphin_cover_thumbnail = Mock()

        # no art
        album = Mock(art_filepath=None)
        plugin.process_album(album)
        assert get_size.call_count == 0
        assert make_dolphin.call_count == 0

        # cannot get art size
        album.art_filepath = b"/path/to/art"
        get_size.return_value = None
        plugin.process_album(album)
        get_size.assert_called_once_with(album.art_filepath)
        assert make_cover.call_count == 0

        # dolphin tests
        plugin.config["dolphin"] = False
        plugin.process_album(album)
        assert make_dolphin.call_count == 0

        plugin.config["dolphin"] = True
        plugin.process_album(album)
        make_dolphin.assert_called_once_with(album.filepath, album.art_filepath)

        # small art
        get_size.return_value = 200, 200
        plugin.process_album(album)
        make_cover.assert_called_once_with(
            album, album.art_filepath, 128, NORMAL_DIR
        )

        # big art
        make_cover.reset_mock()
        get_size.return_value = 500, 500
        plugin.process_album(album)
        make_cover.assert_has_calls(
            [
                call(album, album.art_filepath, 128, NORMAL_DIR),
                call(album, album.art_filepath, 256, LARGE_DIR),
            ],
            any_order=True,
        )

    @patch("beetsplug.thumbnails.ThumbnailsPlugin._check_local_ok", Mock())
    def test_invokations(self):
        plugin = ThumbnailsPlugin()
        plugin.process_album = Mock()
        album = Mock()

        plugin.process_album.reset_mock()
        lib = Mock()
        album2 = Mock()
        lib.albums.return_value = [album, album2]
        plugin.process_query(lib, Mock(), None)
        plugin.process_album.assert_has_calls(
            [call(album), call(album2)], any_order=True
        )

    def test_thumbnail_file_name(self):
        plug = ThumbnailsPlugin()
        plug.get_uri = Mock(return_value="file:///my/uri")
        assert (
            plug.thumbnail_file_name(Path("idontcare"))
            == "9488f5797fbe12ffb316d607dfd93d04.png"
        )

    def test_uri(self):
        gio = GioURI()
        if not gio.available:
            self.skipTest("GIO library not found")

        assert gio.uri("/foo") == "file:///foo"
        assert gio.uri("/foo!") == "file:///foo!"
        assert gio.uri("/music/싸이") == "file:///music/%EC%8B%B8%EC%9D%B4"


class TestPathlibURI:
    """Test PathlibURI class"""

    def test_uri(self):
        test_uri = PathlibURI()

        # test it won't break if we pass it str for a path
        test_uri.uri("/")
