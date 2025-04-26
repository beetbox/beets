# This file is part of beets.
# Copyright 2025, valrus.
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

"""Test beets library add emits only one database_change event."""

import os

import beets
import beets.logging as blog
from beets.test import _common
from beets.test.helper import BeetsTestCase, capture_log


class DatabaseChangeTestBase(BeetsTestCase):
    def test_item_added_one_database_change(self):
        self.item = _common.item()
        self.item.path = beets.util.normpath(
            os.path.join(
                self.temp_dir,
                b"a",
                b"b.mp3",
            )
        )
        self.item.album = "a"
        self.item.title = "b"

        blog.getLogger("beets").set_global_level(blog.DEBUG)
        with capture_log() as logs:
            self.lib.add(self.item)

        assert logs.count("Sending event: database_change") == 1
