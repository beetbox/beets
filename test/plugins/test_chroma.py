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
# Tests for issue #6212: chroma must respect which metadata source plugins are
# enabled. Acoustid fingerprinting only returns MusicBrainz IDs, so chroma
# queries MusicBrainz for release data but then routes the result through the
# metadata source plugins the user has actually enabled — including cross-
# referencing to Spotify / Discogs / etc. via the release's ``url-relations``.
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


def _fake_mb_album(
    album_id: str = "rel-id-1",
    title: str = "Fake MB Album",
    spotify_id: str | None = None,
    discogs_id: str | None = None,
) -> AlbumInfo:
    """Build a MusicBrainz-flavored ``AlbumInfo`` with cross-reference IDs."""
    info = AlbumInfo(
        tracks=[], album_id=album_id, album=title, data_source="MusicBrainz"
    )
    if spotify_id is not None:
        info.spotify_album_id = spotify_id
    if discogs_id is not None:
        info.discogs_album_id = discogs_id
    return info


@pytest.mark.usefixtures("reset_plugin_state")
class TestChromaWithoutCrossRefTargets:
    """Baseline: with no compatible metadata sources, chroma yields nothing.

    When neither the ``musicbrainz`` plugin nor any of the MusicBrainz
    cross-reference targets (Discogs/Bandcamp/Spotify/Deezer/Tidal) are
    loaded, there is nothing acoustid can route its match IDs into, so
    ``candidates`` and ``item_candidates`` must return empty without
    making any network requests.
    """

    def test_candidates_returns_empty_when_nothing_to_route_to(self):
        _load_plugins("chroma")
        plugin = chroma.AcoustidPlugin()

        item = _seed_acoustid_match()

        result = plugin.candidates(
            [item], artist="A", album="B", va_likely=False
        )

        assert list(result) == []
        # We must not have constructed a private MB client — there was
        # no enabled target to route MB results into.
        assert plugin._private_mb is None

    def test_item_candidates_returns_empty_without_musicbrainz(self):
        _load_plugins("chroma")
        plugin = chroma.AcoustidPlugin()

        item = _seed_acoustid_match()

        result = plugin.item_candidates(item, artist="A", title="B")

        assert list(result) == []


@pytest.mark.usefixtures("reset_plugin_state")
class TestChromaWithMusicBrainzOnly:
    """Existing behaviour: chroma + musicbrainz returns MB candidates."""

    def test_candidates_returns_mb_albums(self, monkeypatch):
        _load_plugins("chroma", "musicbrainz")

        fake_album = _fake_mb_album()
        mb_plugin = metadata_plugins.get_metadata_source("musicbrainz")
        assert mb_plugin is not None
        mock_album_for_id = MagicMock(return_value=fake_album)
        monkeypatch.setattr(mb_plugin, "album_for_id", mock_album_for_id)

        plugin = chroma.AcoustidPlugin()
        item = _seed_acoustid_match()

        result = list(
            plugin.candidates([item], artist="A", album="B", va_likely=False)
        )

        assert result == [fake_album]
        mock_album_for_id.assert_called_once_with(
            "rel-id-1", extra_external_sources=None
        )

    def test_item_candidates_returns_mb_tracks(self, monkeypatch):
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


