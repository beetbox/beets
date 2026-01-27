from __future__ import annotations

import fnmatch
import os.path
import shlex
import sys
from typing import TYPE_CHECKING

import pytest
from mediafile import MediaFile

from beets import util
from beets.library import Item
from beets.test import _common
from beets.test.helper import (
    AsIsImporterMixin,
    ImportHelper,
    IOMixin,
    PluginTestHelper,
)
from beetsplug import convert

if TYPE_CHECKING:
    from pathlib import Path

_p = pytest.param


class ConvertPluginHelper(IOMixin, PluginTestHelper):
    db_on_disk = True
    plugin = "convert"

    def setup_beets(self):
        super().setup_beets()
        self.convert_dest = self.temp_dir_path / "convert_dest"
        self.config["convert"] = {"dest": str(self.convert_dest)}

    def tagged_copy_cmd(self, tag):
        """Return a conversion command that copies files and appends
        `tag` to the copy.
        """
        # A Python script that copies the file and appends a tag.
        stub = os.path.join(_common.RSRC, b"convert_stub.py").decode("utf-8")
        return f"{shlex.quote(sys.executable)} {shlex.quote(stub)} $source $dest {tag}"

    def file_endswith(self, path: Path, tag: str):
        """Check the path is a file and if its content ends with `tag`."""
        assert path.exists()
        assert path.is_file()
        return path.read_bytes().endswith(tag.encode("utf-8"))


class TestImportConvert(AsIsImporterMixin, ImportHelper, ConvertPluginHelper):
    def setup_beets(self):
        super().setup_beets()
        self.config["convert"] = {
            "command": self.tagged_copy_cmd("convert"),
            # Enforce running convert
            "max_bitrate": 1,
            "auto": True,
            "quiet": False,
        }

    def test_import_converted(self):
        self.run_asis_importer()
        item = self.lib.items().get()
        assert self.file_endswith(item.filepath, "convert")

    # FIXME: fails on windows
    @pytest.mark.skipif(sys.platform == "win32", reason="win32")
    def test_import_original_on_convert_error(self):
        # `false` exits with non-zero code
        self.config["convert"]["command"] = "false"
        self.run_asis_importer()

        item = self.lib.items().get()
        assert item is not None
        assert item.filepath.is_file()

    def test_delete_originals(self):
        self.config["convert"]["delete_originals"] = True
        self.run_asis_importer()
        for path in self.importer.paths:
            for root, dirnames, filenames in os.walk(path):
                assert len(fnmatch.filter(filenames, "*.mp3")) == 0, (
                    f"Non-empty import directory {util.displayable_path(path)}"
                )


class ConvertCommand:
    """A mixin providing a utility method to run the `convert`command
    in tests.
    """

    def run_convert_path(self, item, *args):
        """Run the `convert` command on a given path."""
        return self.run_command("convert", *args, f"path:{item.filepath}")

    def run_convert(self, *args):
        """Run the `convert` command on `self.item`."""
        return self.run_convert_path(self.item, *args)


