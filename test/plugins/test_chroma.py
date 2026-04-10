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

import beets.plugins
from beets import config, metadata_plugins
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


# -----------------------------------------------------------------------------
# Regression tests for issue #6212: chroma must not produce MusicBrainz-sourced
# autotagger candidates when the musicbrainz plugin is not enabled.
# -----------------------------------------------------------------------------


@pytest.fixture
def reset_plugin_state():
    """Fully reset plugin and metadata-plugin state around each test.

    ``beets.plugins._instances`` is a module-level list and
    ``metadata_plugins.get_metadata_source`` / ``find_metadata_source_plugins``
    are ``@cache`` decorated, so tests that change the loaded plugin set
    must clear both.
    """
    beets.plugins.BeetsPlugin.listeners.clear()
    beets.plugins.BeetsPlugin._raw_listeners.clear()
    beets.plugins._instances.clear()
    config["plugins"] = []
    metadata_plugins.find_metadata_source_plugins.cache_clear()
    metadata_plugins.get_metadata_source.cache_clear()
    chroma._matches.clear()

    yield

    chroma._matches.clear()
    beets.plugins.BeetsPlugin.listeners.clear()
    beets.plugins.BeetsPlugin._raw_listeners.clear()
    beets.plugins._instances.clear()
    config["plugins"] = []
    metadata_plugins.find_metadata_source_plugins.cache_clear()
    metadata_plugins.get_metadata_source.cache_clear()


def _load_plugins(*names: str) -> None:
    """Load the given plugins into the global beets plugin registry."""
    config["plugins"] = list(names)
    beets.plugins.load_plugins()


def _seed_acoustid_match(
    item_path: bytes = b"/fake/path.mp3",
    recording_ids: list[str] | None = None,
    release_ids: list[str] | None = None,
) -> Item:
    """Seed the chroma module-level match cache as if acoustid had run."""
    if recording_ids is None:
        recording_ids = ["rec-id-1"]
    if release_ids is None:
        # Three copies to exceed COMMON_REL_THRESH in _all_releases.
        release_ids = ["rel-id-1", "rel-id-1", "rel-id-1"]

    chroma._matches[item_path] = (recording_ids, release_ids)
    return Item(path=item_path)


@pytest.mark.usefixtures("reset_plugin_state")
class TestChromaWithoutMusicBrainz:
    """Regression tests for issue #6212.

    When the ``musicbrainz`` plugin is not loaded, acoustid must not
    return any candidates. Before the fix, chroma created its own
    ``MusicBrainzPlugin`` instance directly, bypassing the plugin
    registry, so MusicBrainz-sourced candidates would surface regardless
    of the user's plugin configuration.
    """

    def test_candidates_returns_empty_without_musicbrainz(self):
        _load_plugins("chroma")
        plugin = chroma.AcoustidPlugin()

        item = _seed_acoustid_match()

        result = plugin.candidates(
            [item], artist="A", album="B", va_likely=False
        )

        assert list(result) == []

    def test_item_candidates_returns_empty_without_musicbrainz(self):
        _load_plugins("chroma")
        plugin = chroma.AcoustidPlugin()

        item = _seed_acoustid_match()

        result = plugin.item_candidates(item, artist="A", title="B")

        assert list(result) == []


@pytest.mark.usefixtures("reset_plugin_state")
class TestChromaWithMusicBrainz:
    """Ensure candidates are still produced when musicbrainz IS loaded.

    The fix routes chroma through ``get_metadata_source("musicbrainz")``
    rather than a private ``MusicBrainzPlugin`` instance; we verify both
    that results flow through and that the shared registry instance is
    the one being invoked.
    """

    def test_candidates_returns_albums_when_musicbrainz_enabled(
        self, monkeypatch
    ):
        _load_plugins("chroma", "musicbrainz")

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

    def test_item_candidates_returns_tracks_when_musicbrainz_enabled(
        self, monkeypatch
    ):
        _load_plugins("chroma", "musicbrainz")

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
