# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.


import fnmatch
import os.path
import re
import sys
import unittest
from pathlib import Path

import pytest
from mediafile import MediaFile

from beets import util
from beets.library import Item
from beets.test import _common
from beets.test.helper import (
    AsIsImporterMixin,
    ImportHelper,
    PluginTestCase,
    capture_log,
    control_stdin,
)
from beetsplug import convert


def shell_quote(text):
    import shlex

    return shlex.quote(text)


class ConvertMixin:
    def tagged_copy_cmd(self, tag):
        """Return a conversion command that copies files and appends
        `tag` to the copy.
        """
        if re.search("[^a-zA-Z0-9]", tag):
            raise ValueError(
                f"tag '{tag}' must only contain letters and digits"
            )

        # A Python script that copies the file and appends a tag.
        stub = os.path.join(_common.RSRC, b"convert_stub.py").decode("utf-8")
        return f"{shell_quote(sys.executable)} {shell_quote(stub)} $source $dest {tag}"

    def file_endswith(self, path: Path, tag: str):
        """Check the path is a file and if its content ends with `tag`."""
        assert path.exists()
        assert path.is_file()
        return path.read_bytes().endswith(tag.encode("utf-8"))


class ConvertTestCase(ConvertMixin, PluginTestCase):
    db_on_disk = True
    plugin = "convert"


