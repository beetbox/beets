"""Tests for the 'limit' plugin."""

from beets.test.helper import IOMixin, PluginTestCase


class LimitPluginTest(IOMixin, PluginTestCase):
    """Unit tests for LimitPlugin

    Note: query prefix tests do not work correctly with `run_with_output`.
    """

    plugin = "limit"

    def setUp(self):
        super().setUp()

        # we'll create an even number of tracks in the library
        self.num_test_items = 10
        assert self.num_test_items % 2 == 0
        for item_no, item in enumerate(
            self.add_item_fixtures(count=self.num_test_items)
        ):
            item.track = item_no + 1
            item.store()

        # our limit tests will use half of this number
        self.num_limit = self.num_test_items // 2
        self.num_limit_prefix = "".join(["'", "<", str(self.num_limit), "'"])

        # a subset of tests has only `num_limit` results, identified by a
        # range filter on the track number
        self.track_head_range = f"track:..{self.num_limit}"
        self.track_tail_range = f"track:{self.num_limit + 1}{'..'}"

    def test_no_limit(self):
        """Returns all when there is no limit or filter."""
        result = self.run_with_output("lslimit")
        assert result.count("\n") == self.num_test_items

    def test_lslimit_head(self):
        """Returns the expected number with `lslimit --head`."""
        result = self.run_with_output("lslimit", "--head", str(self.num_limit))
        assert result.count("\n") == self.num_limit

    def test_lslimit_tail(self):
        """Returns the expected number with `lslimit --tail`."""
        result = self.run_with_output("lslimit", "--tail", str(self.num_limit))
        assert result.count("\n") == self.num_limit

    def test_lslimit_head_invariant(self):
        """Returns the expected number with `lslimit --head` and a filter."""
        result = self.run_with_output(
            "lslimit", "--head", str(self.num_limit), self.track_tail_range
        )
        assert result.count("\n") == self.num_limit

    def test_lslimit_tail_invariant(self):
        """Returns the expected number with `lslimit --tail` and a filter."""
        result = self.run_with_output(
            "lslimit", "--tail", str(self.num_limit), self.track_head_range
        )
        assert result.count("\n") == self.num_limit

    def test_prefix(self):
        """Returns the expected number with the query prefix."""
        result = self.lib.items(self.num_limit_prefix)
        assert len(result) == self.num_limit

    def test_prefix_when_correctly_ordered(self):
        """Returns the expected number with the query prefix and filter when
        the prefix portion (correctly) appears last."""
        correct_order = f"{self.track_tail_range} {self.num_limit_prefix}"
        result = self.lib.items(correct_order)
        assert len(result) == self.num_limit

    def test_prefix_when_incorrectly_ordred(self):
        """Returns no results with the query prefix and filter when the prefix
        portion (incorrectly) appears first."""
        incorrect_order = f"{self.num_limit_prefix} {self.track_tail_range}"
        result = self.lib.items(incorrect_order)
        assert len(result) == 0

    def test_prefix_with_slow_sort(self):
        """
        HeadQuery combined with a slow sort returns the correct top-N items.

        Regression test for https://github.com/beetbox/beets/issues/5076:
        when a flexible (non-DB) field is used for sorting,
        the limit must be applied AFTER sorting, not before.
        """
        # Assign a flexible attribute so items get SlowFieldSort.
        # Use 0-indexed single-digit ratings to avoid lexicographic-vs-numeric
        # ordering issues (flexible attrs are stored as strings).
        for rating, item in enumerate(
            sorted(self.lib.items(), key=lambda i: i.track)
        ):
            item["rating"] = rating  # 0..num_test_items-1
            item.store()

        # Top num_limit items by rating descending must be the highest-rated ones.
        result = list(self.lib.items(f"rating- {self.num_limit_prefix}"))
        assert len(result) == self.num_limit

        # Flexible attrs come back as strings; single-digit values compare
        # identically as int and as string, so casting is safe here.
        ratings = [int(item["rating"]) for item in result]
        max_rating = self.num_test_items - 1
        expected = list(range(max_rating, max_rating - self.num_limit, -1))
        assert ratings == expected, f"Expected {expected}, got {ratings}"
