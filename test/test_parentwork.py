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


@patch('beets.util.command_output')
class ParentWorkTest(unittest.TestCase, TestHelper):
    def setUp(self):
        """Set up configuration"""
        self.setup_beets()
        self.load_plugins('parentwork')

        self.config['parentwork'] = {
            'auto': True,
            'force': False,
        }

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_normal_case(self, command_output):
        item = Item(path='/file',
                    work_id=u'e27bda6e-531e-36d3-9cd7-b8ebc18e8c53')
        item.add(self.lib)
        command_output.return_value = u'32c8943f-1b27-3a23-8660-4567f4847c94'
        self.run_command('parentwork')
        item.load()
        self.assertEqual(item['parent_work_id'],
                         u'32c8943f-1b27-3a23-8660-4567f4847c94')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
