# This file is part of beets.
# Copyright 2019, Carl Suster
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

"""Test the beets.random utilities associated with the random plugin."""

import math
from random import Random

import pytest

from beets.test.helper import TestHelper
from beetsplug import random


@pytest.fixture(scope="class")
def helper():
    helper = TestHelper()
    helper.setup_beets()

    yield helper

    helper.teardown_beets()


class TestEqualChancePermutation:
    """Test the _equal_chance_permutation function."""

    @pytest.fixture(autouse=True)
    def setup(self, helper):
        """Set up the test environment with items."""
        self.lib = helper.lib
        self.artist1 = "Artist 1"
        self.artist2 = "Artist 2"
        self.item1 = helper.create_item(artist=self.artist1)
        self.item2 = helper.create_item(artist=self.artist2)
        self.items = [self.item1, self.item2]
        for _ in range(8):
            self.items.append(helper.create_item(artist=self.artist2))
        self.random_gen = Random()
        self.random_gen.seed(12345)

    def _stats(self, data):
        mean = sum(data) / len(data)
        stdev = math.sqrt(sum((p - mean) ** 2 for p in data) / (len(data) - 1))
        quot, rem = divmod(len(data), 2)
        if rem:
            median = sorted(data)[quot]
        else:
            median = sum(sorted(data)[quot - 1 : quot + 1]) / 2
        return mean, stdev, median

    def test_equal_permutation(self):
        """We have a list of items where only one item is from artist1 and the
        rest are from artist2. If we permute weighted by the artist field then
        the solo track will almost always end up near the start. If we use a
        different field then it'll be in the middle on average.
        """

        def experiment(field, histogram=False):
            """Permutes the list of items 500 times and calculates the position
            of self.item1 each time. Returns stats about that position.
            """
            positions = []
            for _ in range(500):
                shuffled = list(
                    random._equal_chance_permutation(
                        self.items, field=field, random_gen=self.random_gen
                    )
                )
                positions.append(shuffled.index(self.item1))
            # Print a histogram (useful for debugging).
            if histogram:
                for i in range(len(self.items)):
                    print(f"{i:2d} {'*' * positions.count(i)}")
            return self._stats(positions)

        _, stdev1, median1 = experiment("artist")
        _, stdev2, median2 = experiment("track")
        assert 0 == pytest.approx(median1, abs=1)
        assert len(self.items) // 2 == pytest.approx(median2, abs=1)
        assert stdev2 > stdev1

    @pytest.mark.parametrize(
        "input_items, field, expected",
        [
            ([], "artist", []),
            ([{"artist": "Artist 1"}], "artist", [{"artist": "Artist 1"}]),
            # Missing field should not raise an error, but return empty
            ([{"artist": "Artist 1"}], "nonexistent", []),
            # Multiple items with the same field value
            (
                [{"artist": "Artist 1"}, {"artist": "Artist 1"}],
                "artist",
                [{"artist": "Artist 1"}, {"artist": "Artist 1"}],
            ),
        ],
    )
    def test_equal_permutation_items(
        self, input_items, field, expected, helper
    ):
        """Test _equal_chance_permutation with empty input."""
        result = list(
            random._equal_chance_permutation(
                [helper.create_item(**i) for i in input_items], field
            )
        )

        for item in expected:
            for key, value in item.items():
                assert any(getattr(r, key) == value for r in result)
        assert len(result) == len(expected)


class TestRandomObjs:
    """Test the random_objs function."""

    @pytest.fixture(autouse=True)
    def setup(self, helper):
        """Set up the test environment with items."""
        self.lib = helper.lib
        self.artist1 = "Artist 1"
        self.artist2 = "Artist 2"
        self.items = [
            helper.create_item(artist=self.artist1, length=180),  # 3 minutes
            helper.create_item(artist=self.artist2, length=240),  # 4 minutes
            helper.create_item(artist=self.artist2, length=300),  # 5 minutes
        ]
        self.random_gen = random.Random()

    def test_random_selection_by_count(self):
        """Test selecting a specific number of items."""
        selected = list(random.random_objs(self.items, number=2))
        assert len(selected) == 2
        assert all(item in self.items for item in selected)

    def test_random_selection_by_time(self):
        """Test selecting items constrained by total time (minutes)."""
        selected = list(
            random.random_objs(self.items, time_minutes=6)
        )  # 6 minutes
        total_time = (
            sum(item.length for item in selected) / 60
        )  # Convert to minutes
        assert total_time <= 6

    def test_equal_chance_permutation(self, helper):
        """Test equal chance permutation ensures balanced artist selection."""
        # Add more items to make the test meaningful
        for _ in range(5):
            self.items.append(
                helper.create_item(artist=self.artist1, length=180)
            )

        selected = list(
            random.random_objs(self.items, number=10, equal_chance=True)
        )
        artist_counts = {}
        for item in selected:
            artist_counts[item.artist] = artist_counts.get(item.artist, 0) + 1

        # Ensure both artists are represented (not strictly equal due to randomness)
        assert len(artist_counts) >= 2

    def test_empty_input_list(self):
        """Test behavior with an empty input list."""
        selected = list(random.random_objs([], number=1))
        assert len(selected) == 0

    def test_no_constraints_returns_all(self):
        """Test that no constraints return all items in random order."""
        selected = list(random.random_objs(self.items, 3))
        assert len(selected) == len(self.items)
        assert set(selected) == set(self.items)
