from __future__ import annotations

import ctypes
import sys
from typing import TYPE_CHECKING, Any, ClassVar
from unittest import mock

from beets import importer
from beets.test.helper import (
    AutotagImportHelper,
    IOMixin,
    PluginMixin,
    PluginTestHelper,
)
from beetsplug.fetchart import (
    Candidate,
    CoverArtArchive,
    FetchArtPlugin,
    FileSystem,
    _logged_get,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestFetchartImport(PluginMixin, AutotagImportHelper):
    plugin = "fetchart"
    preload_plugin = False
    plugin_defaults: ClassVar[Any] = {"sources": ["filesystem", "coverart"]}

    def setup_beets(self):
        super().setup_beets()

        self.prepare_album_for_import(1)
        self.setup_importer()

        self.local_art_patcher = mock.patch.object(
            FileSystem, "get", autospec=True, return_value=iter(())
        )
        self.local_art_mock = self.local_art_patcher.start()
        self.remote_art_patcher = mock.patch.object(
            CoverArtArchive, "get", autospec=True, return_value=iter(())
        )
        self.remote_art_mock = self.remote_art_patcher.start()

    def teardown_beets(self):
        super().teardown_beets()
        self.local_art_patcher.stop()
        self.remote_art_patcher.stop()

    def test_asis_skips_network_sources(self):
        self.importer.add_choice(importer.Action.ASIS)
        with self.configure_plugin(self.plugin_defaults):
            self.importer.run()
        self.local_art_mock.assert_called()
        self.remote_art_mock.assert_not_called()

    def test_apply_uses_network_sources(self):
        self.importer.add_choice(importer.Action.APPLY)
        with self.configure_plugin(self.plugin_defaults):
            self.importer.run()
        self.local_art_mock.assert_called()
        self.remote_art_mock.assert_called()

    def test_fetch_for_asis_uses_network_sources(self):
        self.importer.add_choice(importer.Action.ASIS)
        with self.configure_plugin(
            self.plugin_defaults | {"fetch_for_asis": True}
        ):
            self.importer.run()
        self.local_art_mock.assert_called()
        self.remote_art_mock.assert_called()


class TestFetchartCli(IOMixin, PluginTestHelper):
    plugin = "fetchart"

    def setup_beets(self):
        super().setup_beets()
        self.config["fetchart"]["cover_names"] = "c\xc3\xb6ver.jpg"
        self.config["art_filename"] = "mycover"
        self.album = self.add_album()
        self.album.filepath.mkdir(parents=True)

    def cover_path(self, ext: str = "jpg"):
        return self.album.filepath / f"mycover.{ext}"

    def check_cover_is_stored(self, ext: str = "jpg"):
        cover_path = self.cover_path(ext)
        assert cover_path == self.album.art_filepath
        assert cover_path.read_text() == "IMAGE"

    def hide_file_windows(self, path: Path) -> None:
        if sys.platform == "win32":
            hidden_mask = 2
            assert ctypes.windll.kernel32.SetFileAttributesW(
                str(path), hidden_mask
            )

    def test_set_art_from_folder(self):
        (self.album.filepath / "c\xc3\xb6ver.jpg").write_text("IMAGE")

        self.run_command("fetchart")

        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_does_not_pick_up_folder(self):
        self.run_command("fetchart")
        self.album.load()
        assert self.album["artpath"] is None

    def test_filesystem_does_not_pick_up_ignored_file(self):
        (self.album.filepath / "co_ver.jpg").write_text("IMAGE")
        self.config["ignore"] = ["*_*"]
        self.run_command("fetchart")
        self.album.load()
        assert self.album["artpath"] is None

    def test_filesystem_picks_up_non_ignored_file(self):
        (self.album.filepath / "cover.jpg").write_text("IMAGE")
        self.config["ignore"] = ["*_*"]
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_does_not_pick_up_hidden_file(self):
        path = self.album.filepath / ".cover.jpg"
        path.write_text("IMAGE")
        self.hide_file_windows(path)
        self.config["ignore"] = []  # By default, ignore includes '.*'.
        self.config["ignore_hidden"] = True
        self.run_command("fetchart")
        self.album.load()
        assert self.album["artpath"] is None

    def test_filesystem_picks_up_non_hidden_file(self):
        (self.album.filepath / "cover.jpg").write_text("IMAGE")
        self.config["ignore_hidden"] = True
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_picks_up_hidden_file(self):
        path = self.album.filepath / ".cover.jpg"
        path.write_text("IMAGE")
        self.hide_file_windows(path)
        self.config["ignore"] = []  # By default, ignore includes '.*'.
        self.config["ignore_hidden"] = False
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored()

    def test_filesystem_picks_up_webp_file(self):
        (self.album.filepath / "cover.webp").write_text("IMAGE")
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored("webp")

    def test_filesystem_picks_up_png_file(self):
        (self.album.filepath / "cover.png").write_text("IMAGE")
        self.run_command("fetchart")
        self.album.load()
        self.check_cover_is_stored("png")

    def test_colorization(self):
        self.config["ui"]["color"] = True
        out = self.run_with_output("fetchart")
        assert " - the älbum: \x1b[1;31mno art found\x1b[39;49;00m\n" == out

    def test_set_art_oserror_is_handled_gracefully(self):
        """OSError (e.g. PermissionError) in set_art is logged as a warning,
        not an unhandled crash. Regression test for #6193.
        """
        (self.album.filepath / "c\xc3\xb6ver.jpg").write_text("IMAGE")
        with mock.patch(
            "beets.library.Album.set_art",
            side_effect=PermissionError("[WinError 32] file in use"),
        ):
            out = self.run_with_output("fetchart")
        self.album.load()
        assert "error writing album art" in out
        assert self.album["artpath"] is None

    def test_sources_is_a_string(self):
        self.config["fetchart"].set({"sources": "filesystem"})
        fa = FetchArtPlugin()
        assert len(fa.sources) == 1
        assert isinstance(fa.sources[0], FileSystem)

    def test_sources_is_an_asterisk(self):
        self.config["fetchart"].set({"sources": "*"})
        fa = FetchArtPlugin()
        assert len(fa.sources) == 10

    def test_sources_is_a_string_list(self):
        self.config["fetchart"].set({"sources": ["filesystem", "coverart"]})
        fa = FetchArtPlugin()
        assert len(fa.sources) == 3

    def test_sources_is_a_mapping_list(self):
        self.config["fetchart"].set(
            {"sources": {"filesystem": "*", "coverart": "*"}}
        )
        fa = FetchArtPlugin()
        assert len(fa.sources) == 3


class TestFetchartRemoteDownload(PluginTestHelper):
    plugin = "fetchart"

    def test_logged_get_preserves_stream_and_send_kwargs(self):
        log = mock.MagicMock()
        with mock.patch("requests.Session.send") as mock_send:
            mock_send.return_value = mock.MagicMock()
            _logged_get(
                log, "https://example.com/art.jpg", stream=True, timeout=15
            )
            mock_send.assert_called_once()
            _, kwargs = mock_send.call_args
            assert kwargs["stream"] is True
            assert kwargs["timeout"] == 15

    def test_logged_get_default_timeout(self):
        log = mock.MagicMock()
        with mock.patch("requests.Session.send") as mock_send:
            mock_send.return_value = mock.MagicMock()
            _logged_get(log, "https://example.com/art.jpg")
            mock_send.assert_called_once()
            _, kwargs = mock_send.call_args
            assert kwargs["timeout"] == 10

    def test_fetch_image_early_exit_on_http_error(self):
        log = mock.MagicMock()
        source = CoverArtArchive(log, self.config["fetchart"])
        plugin = FetchArtPlugin()
        candidate = Candidate(
            log, source.ID, url="https://example.com/error.jpg"
        )

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 404
        with mock.patch.object(source, "request", return_value=mock_resp):
            source.fetch_image(candidate, plugin)

        assert candidate.path is None
        mock_resp.iter_content.assert_not_called()

    def test_fetch_image_content_length_exceeds_max_filesize(self):
        log = mock.MagicMock()
        source = CoverArtArchive(log, self.config["fetchart"])
        plugin = FetchArtPlugin()
        plugin.max_filesize = 5000
        candidate = Candidate(
            log, source.ID, url="https://example.com/large.jpg"
        )

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Length": "10000"}
        with mock.patch.object(source, "request", return_value=mock_resp):
            source.fetch_image(candidate, plugin)

        assert candidate.path is None
        mock_resp.iter_content.assert_not_called()

    def test_fetch_image_streaming_exceeds_max_filesize(self):
        log = mock.MagicMock()
        source = CoverArtArchive(log, self.config["fetchart"])
        plugin = FetchArtPlugin()
        plugin.max_filesize = 50
        candidate = Candidate(log, source.ID, url="https://example.com/art.jpg")

        # Valid JPEG header (32 bytes) followed by chunk that exceeds 50 bytes total
        jpeg_header = b"\xff\xd8\xff\xe0" + b"\x00" * 28
        chunk = b"x" * 40

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "image/jpeg"}
        mock_resp.iter_content.return_value = iter([jpeg_header, chunk])

        with mock.patch.object(source, "request", return_value=mock_resp):
            source.fetch_image(candidate, plugin)

        assert candidate.path is None

    def test_fetch_image_cleanup_on_download_exception(self):
        import requests

        log = mock.MagicMock()
        source = CoverArtArchive(log, self.config["fetchart"])
        plugin = FetchArtPlugin()
        candidate = Candidate(log, source.ID, url="https://example.com/art.jpg")

        jpeg_header = b"\xff\xd8\xff\xe0" + b"\x00" * 28

        def failing_chunks():
            yield jpeg_header
            raise requests.exceptions.ReadTimeout("read timed out")

        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "image/jpeg"}
        mock_resp.iter_content.return_value = failing_chunks()

        with mock.patch.object(source, "request", return_value=mock_resp):
            source.fetch_image(candidate, plugin)

        assert candidate.path is None
