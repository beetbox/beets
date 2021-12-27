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

"""Tests for the 'limit' plugin."""

import unittest

from test.helper import TestHelper


class LsLimitPluginTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.load_plugins("limit")
        self.num_test_items = 10
        assert self.num_test_items % 2 == 0
        self.num_limit = self.num_test_items // 2
        self.num_limit_prefix = "'<" + str(self.num_limit) + "'"
        self.track_head_range = "track:.." + str(self.num_limit)
        self.track_tail_range = "track:" + str(self.num_limit + 1) + ".."
        for item_no, item in \
                enumerate(self.add_item_fixtures(count=self.num_test_items)):
            item.track = item_no + 1
            item.store()

    def tearDown(self):
        self.teardown_beets()

    def test_no_limit(self):
        result = self.run_with_output("lslimit")
        self.assertEqual(result.count("\n"), self.num_test_items)

    def test_lslimit_head(self):
        result = self.run_with_output("lslimit", "--head", str(self.num_limit))
        self.assertEqual(result.count("\n"), self.num_limit)

    def test_lslimit_tail(self):
        result = self.run_with_output("lslimit", "--tail", str(self.num_limit))
        self.assertEqual(result.count("\n"), self.num_limit)

    def test_lslimit_head_invariant(self):
        result = self.run_with_output(
            "lslimit", "--head", str(self.num_limit), self.track_tail_range)
        self.assertEqual(result.count("\n"), self.num_limit)

    def test_lslimit_tail_invariant(self):
        result = self.run_with_output(
            "lslimit", "--tail", str(self.num_limit), self.track_head_range)
        self.assertEqual(result.count("\n"), self.num_limit)

    def test_prefix(self):
        result = self.run_with_output("ls", self.num_limit_prefix)
        self.assertEqual(result.count("\n"), self.num_limit)

    def test_prefix_when_correctly_ordered(self):
        result = self.run_with_output(
            "ls", self.track_tail_range, self.num_limit_prefix)
        self.assertEqual(result.count("\n"), self.num_limit)

    def test_prefix_when_incorrectly_ordred(self):
        result = self.run_with_output(
            "ls", self.num_limit_prefix, self.track_tail_range)
        self.assertEqual(result.count("\n"), 0)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