class TestConvertCli(ConvertPluginHelper, ConvertCommand):
    def setup_beets(self):
        super().setup_beets()
        self.album = self.add_album_fixture(ext="ogg")
        self.item = self.album.items()[0]

        self.converted_mp3 = self.convert_dest / "converted.mp3"
        self.config["convert"] = {
            "paths": {"default": "converted"},
            "format": "mp3",
            "formats": {
                "mp3": self.tagged_copy_cmd("mp3"),
                "ogg": self.tagged_copy_cmd("ogg"),
                "opus": {
                    "command": self.tagged_copy_cmd("opus"),
                    "extension": "ops",
                },
            },
        }

    def test_convert(self):
        self.io.addinput("y")
        self.run_convert()
        assert self.file_endswith(self.converted_mp3, "mp3")

    def test_convert_with_auto_confirmation(self):
        self.run_convert("--yes")
        assert self.file_endswith(self.converted_mp3, "mp3")

    def test_reject_confirmation(self):
        self.io.addinput("n")
        self.run_convert()
        assert not self.converted_mp3.exists()

    def test_convert_keep_new(self):
        assert self.item.filepath.suffix == ".ogg"

        self.io.addinput("y")
        self.run_convert("--keep-new")

        self.item.load()
        assert self.item.filepath.suffix == ".mp3"

    def test_format_option(self):
        self.io.addinput("y")
        self.run_convert("--format", "opus")
        assert self.file_endswith(self.convert_dest / "converted.ops", "opus")

    def test_embed_album_art(self):
        self.config["convert"]["embed"] = True
        image_path = os.path.join(_common.RSRC, b"image-2x3.jpg")
        self.album.artpath = image_path
        self.album.store()
        with open(os.path.join(image_path), "rb") as f:
            image_data = f.read()

        self.io.addinput("y")
        self.run_convert()
        mediafile = MediaFile(self.converted_mp3)
        assert mediafile.images[0].data == image_data

    def test_copy_album_art_missing_source(self, caplog):
        # A missing/stale art source should be skipped instead of crashing
        # the conversion (see #4692).
        self.config["convert"]["copy_album_art"] = True
        self.album.artpath = os.path.join(_common.RSRC, b"nonexistent.jpg")
        self.album.store()

        with caplog.at_level("INFO", logger="beets.convert"):
            self.run_command("convert", "-a", "--yes")

        assert any(
            "source file not found" in message for message in caplog.messages
        )
        assert self.file_endswith(self.converted_mp3, "mp3")

    def test_skip_existing(self):
        converted = self.converted_mp3
        self.touch(converted, content="XXX")
        self.run_convert("--yes")
        with open(converted) as f:
            assert f.read() == "XXX"

    def test_pretend(self):
        self.run_convert("--pretend")
        assert not self.converted_mp3.exists()

    def test_empty_query(self, caplog):
        with caplog.at_level("INFO", logger="beets.convert"):
            self.run_convert("An impossible query")
        assert caplog.messages[0] == "Empty query result."

    @pytest.mark.parametrize(
        "max_bitrate,convert_format,args,should_transcode",
        [
            _p(5000, "mp3", (), True, id="different-format-high-bitrate"),
            _p(5, "mp3", (), True, id="different-format-low-bitrate"),
            _p(None, "mp3", (), True, id="different-format-no-max-bitrate"),
            _p(5000, "ogg", (), False, id="same-format-high-bitrate"),
            _p(5000, "ogg", ("--force",), True, id="same-format-force"),
            _p(5, "ogg", (), True, id="same-format-low-bitrate"),
            _p(None, "ogg", (), False, id="same-format-no-max-bitrate"),
        ],
    )
    def test_transcode_selection(
        self, max_bitrate, convert_format, args, should_transcode
    ):
        if max_bitrate is not None:
            self.config["convert"]["max_bitrate"] = max_bitrate
        self.config["convert"]["format"] = convert_format

        self.io.addinput("y")
        self.run_convert(*args)

        converted_path = self.convert_dest / f"converted.{convert_format}"
        assert (
            self.file_endswith(converted_path, convert_format)
            is should_transcode
        )

    def test_playlist(self):
        self.io.addinput("y")
        self.run_convert("--playlist", "playlist.m3u8")
        assert (self.convert_dest / "playlist.m3u8").exists()

    def test_playlist_pretend(self):
        self.run_convert("--playlist", "playlist.m3u8", "--pretend")
        assert not (self.convert_dest / "playlist.m3u8").exists()

    @pytest.mark.parametrize(
        "config_overrides",
        [
            _p({"no_convert": "format:ogg"}, id="no-covert"),
            _p({"never_convert_lossy_files": True}, id="never-convert-lossy-files"),
        ],
    )  # fmt: skip
    def test_force_overrides(self, config_overrides):
        [item] = self.add_item_fixtures(ext="ogg")
        self.io.addinput("y")

        with self.configure_plugin(config_overrides):
            self.run_convert_path(item, "--format", "opus", "--force")

        converted = self.convert_dest / "converted.ops"
        assert self.file_endswith(converted, "opus")

    @pytest.mark.parametrize(
        "args,no_convert,expected_entry",
        [
            _p((), None, "converted.mp3", id="config-format"),
            _p(("--format", "opus"), None, "converted.ops", id="cli-format"),
            _p((), "format:ogg", "converted.ogg", id="not-transcoded"),
            _p(("--keep-new",), None, "converted.ogg", id="keep-new"),
        ],
    )
    def test_playlist_entry(self, args, no_convert, expected_entry):
        if no_convert:
            self.config["convert"]["no_convert"] = no_convert

        self.io.addinput("y")
        self.run_convert(*args, "--playlist", "playlist.m3u8")
        lines = (self.convert_dest / "playlist.m3u8").read_text().splitlines()
        assert lines[0] == "#EXTM3U"
        assert lines[1] == expected_entry


