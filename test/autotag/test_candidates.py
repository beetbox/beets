from typing import ClassVar

import pytest

from beets import metadata_plugins
from beets.autotag import (
    AlbumCandidates,
    AlbumInfo,
    Source,
    TrackCandidates,
    TrackInfo,
)
from beets.library import Item


class TestTagMultipleDataSources:
    @pytest.fixture
    def shared_track_id(self):
        return "track-12345"

    @pytest.fixture
    def shared_album_id(self):
        return "album-12345"

    @pytest.fixture(autouse=True)
    def _setup_plugins(self, monkeypatch, shared_album_id, shared_track_id):
        class StubPlugin:
            data_source: ClassVar[str]
            data_source_mismatch_penalty = 0

            @property
            def track(self):
                return TrackInfo(
                    artist="Artist",
                    title="Title",
                    track_id=shared_track_id,
                    data_source=self.data_source,
                )

            @property
            def album(self):
                return AlbumInfo(
                    [self.track],
                    artist="Albumartist",
                    album="Album",
                    album_id=shared_album_id,
                    data_source=self.data_source,
                )

            def albums_for_ids(self, *_):
                yield self.album

            def tracks_for_ids(self, *_):
                yield self.track

            def candidates(self, *_, **__):
                yield self.album

            def item_candidates(self, *_, **__):
                yield self.track

        class DeezerPlugin(StubPlugin):
            data_source = "Deezer"

        class DiscogsPlugin(StubPlugin):
            data_source = "Discogs"

        monkeypatch.setattr(
            metadata_plugins,
            "find_metadata_source_plugins",
            lambda: [DeezerPlugin(), DiscogsPlugin()],
        )

    def check_candidates(self, candidates):
        sources = [m.info.data_source for m in candidates.matches]
        assert len(sources) == 2
        assert set(sources) == {"Discogs", "Deezer"}

    def test_search_album_ids(self, shared_album_id):
        source = Source.from_items([Item()])

        candidates = AlbumCandidates(source)
        candidates.resolve([shared_album_id])

        self.check_candidates(candidates)

    def test_search_album_current_id(self, shared_album_id):
        source = Source.from_items([Item(mb_albumid=shared_album_id)])

        candidates = AlbumCandidates(source)
        candidates.resolve([])

        self.check_candidates(candidates)

    def test_search_track_ids(self, shared_track_id):
        source = Source.from_item(Item())

        candidates = TrackCandidates(source)
        candidates.resolve([shared_track_id])

        self.check_candidates(candidates)

    def test_search_track_current_id(self, shared_track_id):
        source = Source.from_item(Item(mb_trackid=shared_track_id))

        candidates = TrackCandidates(source)
        candidates.resolve([])

        self.check_candidates(candidates)
