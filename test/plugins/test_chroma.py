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


from unittest.mock import patch

from beets.library import Item
from beets.test.helper import ImportTestCase, IOMixin, PluginMixin

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
