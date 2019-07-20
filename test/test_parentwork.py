# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017, Dorian Soergel
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

"""Tests for the 'parentwork' plugin."""

from __future__ import division, absolute_import, print_function

import unittest
from test.helper import TestHelper

from beets.library import Item
from beetsplug import parentwork


class ParentWorkTest(unittest.TestCase, TestHelper):
    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self.load_plugins('parentwork')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_normal_case(self):
        item = Item(path='/file',
                    mb_workid=u'e27bda6e-531e-36d3-9cd7-b8ebc18e8c53')
        item.add(self.lib)

        self.run_command('parentwork')

        item.load()
        self.assertEqual(item['mb_parentworkid'],
                         u'32c8943f-1b27-3a23-8660-4567f4847c94')

    def test_force(self):
        self.config['parentwork']['force'] = True
        item = Item(path='/file',
                    mb_workid=u'e27bda6e-531e-36d3-9cd7-b8ebc18e8c53',
                    mb_parentworkid=u'XXX')
        item.add(self.lib)

        self.run_command('parentwork')

        item.load()
        self.assertEqual(item['mb_parentworkid'],
                         u'32c8943f-1b27-3a23-8660-4567f4847c94')

    def test_no_force(self):
        self.config['parentwork']['force'] = True
        item = Item(path='/file', mb_workid=u'e27bda6e-531e-36d3-9cd7-\
                    b8ebc18e8c53', mb_parentworkid=u'XXX')
        item.add(self.lib)

        self.run_command('parentwork')

        item.load()
        self.assertEqual(item['mb_parentworkid'], u'XXX')

    # test different cases, still with Matthew Passion Ouverture or Mozart
    # requiem

    def test_direct_parent_work(self):
        mb_workid = u'2e4a3668-458d-3b2a-8be2-0b08e0d8243a'
        self.assertEqual(u'f04b42df-7251-4d86-a5ee-67cfa49580d1',
                         parentwork.direct_parent_id(mb_workid)[0])
        self.assertEqual(u'45afb3b2-18ac-4187-bc72-beb1b1c194ba',
                         parentwork.work_parent_id(mb_workid)[0])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
