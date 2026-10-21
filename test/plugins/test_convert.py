from __future__ import annotations

import fnmatch
import os
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
        self.convert_dest = self.temp_path / "convert_dest"
        self.config["convert"] = {"dest": str(self.convert_dest)}

    def tagged_copy_cmd(self, tag):
        """Return a conversion command that copies files and appends
        `tag` to the copy.
        """
        # A Python script that copies the file and appends a tag.
        stub = str(_common.RSRC / "convert_stub.py")
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
        image_path = _common.RSRC / "image-2x3.jpg"
        self.album.artpath = image_path
        self.album.store()
        image_data = image_path.read_bytes()

        self.io.addinput("y")
        self.run_convert()
        mediafile = MediaFile(self.converted_mp3)
        assert mediafile.images[0].data == image_data

    def test_copy_album_art_missing_source(self, caplog):
        # A missing/stale art source should be skipped instead of crashing
        # the conversion (see #4692).
        self.config["convert"]["copy_album_art"] = True
        self.album.artpath = _common.RSRC / "nonexistent.jpg"
        self.album.store()

        with caplog.at_level("INFO", logger="beets.convert"):
            self.run_command("convert", "-a", "--yes")

        assert any(
            "source file not found" in message for message in caplog.messages
        )
        assert self.file_endswith(self.converted_mp3, "mp3")

    def test_skip_existing(self):
        converted = self.converted_mp3
        util.mkdirall(converted)
        converted.write_text("XXX")
        self.run_convert("--yes")
        assert converted.read_text() == "XXX"

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


class TestFormatMap(ConvertPluginHelper, ConvertCommand):
    """Test the `format_map` option: the target format depends on the source
    format of each file.
    """

    def setup_beets(self):
        super().setup_beets()
        self.config["convert"] = {
            "paths": {"default": "converted"},
            "format": "mp3",
            "format_map": {"flac": "ogg"},
            "formats": {
                "mp3": self.tagged_copy_cmd("mp3"),
                "ogg": self.tagged_copy_cmd("ogg"),
                "opus": {
                    "command": self.tagged_copy_cmd("opus"),
                    "extension": "ops",
                },
            },
        }

    @pytest.mark.parametrize(
        "source_ext,format_map,args,expected_file,expected_tag",
        [
            _p(
                "flac", {"flac": "ogg"}, (), "converted.ogg", "ogg", id="mapped"
            ),
            _p(
                "ogg",
                {"flac": "ogg"},
                (),
                "converted.mp3",
                "mp3",
                id="unmapped",
            ),
            _p("flac", {"FLAC": "ogg"}, (), "converted.ogg", "ogg", id="case"),
            _p(
                "flac",
                {"flac": "ogg"},
                ("--format", "opus"),
                "converted.ops",
                "opus",
                id="cli-format-overrides",
            ),
            _p("flac", {}, (), "converted.mp3", "mp3", id="empty-map"),
        ],
    )
    def test_target_format(
        self, source_ext, format_map, args, expected_file, expected_tag
    ):
        [item] = self.add_item_fixtures(ext=source_ext)
        self.config["convert"]["format_map"] = format_map

        self.io.addinput("y")
        self.run_convert_path(item, *args)

        converted = self.convert_dest / expected_file
        assert self.file_endswith(converted, expected_tag)

    def test_source_already_in_target_format_is_copied(self):
        [item] = self.add_item_fixtures(ext="ogg")
        self.config["convert"]["format_map"] = {"ogg": "ogg"}

        self.io.addinput("y")
        self.run_convert_path(item)

        # The file is copied as is: the stub command did not run.
        assert not self.file_endswith(
            self.convert_dest / "converted.ogg", "ogg"
        )

    def test_mixed_sources_in_one_run(self):
        self.add_item_fixtures(ext="flac")
        self.add_item_fixtures(ext="ogg")

        self.run_command("convert", "--yes")

        # flac is mapped to ogg, ogg falls back to the `format` option.
        assert self.file_endswith(self.convert_dest / "converted.ogg", "ogg")
        assert self.file_endswith(self.convert_dest / "converted.mp3", "mp3")

    def test_playlist_entry_uses_mapped_extension(self):
        [item] = self.add_item_fixtures(ext="flac")

        self.io.addinput("y")
        self.run_convert_path(item, "--playlist", "playlist.m3u8")

        lines = (self.convert_dest / "playlist.m3u8").read_text().splitlines()
        assert lines[1] == "converted.ogg"


class TestGetTargetFormat(PluginTestHelper):
    """Test how the target format is chosen for a single item."""

    plugin = "convert"

    @pytest.mark.parametrize(
        "item_format,format_map,expected",
        [
            _p("WAVE", {"wav": "flac"}, "flac", id="wav-alias"),
            _p("WAVE", {"wave": "flac"}, "flac", id="wave"),
            _p("ALAC", {"alac": "flac"}, "flac", id="alac"),
            _p("MP3", {"alac": "flac"}, "mp3", id="not-in-map"),
        ],
    )
    def test_get_target_format(self, config, item_format, format_map, expected):
        config["convert"]["format_map"] = format_map
        plugin = convert.ConvertPlugin()
        assert plugin.get_target_format(Item(format=item_format)) == expected


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
