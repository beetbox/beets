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


from unittest.mock import MagicMock, patch

import pytest

from beets import metadata_plugins
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.library import Item
from beets.test.helper import ImportTestCase, IOMixin, PluginMixin
from beetsplug import chroma

TEST_TITLE_1 = "TEST_TITLE_1"
TEST_TITLE_2 = "TEST_TITLE_2"
FINGERPRINT_1 = "FP_1"
FINGERPRINT_1_CLOSE = "FP_1_CLOSE"
FINGERPRINT_2 = "FP_2"


@patch("acoustid.compare_fingerprints")
class ChromaTest(IOMixin, PluginMixin, ImportTestCase):
    plugin = "chroma"

    def setup_lib(self):
        item1 = Item(path="/file")
        item1.length = 30
        item1.title = TEST_TITLE_1
        item1.acoustid_fingerprint = FINGERPRINT_1
        item1.add(self.lib)

        item2 = Item(path="/file")
        item2.length = 30
        item2.title = TEST_TITLE_2
        item2.acoustid_fingerprint = FINGERPRINT_2
        item2.add(self.lib)

    def run_search(self, fp):
        return self.run_with_output("chromasearch", "-s", fp, "-f", "$title")

    def line_count(self, str):
        return len(
            [line for line in str.split("\n") if line.strip(" \n") != ""]
        )

    def compare_fingerprints(self, *args, **kwargs):
        if args[0][1] == args[1][1]:
            return 1

        if args[0][1] == FINGERPRINT_1_CLOSE and args[1][1] == FINGERPRINT_1:
            return 0.9

        return 0.1

    def test_chroma_search_exact(self, compare_fingerprints):
        self.setup_lib()
        compare_fingerprints.side_effect = self.compare_fingerprints

        output = self.run_search(FINGERPRINT_2)
        assert self.line_count(output) == 1
        assert TEST_TITLE_2 in output

        output = self.run_search(FINGERPRINT_1)
        assert self.line_count(output) == 1
        assert TEST_TITLE_1 in output

    def test_chroma_search_close(self, compare_fingerprints):
        self.setup_lib()
        compare_fingerprints.side_effect = self.compare_fingerprints

        output = self.run_search(FINGERPRINT_1_CLOSE)
        assert self.line_count(output) == 2
        assert TEST_TITLE_1 in output.split("\n")[0]


def _seed_acoustid_match(
    item_path: bytes = b"/fake/path.mp3",
    recording_ids: list[str] | None = None,
    release_ids: list[str] | None = None,
) -> Item:
    """Seed the chroma module-level match cache as if acoustid had run."""
    if recording_ids is None:
        recording_ids = ["rec-id-1"]
    if release_ids is None:
        release_ids = ["rel-id-1", "rel-id-1", "rel-id-1"]

    chroma._matches[item_path] = (recording_ids, release_ids)
    return Item(path=item_path)


class TestChromaCandidates(PluginMixin):
    """Regression tests for issue #6212: chroma must respect which metadata
    source plugins are enabled.

    When the musicbrainz plugin is not loaded, chroma must not produce any
    MusicBrainz-sourced candidates (via either ``candidates`` or
    ``item_candidates``). When it IS loaded, chroma resolves acoustid
    matches through the registered plugin instance.

    ``plugin`` is intentionally not set on the class so that
    :py:meth:`PluginMixin.load_plugins` honours explicit plugin-name
    arguments and each test can choose its own combination. The autouse
    fixture clears the ``@cache``-decorated metadata-source registry and
    the chroma match state between tests.
    """

    preload_plugin = False

    @pytest.fixture(autouse=True)
    def _setup_chroma(self):
        metadata_plugins.find_metadata_source_plugins.cache_clear()
        metadata_plugins.get_metadata_source.cache_clear()
        chroma._matches.clear()
        yield
        chroma._matches.clear()
        self.unload_plugins()
        metadata_plugins.find_metadata_source_plugins.cache_clear()
        metadata_plugins.get_metadata_source.cache_clear()

    def test_candidates_returns_empty_without_musicbrainz(self):
        self.load_plugins("chroma")
        plugin = chroma.AcoustidPlugin()
        item = _seed_acoustid_match()

        result = plugin.candidates(
            [item], artist="A", album="B", va_likely=False
        )

        assert list(result) == []

    def test_item_candidates_returns_empty_without_musicbrainz(self):
        self.load_plugins("chroma")
        plugin = chroma.AcoustidPlugin()
        item = _seed_acoustid_match()

        result = plugin.item_candidates(item, artist="A", title="B")

        assert list(result) == []

    def test_candidates_returns_mb_albums_with_musicbrainz(self, monkeypatch):
        self.load_plugins("chroma", "musicbrainz")

        fake_album = AlbumInfo(
            tracks=[], album_id="rel-id-1", album="Fake Album"
        )
        mb_plugin = metadata_plugins.get_metadata_source("musicbrainz")
        assert mb_plugin is not None
        monkeypatch.setattr(
            mb_plugin, "album_for_id", MagicMock(return_value=fake_album)
        )

        plugin = chroma.AcoustidPlugin()
        item = _seed_acoustid_match()

        result = list(
            plugin.candidates([item], artist="A", album="B", va_likely=False)
        )

        assert result == [fake_album]
        mb_plugin.album_for_id.assert_called_with("rel-id-1")

    def test_item_candidates_returns_mb_tracks_with_musicbrainz(
        self, monkeypatch
    ):
        self.load_plugins("chroma", "musicbrainz")

        fake_track = TrackInfo(title="Fake Track", track_id="rec-id-1")
        mb_plugin = metadata_plugins.get_metadata_source("musicbrainz")
        assert mb_plugin is not None
        monkeypatch.setattr(
            mb_plugin, "track_for_id", MagicMock(return_value=fake_track)
        )

        plugin = chroma.AcoustidPlugin()
        item = _seed_acoustid_match()

        result = list(plugin.item_candidates(item, artist="A", title="B"))

        assert result == [fake_track]
        mb_plugin.track_for_id.assert_called_with("rec-id-1")
