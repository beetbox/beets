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

from mock import patch
import unittest
from test.helper import TestHelper

from beets.library import Item
from beetsplug import parentwork
from beets import util


@patch('beets.util.command_output')
class ParentWorkTest(unittest.TestCase, TestHelper):
    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self.load_plugins('parentwork')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

#    def test_normal_case(self, command_output):
#        item = Item(path='/file',
#                    work_id=u'e27bda6e-531e-36d3-9cd7-b8ebc18e8c53')
#        item.add(self.lib)
#
#        command_output.return_value = u'32c8943f-1b27-3a23-8660-4567f4847c94'
#        self.run_command('parentwork')
#
#        item.load()
#        self.assertEqual(item['parent_work_id'],
#                         u'32c8943f-1b27-3a23-8660-4567f4847c94')
#        command_output.assert_called_with(
#            ['ParentWork', '-f', util.syspath(item.path)])

#
    def test_force(self, command_output):
        self.config['parentwork']['force'] = True
        item = Item(path='/file',
                    work_id=u'e27bda6e-531e-36d3-9cd7-b8ebc18e8c53',
                    parent_work_id=u'XXX')
        item.add(self.lib)

        command_output.return_value = u'32c8943f-1b27-3a23-8660-4567f4847c94'
        self.run_command('parentwork')
#
        item.load()
        self.assertEqual(item['parent_work_id'],
                         u'32c8943f-1b27-3a23-8660-4567f4847c94')
#
#    def test_no_force(self, command_output):
#        self.config['parentwork']['force'] = True
#        item = Item(path='/file', work_id=u'e27bda6e-531e-36d3-9cd7-\
#                    b8ebc18e8c53', parent_work_id=u'XXX')
#        item.add(self.lib)
#
#        command_output.return_value = u'32c8943f-1b27-3a23-8660-4567f4847c94'
#        self.run_command('parentwork')
#
#        item.load()
#        self.assertEqual(item['parent_work_id'], u'XXX')
#
#    # test different cases, still with Matthew Passion Ouverture or Mozart
#    # requiem
#
#    def test_father_work(self, command_output):
#        work_id = u'2e4a3668-458d-3b2a-8be2-0b08e0d8243a'
#        self.assertEqual(u'f04b42df-7251-4d86-a5ee-67cfa49580d1',
#                         parentwork.work_father(work_id)[0])
#        self.assertEqual(u'45afb3b2-18ac-4187-bc72-beb1b1c194ba',
#                         parentwork.work_parent(work_id)[0])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
