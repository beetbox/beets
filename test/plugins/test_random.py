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
import unittest
from random import Random

import pytest

from beets.test.helper import TestHelper
from beetsplug import random


class RandomTest(TestHelper, unittest.TestCase):
    def setUp(self):
        self.lib = None
        self.artist1 = "Artist 1"
        self.artist2 = "Artist 2"
        self.item1 = self.create_item(artist=self.artist1)
        self.item2 = self.create_item(artist=self.artist2)
        self.items = [self.item1, self.item2]
        for _ in range(8):
            self.items.append(self.create_item(artist=self.artist2))
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

    def test_equal_permutation_empty_input(self):
        """Test _equal_chance_permutation with empty input."""
        result = list(random._equal_chance_permutation([], "artist"))
        assert result == []

    def test_equal_permutation_single_item(self):
        """Test _equal_chance_permutation with single item."""
        result = list(random._equal_chance_permutation([self.item1], "artist"))
        assert result == [self.item1]

    def test_equal_permutation_single_artist(self):
        """Test _equal_chance_permutation with items from one artist."""
        items = [self.create_item(artist=self.artist1) for _ in range(5)]
        result = list(random._equal_chance_permutation(items, "artist"))
        assert set(result) == set(items)
        assert len(result) == len(items)

    def test_random_objs_count(self):
        """Test random_objs with count-based selection."""
        result = random.random_objs(
            self.items, number=3, random_gen=self.random_gen
        )
        assert len(result) == 3
        assert all(item in self.items for item in result)

    def test_random_objs_time(self):
        """Test random_objs with time-based selection."""
        # Total length is 30 + 60 + 8*45 = 450 seconds
        # Requesting 120 seconds should return 2-3 items
        result = random.random_objs(
            self.items,
            time=2,
            random_gen=self.random_gen,  # 2 minutes = 120 sec
        )
        total_time = sum(item.length for item in result)
        assert total_time <= 120
        # Check we got at least some items
        assert len(result) > 0

    def test_random_objs_equal_chance(self):
        """Test random_objs with equal_chance=True."""

        # With equal_chance, artist1 should appear more often in results
        def experiment():
            """Run the random_objs function multiple times and collect results."""
            results = []
            for _ in range(5000):
                result = random.random_objs(
                    [self.item1, self.item2],
                    number=1,
                    equal_chance=True,
                    random_gen=self.random_gen,
                )
                results.append(result[0].artist)

            # Return ratio
            return results.count(self.artist1), results.count(self.artist2)

        count_artist1, count_artist2 = experiment()
        assert 1 - count_artist1 / count_artist2 < 0.1  # 10% deviation

    def test_random_objs_empty_input(self):
        """Test random_objs with empty input."""
        result = random.random_objs([], number=3)
        assert result == []

    def test_random_objs_zero_number(self):
        """Test random_objs with number=0."""
        result = random.random_objs(self.items, number=0)
        assert result == []
