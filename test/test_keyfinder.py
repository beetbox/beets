# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Thomas Scholtes.
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

from __future__ import division, absolute_import, print_function

from mock import patch
import unittest
from test.helper import TestHelper

from beets.library import Item
from beets import util


@patch('beets.util.command_output')
class KeyFinderTest(unittest.TestCase, TestHelper):

    def setUp(self):
        self.setup_beets()
        self.load_plugins('keyfinder')

    def tearDown(self):
        self.teardown_beets()
        self.unload_plugins()

    def test_add_key(self, command_output):
        item = Item(path='/file')
        item.add(self.lib)

        command_output.return_value = 'dbm'
        self.run_command('keyfinder')

        item.load()
        self.assertEqual(item['initial_key'], 'C#m')
        command_output.assert_called_with(
            ['KeyFinder', '-f', util.syspath(item.path)])

    def test_add_key_on_import(self, command_output):
        command_output.return_value = 'dbm'
        importer = self.create_importer()
        importer.run()

        item = self.lib.items().get()
        self.assertEqual(item['initial_key'], 'C#m')

    def test_force_overwrite(self, command_output):
        self.config['keyfinder']['overwrite'] = True

        item = Item(path='/file', initial_key='F')
        item.add(self.lib)

        command_output.return_value = 'C#m'
        self.run_command('keyfinder')

        item.load()
        self.assertEqual(item['initial_key'], 'C#m')

    def test_do_not_overwrite(self, command_output):
        item = Item(path='/file', initial_key='F')
        item.add(self.lib)

        command_output.return_value = 'dbm'
        self.run_command('keyfinder')

        item.load()
        self.assertEqual(item['initial_key'], 'F')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
