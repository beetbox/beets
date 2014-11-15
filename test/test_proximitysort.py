# This file is part of beets.
# Copyright 2014, Sergei Zimakov.
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

"""Tests for proximity sort.
"""

import _common
from _common import unittest
from beets import plugins
from beets.dbcore import types
from beets.library import Item, Library
from beetsplug import proximitysort


# A test case class providing a library with some dummy data.
class ProximitySortTestCase(_common.TestCase):
    def setUp(self):
        super(ProximitySortTestCase, self).setUp()
        self.lib = Library(':memory:')
        plugins._classes.add(proximitysort.ProximitySortPlugin)
        Item._types['flex'] = types.FLOAT

        items = [_common.item() for _ in range(5)]

        for i, item in enumerate(items):
            item.bpm = 100 + i * 10
            item.flex = 1.1 + i * .2

        items[4].bpm = 0    # [100, 110, 120, 130, 140, 0]
        items[4].flex = 0   # [1.1, 1.3, 1.5, 1.7, 0]

        for item in items:
            self.lib.add(item)

    def tearDown(self):
        plugins._classes.remove(proximitysort.ProximitySortPlugin)
        super(ProximitySortTestCase, self).tearDown()


class FixedFieldTestCase(ProximitySortTestCase):
    def test_in_the_middle(self):
        items = self.lib.items('bpm+^111')
        bpms = [o.bpm for o in items]
        self.assertEqual(bpms, [110, 120, 100, 130, 0])

    def test_on_the_right(self):
        items = self.lib.items('bpm+^200')
        bpms = [o.bpm for o in items]
        self.assertEqual(bpms, [130, 120, 110, 100, 0])

    def test_on_the_left(self):
        items = self.lib.items('bpm+^90')
        bpms = [o.bpm for o in items]
        self.assertEqual(bpms, [100, 110, 120, 130, 0])

    def test_near_0(self):
        items = self.lib.items('bpm+^1')
        bpms = [o.bpm for o in items]
        self.assertEqual(bpms, [0, 100, 110, 120, 130])


class FlexFieldTestCase(ProximitySortTestCase):
    def test_in_the_middle(self):
        items = self.lib.items('flex+^1.49')
        flexes = [o.flex for o in items]
        self.assertEqual(flexes, [1.5, 1.3, 1.7, 1.1, 0])

    def test_on_the_right(self):
        items = self.lib.items('flex+^1.8')
        flexes = [o.flex for o in items]
        self.assertEqual(flexes, [1.7, 1.5, 1.3, 1.1, 0])

    def test_on_the_left(self):
        items = self.lib.items('flex+^1.0')
        flexes = [o.flex for o in items]
        self.assertEqual(flexes, [1.1, 1.3, 1.5, 1.7, 0])

    def test_near_0(self):
        items = self.lib.items('flex+^0.1')
        flexes = [o.flex for o in items]
        self.assertEqual(flexes, [0, 1.1, 1.3, 1.5, 1.7])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
