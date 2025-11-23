import pytest

from beets.autotag import TrackInfo, match
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
