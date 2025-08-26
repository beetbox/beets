# This file is part of beets.
# Copyright 2025, Austin Tinkel.
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

"""Tests for the 'stripfeat' plugin."""

from beets.test.helper import PluginTestCase


class TestStripFeatPlugin(PluginTestCase):
    plugin = "stripfeat"

    def _add_item(self, path, artist, title, album_artist):
        return self.add_item(
            path=path,
            artist=artist,
            artist_sort=artist,
            title=title,
            albumartist=album_artist,
        )

    def _set_config(
        self,
        delimiter=";",
        strip_from_album_artist=False,
        auto=True,
    ):
        self.config["stripfeat"]["delimiter"] = delimiter
        self.config["stripfeat"]["strip_from_album_artist"] = (
            strip_from_album_artist
        )
        self.config["stripfeat"]["auto"] = auto

    def test_strip_feature(self):
        item = self._add_item(
            "/", "Bob Ross feat. Steve Ross", "Happy Little Trees", "Bob Ross"
        )
        self.run_command("stripfeat")
        item.load()
        assert item["artist"] == "Bob Ross;Steve Ross"
        assert item["albumartist"] == "Bob Ross"
        assert item["title"] == "Happy Little Trees"

    def test_strip_from_album_artist(self):
        item = self._add_item(
            "/",
            "Bob Ross feat. Steve Ross",
            "Happy Little Trees",
            "Bob Ross feat. Steve Ross",
        )
        self.run_command("stripfeat", "-a")
        item.load()
        assert item["artist"] == "Bob Ross;Steve Ross"
        assert item["albumartist"] == "Bob Ross;Steve Ross"
        assert item["title"] == "Happy Little Trees"

    def test_no_feature(self):
        item = self._add_item("/", "Bob Ross", "Happy Little Trees", "Bob Ross")
        self.run_command("stripfeat")
        item.load()
        assert item["artist"] == "Bob Ross"
        assert item["albumartist"] == "Bob Ross"
        assert item["title"] == "Happy Little Trees"

    def test_custom_delimiter(self):
        self._set_config(delimiter=" and ")
        item = self._add_item(
            "/", "Bob Ross feat. Steve Ross", "Happy Little Trees", "Bob Ross"
        )
        self.run_command("stripfeat")
        item.load()
        assert item["artist"] == "Bob Ross and Steve Ross"
        assert item["albumartist"] == "Bob Ross"
        assert item["title"] == "Happy Little Trees"

        self._set_config(delimiter=",")
        item = self._add_item(
            "/", "Bob Ross feat. Steve Ross", "Happy Little Trees", "Bob Ross"
        )
        self.run_command("stripfeat")
        item.load()
        assert item["artist"] == "Bob Ross,Steve Ross"
        assert item["albumartist"] == "Bob Ross"
        assert item["title"] == "Happy Little Trees"