class TestNeverConvertLossyFiles(ConvertPluginHelper, ConvertCommand):
    """Test the effect of the `never_convert_lossy_files` option."""

    @pytest.mark.parametrize(
        "source_ext,never_convert_lossy_files,expected_ext,should_convert",
        [
            _p("flac", True, "mp3", True, id="lossless-converts-flag-on"),
            _p("flac", False, "mp3", True, id="lossless-converts-flag-off"),
            _p("ogg", False, "mp3", True, id="lossy-converts-allowed"),
            _p("ogg", True, "ogg", False, id="lossy-kept-prevented"),
        ],
    )
    def test_transcode(
        self,
        source_ext,
        never_convert_lossy_files,
        expected_ext,
        should_convert,
    ):
        [item] = self.add_item_fixtures(ext=source_ext)
        self.io.addinput("y")

        convert_fmt = "mp3"
        config = {
            "paths": {"default": "converted"},
            "format": convert_fmt,
            "formats": {convert_fmt: self.tagged_copy_cmd(convert_fmt)},
            "never_convert_lossy_files": never_convert_lossy_files,
        }
        with self.configure_plugin(config):
            self.run_convert_path(item)

        converted = self.convert_dest / f"converted.{expected_ext}"
        assert self.file_endswith(converted, convert_fmt) is should_convert


class TestNoConvert(PluginTestHelper):
    """Test the effect of the `no_convert` option."""

    plugin = "convert"

    @pytest.mark.parametrize(
        "config_value, should_skip",
        [
            ("", False),
            ("bitrate:320", False),
            ("bitrate:320 format:ogg", False),
            ("bitrate:320 , format:ogg", True),
        ],
    )
    def test_no_convert_skip(self, config, config_value, should_skip):
        item = Item(format="ogg", bitrate=256)
        config["convert"]["no_convert"] = config_value
        assert convert.ConvertPlugin().in_no_convert(item) == should_skip


class ConvertRemoveMissingTest(ConvertPluginHelper, ConvertCommand):
    "Tests the effect of the `remove_missing option`"

    @pytest.fixture(autouse=True)
    def setup_removemissing(self, setup):
        self.item = self.add_item(title="title", album="album", format="ogg")

        self.convert_dest = self.temp_dir_path / "convert_dest"
        self.file_to_remove = self.convert_dest / "to_remove.mp3"
        self.convert_dest.mkdir(parents=True)

        self.config["convert"] = {
            "dest": str(self.convert_dest),
            "format": "mp3",
        }

        with self.file_to_remove.open("w") as f:
            f.write("test")

    def test_convert_not_removemissing(self):
        self.run_convert("--yes")

        assert self.file_to_remove.exists()

    def test_convert_pretend_removemissing(self):
        self.run_convert("--yes", "--remove-missing", "--pretend")

        assert self.file_to_remove.exists()

    def test_convert_removemissing(self):
        self.run_convert("--yes", "--remove-missing")

        assert not self.file_to_remove.exists()

        # This should hit the case where no files to remove are present
        self.run_convert("--remove-missing", "--yes")