@pytest.mark.usefixtures("reset_plugin_state")
class TestChromaWithExternalOnly:
    """chroma + spotify but NO musicbrainz plugin.

    Chroma must still query MusicBrainz (via a private, unregistered
    ``MusicBrainzPlugin`` instance) to resolve the acoustid release ID,
    extract the Spotify cross-reference ID from the MB release's
    ``url-relations``, and yield the Spotify-sourced candidate instead
    of the MB-sourced one. This is the core feedback semohr left on
    the PR for issue #6212.
    """

    def test_candidates_routes_acoustid_via_mb_to_spotify(self, monkeypatch):
        _load_plugins("chroma", "spotify")

        # MB plugin is NOT loaded — chroma should construct a private
        # MB client. We pre-populate ``_private_mb`` with a mock to
        # avoid the real import / network call.
        mb_mock = MagicMock()
        mb_mock.album_for_id = MagicMock(
            return_value=_fake_mb_album(spotify_id="spot-release-999")
        )

        spotify_plugin = metadata_plugins.get_metadata_source("spotify")
        assert spotify_plugin is not None
        fake_spotify_album = AlbumInfo(
            tracks=[],
            album_id="spot-release-999",
            album="Fake Spotify Album",
            data_source="Spotify",
        )
        monkeypatch.setattr(
            spotify_plugin,
            "album_for_id",
            MagicMock(return_value=fake_spotify_album),
        )

        plugin = chroma.AcoustidPlugin()
        plugin._private_mb = mb_mock
        item = _seed_acoustid_match()

        result = list(
            plugin.candidates([item], artist="A", album="B", va_likely=False)
        )

        # The MB-sourced candidate must NOT appear (musicbrainz plugin
        # not loaded), but the Spotify cross-reference must.
        assert result == [fake_spotify_album]

        # MB was asked to populate the Spotify external ID.
        mb_mock.album_for_id.assert_called_once_with(
            "rel-id-1", extra_external_sources={"spotify"}
        )
        spotify_plugin.album_for_id.assert_called_once_with("spot-release-999")

    def test_item_candidates_still_gated_without_musicbrainz(self):
        """Track path stays gated even when other sources are loaded.

        MusicBrainz recording responses do not carry cross-source
        track IDs the way releases do, so there is no equivalent
        routing path for ``item_candidates``.
        """
        _load_plugins("chroma", "spotify")
        plugin = chroma.AcoustidPlugin()
        item = _seed_acoustid_match()

        result = plugin.item_candidates(item, artist="A", title="B")

        assert list(result) == []


@pytest.mark.usefixtures("reset_plugin_state")
class TestChromaWithMusicBrainzAndExternal:
    """chroma + musicbrainz + spotify must yield BOTH kinds of candidates."""

    def test_candidates_yields_mb_and_spotify(self, monkeypatch):
        _load_plugins("chroma", "musicbrainz", "spotify")

        fake_mb_album = _fake_mb_album(spotify_id="spot-release-42")
        mb_plugin = metadata_plugins.get_metadata_source("musicbrainz")
        assert mb_plugin is not None
        mb_mock = MagicMock(return_value=fake_mb_album)
        monkeypatch.setattr(mb_plugin, "album_for_id", mb_mock)

        fake_spotify_album = AlbumInfo(
            tracks=[],
            album_id="spot-release-42",
            album="Fake Spotify Album",
            data_source="Spotify",
        )
        spotify_plugin = metadata_plugins.get_metadata_source("spotify")
        assert spotify_plugin is not None
        monkeypatch.setattr(
            spotify_plugin,
            "album_for_id",
            MagicMock(return_value=fake_spotify_album),
        )

        plugin = chroma.AcoustidPlugin()
        item = _seed_acoustid_match()

        result = list(
            plugin.candidates([item], artist="A", album="B", va_likely=False)
        )

        assert fake_mb_album in result
        assert fake_spotify_album in result
        # MB was instructed to populate the Spotify cross-ref.
        mb_mock.assert_called_once_with(
            "rel-id-1", extra_external_sources={"spotify"}
        )
        spotify_plugin.album_for_id.assert_called_once_with("spot-release-42")

    def test_candidates_skips_external_without_matching_id(self, monkeypatch):
        """No external candidate when MB release has no cross-ref link."""
        _load_plugins("chroma", "musicbrainz", "spotify")

        # Note: no spotify_id on the fake MB album.
        fake_mb_album = _fake_mb_album()
        mb_plugin = metadata_plugins.get_metadata_source("musicbrainz")
        assert mb_plugin is not None
        monkeypatch.setattr(
            mb_plugin,
            "album_for_id",
            MagicMock(return_value=fake_mb_album),
        )

        spotify_plugin = metadata_plugins.get_metadata_source("spotify")
        assert spotify_plugin is not None
        spotify_mock = MagicMock()
        monkeypatch.setattr(spotify_plugin, "album_for_id", spotify_mock)

        plugin = chroma.AcoustidPlugin()
        item = _seed_acoustid_match()

        result = list(
            plugin.candidates([item], artist="A", album="B", va_likely=False)
        )

        assert result == [fake_mb_album]
        spotify_mock.assert_not_called()