@_common.slow_test()
class ImportConvertTest(AsIsImporterMixin, ImportHelper, ConvertTestCase):
    def setUp(self):
        super().setUp()
        self.config["convert"] = {
            "dest": os.path.join(self.temp_dir, b"convert"),
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
    @unittest.skipIf(sys.platform == "win32", "win32")
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

    def get_count_of_import_files(self):
        import_file_count = 0

        for path in self.importer.paths:
            for root, _, filenames in os.walk(path):
                import_file_count += len(filenames)

        return import_file_count


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


@_common.slow_test()
class ConvertCliTest(ConvertTestCase, ConvertCommand):
    def setUp(self):
        super().setUp()
        self.album = self.add_album_fixture(ext="ogg")
        self.item = self.album.items()[0]

        self.convert_dest = self.temp_dir_path / "convert_dest"
        self.converted_mp3 = self.convert_dest / "converted.mp3"
        self.config["convert"] = {
            "dest": str(self.convert_dest),
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
        with control_stdin("y"):
            self.run_convert()
        assert self.file_endswith(self.converted_mp3, "mp3")

    def test_convert_with_auto_confirmation(self):
        self.run_convert("--yes")
        assert self.file_endswith(self.converted_mp3, "mp3")

    def test_reject_confirmation(self):
        with control_stdin("n"):
            self.run_convert()
        assert not self.converted_mp3.exists()

    def test_convert_keep_new(self):
        assert os.path.splitext(self.item.path)[1] == b".ogg"

        with control_stdin("y"):
            self.run_convert("--keep-new")

        self.item.load()
        assert os.path.splitext(self.item.path)[1] == b".mp3"

    def test_format_option(self):
        with control_stdin("y"):
            self.run_convert("--format", "opus")
        assert self.file_endswith(self.convert_dest / "converted.ops", "opus")

    def test_embed_album_art(self):
        self.config["convert"]["embed"] = True
        image_path = os.path.join(_common.RSRC, b"image-2x3.jpg")
        self.album.artpath = image_path
        self.album.store()
        with open(os.path.join(image_path), "rb") as f:
            image_data = f.read()

        with control_stdin("y"):
            self.run_convert()
        mediafile = MediaFile(self.converted_mp3)
        assert mediafile.images[0].data == image_data

    def test_skip_existing(self):
        converted = self.converted_mp3
        self.touch(converted, content="XXX")
        self.run_convert("--yes")
        with open(converted) as f:
            assert f.read() == "XXX"

    def test_pretend(self):
        self.run_convert("--pretend")
        assert not self.converted_mp3.exists()

    def test_empty_query(self):
        with capture_log("beets.convert") as logs:
            self.run_convert("An impossible query")
        assert logs[0] == "convert: Empty query result."

    def test_no_transcode_when_maxbr_set_high_and_different_formats(self):
        self.config["convert"]["max_bitrate"] = 5000
        with control_stdin("y"):
            self.run_convert()
        assert self.file_endswith(self.converted_mp3, "mp3")

    def test_transcode_when_maxbr_set_low_and_different_formats(self):
        self.config["convert"]["max_bitrate"] = 5
        with control_stdin("y"):
            self.run_convert()
        assert self.file_endswith(self.converted_mp3, "mp3")

    def test_transcode_when_maxbr_set_to_none_and_different_formats(self):
        with control_stdin("y"):
            self.run_convert()
        assert self.file_endswith(self.converted_mp3, "mp3")

    def test_no_transcode_when_maxbr_set_high_and_same_formats(self):
        self.config["convert"]["max_bitrate"] = 5000
        self.config["convert"]["format"] = "ogg"
        with control_stdin("y"):
            self.run_convert()
        assert not self.file_endswith(
            self.convert_dest / "converted.ogg", "ogg"
        )

    def test_transcode_when_maxbr_set_low_and_same_formats(self):
        self.config["convert"]["max_bitrate"] = 5
        self.config["convert"]["format"] = "ogg"
        with control_stdin("y"):
            self.run_convert()
        assert self.file_endswith(self.convert_dest / "converted.ogg", "ogg")

    def test_transcode_when_maxbr_set_to_none_and_same_formats(self):
        self.config["convert"]["format"] = "ogg"
        with control_stdin("y"):
            self.run_convert()
        assert not self.file_endswith(
            self.convert_dest / "converted.ogg", "ogg"
        )

    def test_playlist(self):
        with control_stdin("y"):
            self.run_convert("--playlist", "playlist.m3u8")
        assert (self.convert_dest / "playlist.m3u8").exists()

    def test_playlist_pretend(self):
        self.run_convert("--playlist", "playlist.m3u8", "--pretend")
        assert not (self.convert_dest / "playlist.m3u8").exists()


@_common.slow_test()
class NeverConvertLossyFilesTest(ConvertTestCase, ConvertCommand):
    """Test the effect of the `never_convert_lossy_files` option."""

    def setUp(self):
        super().setUp()

        self.convert_dest = self.temp_dir_path / "convert_dest"
        self.config["convert"] = {
            "dest": str(self.convert_dest),
            "paths": {"default": "converted"},
            "never_convert_lossy_files": True,
            "format": "mp3",
            "formats": {
                "mp3": self.tagged_copy_cmd("mp3"),
            },
        }

    def test_transcode_from_lossless(self):
        [item] = self.add_item_fixtures(ext="flac")
        with control_stdin("y"):
            self.run_convert_path(item)
        converted = self.convert_dest / "converted.mp3"
        assert self.file_endswith(converted, "mp3")

    def test_transcode_from_lossy(self):
        self.config["convert"]["never_convert_lossy_files"] = False
        [item] = self.add_item_fixtures(ext="ogg")
        with control_stdin("y"):
            self.run_convert_path(item)
        converted = self.convert_dest / "converted.mp3"
        assert self.file_endswith(converted, "mp3")

    def test_transcode_from_lossy_prevented(self):
        [item] = self.add_item_fixtures(ext="ogg")
        with control_stdin("y"):
            self.run_convert_path(item)
        converted = self.convert_dest / "converted.ogg"
        assert not self.file_endswith(converted, "mp3")


class TestNoConvert:
    """Test the effect of the `no_convert` option."""

    @pytest.mark.parametrize(
        "config_value, should_skip",
        [
            ("", False),
            ("bitrate:320", False),
            ("bitrate:320 format:ogg", False),
            ("bitrate:320 , format:ogg", True),
        ],
    )
    def test_no_convert_skip(self, config_value, should_skip):
        item = Item(format="ogg", bitrate=256)
        convert.config["convert"]["no_convert"] = config_value
        assert convert.in_no_convert(item) == should_skip
