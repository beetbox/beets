# This file is part of beets.
# Copyright 2015
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

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)


from mock import Mock
from test._common import unittest
from test.helper import TestHelper

from beets.library import Item
from beetsplug.mpdstats import MPDStats


class MPDStatsTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('mpdstats')

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def test_update_rating(self):
        item = Item(title='title', path='', id=1)
        item.add(self.lib)

        log = Mock()
        mpdstats = MPDStats(self.lib, log)

        self.assertFalse(mpdstats.update_rating(item, True))
        self.assertFalse(mpdstats.update_rating(None, True))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
