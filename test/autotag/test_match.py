from typing import ClassVar

import pytest

from beets import metadata_plugins
from beets.autotag import AlbumInfo, TrackInfo, match
from beets.library import Item


class TestAssignment:
    A = "one"
    B = "two"
    C = "three"

    @pytest.fixture(autouse=True)
    def config(self, config):
        config["match"]["track_length_grace"] = 10
        config["match"]["track_length_max"] = 30

    @pytest.mark.parametrize(
        # 'expected' is a tuple of expected (mapping, extra_items, extra_tracks)
        "item_titles, track_titles, expected",
        [
            # items ordering gets corrected
            ([A, C, B], [A, B, C], ({A: A, B: B, C: C}, [], [])),
            # unmatched tracks are returned as 'extra_tracks'
            # the first track is unmatched
            ([B, C], [A, B, C], ({B: B, C: C}, [], [A])),
            # the middle track is unmatched
            ([A, C], [A, B, C], ({A: A, C: C}, [], [B])),
            # the last track is unmatched
            ([A, B], [A, B, C], ({A: A, B: B}, [], [C])),
            # unmatched items are returned as 'extra_items'
            ([A, C, B], [A, C], ({A: A, C: C}, [B], [])),
        ],
    )
    def test_assign_tracks(self, item_titles, track_titles, expected):
        expected_mapping, expected_extra_items, expected_extra_tracks = expected

        items = [Item(title=title) for title in item_titles]
        tracks = [TrackInfo(title=title) for title in track_titles]

        item_info_pairs, extra_items, extra_tracks = match.assign_items(
            items, tracks
        )

        assert (
            {i.title: t.title for i, t in item_info_pairs},
            [i.title for i in extra_items],
            [t.title for t in extra_tracks],
        ) == (expected_mapping, expected_extra_items, expected_extra_tracks)

    def test_order_works_when_track_names_are_entirely_wrong(self):
        # A real-world test case contributed by a user.
        def item(i, length):
            return Item(
                artist="ben harper",
                album="burn to shine",
                title=f"ben harper - Burn to Shine {i}",
                track=i,
                length=length,
            )

        items = []
        items.append(item(1, 241.37243007106997))
        items.append(item(2, 342.27781704375036))
        items.append(item(3, 245.95070222338137))
        items.append(item(4, 472.87662515485437))
        items.append(item(5, 279.1759535763187))
        items.append(item(6, 270.33333768012))
        items.append(item(7, 247.83435613222923))
        items.append(item(8, 216.54504531525072))
        items.append(item(9, 225.72775379800484))
        items.append(item(10, 317.7643606963552))
        items.append(item(11, 243.57001238834192))
        items.append(item(12, 186.45916150485752))

        def info(index, title, length):
            return TrackInfo(title=title, length=length, index=index)

        trackinfo = []
        trackinfo.append(info(1, "Alone", 238.893))
        trackinfo.append(info(2, "The Woman in You", 341.44))
        trackinfo.append(info(3, "Less", 245.59999999999999))
        trackinfo.append(info(4, "Two Hands of a Prayer", 470.49299999999999))
        trackinfo.append(info(5, "Please Bleed", 277.86599999999999))
        trackinfo.append(info(6, "Suzie Blue", 269.30599999999998))
        trackinfo.append(info(7, "Steal My Kisses", 245.36000000000001))
        trackinfo.append(info(8, "Burn to Shine", 214.90600000000001))
        trackinfo.append(info(9, "Show Me a Little Shame", 224.0929999999999))
        trackinfo.append(info(10, "Forgiven", 317.19999999999999))
        trackinfo.append(info(11, "Beloved One", 243.733))
        trackinfo.append(info(12, "In the Lord's Arms", 186.13300000000001))

        expected = list(zip(items, trackinfo)), [], []

        assert match.assign_items(items, trackinfo) == expected


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

    def check_proposal(self, proposal):
        sources = [
            candidate.info.data_source for candidate in proposal.candidates
        ]
        assert len(sources) == 2
        assert set(sources) == {"Discogs", "Deezer"}

    @pytest.mark.xfail(
        reason="Same ID from different sources is considered a duplicate (#6181)",
        raises=AssertionError,
        strict=True,
    )
    def test_search_album_ids(self, shared_album_id):
        _, _, proposal = match.tag_album([Item()], search_ids=[shared_album_id])

        self.check_proposal(proposal)

    @pytest.mark.xfail(
        reason="Same ID from different sources is considered a duplicate (#6181)",
        raises=AssertionError,
        strict=True,
    )
    def test_search_album_current_id(self, shared_album_id):
        _, _, proposal = match.tag_album([Item(mb_albumid=shared_album_id)])

        self.check_proposal(proposal)

    @pytest.mark.xfail(
        reason="The last match wins",
        raises=AssertionError,
        strict=True,
    )
    def test_search_track_ids(self, shared_track_id):
        proposal = match.tag_item(Item(), search_ids=[shared_track_id])

        self.check_proposal(proposal)

    @pytest.mark.xfail(
        reason="The last match wins",
        raises=AssertionError,
        strict=True,
    )
    def test_search_track_current_id(self, shared_track_id):
        proposal = match.tag_item(Item(mb_trackid=shared_track_id))

        self.check_proposal(proposal)
