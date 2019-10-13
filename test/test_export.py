# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2019, Carl Suster
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

"""Test the beets.export utilities associated with the export plugin.
"""

from __future__ import division, absolute_import, print_function

import unittest
from test.helper import TestHelper


class ExportPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('export')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def test_json_output(self):
        item1, item2 = self.add_item_fixtures(count=2)
        item1.album = 'talbum'
        item1.artist = "tartist"
        item1.track = "ttrack"
        item1.write()
        item1.store()
        options = '-f json -i "track,album" ' + item1.artist
        out = self.run_with_output('export', options)
        self.assertIn('"track": "' + item1.track + '"', out)
        self.assertIn('"album": "' + item1.album + '"', out)

    def test_csv_output(self):
        item1, item2 = self.add_item_fixtures(count=2)
        item1.album = 'talbum'
        item1.artist = "tartist"
        item1.track = "ttrack"
        item1.write()
        item1.store()
        options = '-f csv -i "track,album" ' + item1.artist
        out = self.run_with_output('export', options)
        self.assertIn(item1.track + ',' + item1.album,  out)

    def test_xml_output(self):
        item1, item2 = self.add_item_fixtures(count=2)
        item1.album = 'talbum'
        item1.artist = "tartist"
        item1.track = "ttrack"
        item1.write()
        item1.store()
        options = '-f xml -i "track,album" ' + item1.artist
        out = self.run_with_output('export', options)
        self.assertIn("<title>" + item1.track + "</title>", out)
        self.assertIn("<album>" + item1.album + "</album>", out)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
