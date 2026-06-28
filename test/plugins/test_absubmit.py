# This file is part of beets.
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

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from beets.library import Item
from beets.test.helper import PluginTestHelper
from beetsplug.absubmit import AcousticBrainzSubmitPlugin


class TestAcousticBrainzSubmitPlugin(PluginTestHelper):
    plugin = "absubmit"
    preload_plugin = False

    def _make_plugin(self):
        extractor = self.temp_dir_path / "streaming_extractor_music"
        extractor.write_bytes(b"extractor")
        self.config[self.plugin]["extractor"] = str(extractor)

        plugin = AcousticBrainzSubmitPlugin()
        plugin.opts = SimpleNamespace(force_refetch=False, pretend_fetch=False)
        return plugin

    def _write_extractor_output(self, args, payload):
        Path(args[2]).write_bytes(payload)
        return b""

    def test_get_analysis_ignores_invalid_utf8(self):
        plugin = self._make_plugin()
        item = Item(path="/music/item.flac", mb_trackid="track-id")

        payload = (
            b'{"metadata":{"version":{},"tags":{"encodedby":'
            b'["bad \xff bytes"]}}}'
        )
        with patch("beetsplug.absubmit.call") as extractor_call:
            extractor_call.side_effect = lambda args: (
                self._write_extractor_output(args, payload)
            )

            analysis = plugin._get_analysis(item)

        assert analysis["metadata"]["tags"]["encodedby"] == ["bad  bytes"]
        assert analysis["metadata"]["version"]["essentia_build_sha"] == (
            plugin.extractor_sha
        )

    def test_get_analysis_skips_unparseable_json(self, caplog):
        plugin = self._make_plugin()
        item = Item(path="/music/item.flac", mb_trackid="track-id")

        with patch("beetsplug.absubmit.call") as extractor_call:
            extractor_call.side_effect = lambda args: (
                self._write_extractor_output(args, b'{"metadata":')
            )

            with caplog.at_level("WARNING", logger="beets.absubmit"):
                analysis = plugin._get_analysis(item)

        assert analysis is None
        assert "Failed to parse AcousticBrainz analysis" in caplog.text
