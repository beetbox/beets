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
from test import helper
from test.helper import TestHelper
#from beetsplug.export import ExportPlugin, ExportFormat, JSONFormat, CSVFormat, XMLFormat
#from collections import namedtuple


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

        out = self.run_with_output('export', '-f json -i "track,album" tartist')
        self.assertIn('"track": "' + item1.track + '"', out)
        self.assertIn('"album": "' + item1.album + '"', out)
    
    def test_csv_output(self):
        item1, item2 = self.add_item_fixtures(count=2)
        item1.album = 'talbum'
        item1.artist = "tartist"
        item1.track = "ttrack"
        item1.write()
        item1.store()

        out = self.run_with_output('export', '-f json -i "track,album" tartist')
        self.assertIn(item1.track + ',' + item1.album,  out)
    
    def test_xml_output(self):
        item1, item2 = self.add_item_fixtures(count=2)
        item1.album = 'talbum'
        item1.artist = "tartist"
        item1.track = "ttrack"
        item1.write()
        item1.store()

        out = self.run_with_output('export', '-f json -i "track,album" tartist')
        self.assertIn("<title>" + item1.track + "</title>", out)
        self.assertIn("<album>" + item1.album + "</album>", out)

    """
    def setUp(self):
        Opts = namedtuple('Opts', 'output append included_keys library format')
        self.args = None
        self._export = ExportPlugin()
        included_keys = ['title,artist,album']
        self.opts = Opts(None, False, included_keys, True, "json")
        self.export_format_classes = {"json": ExportFormat, "csv": CSVFormat, "xml": XMLFormat}

    def test_run(self, _format="json"):
        self.opts.format = _format
        self._export.run(lib=self.lib, opts=self.opts, args=self.args)
        # 1.) Test that the ExportFormat Factory class method invoked the correct class 
        self.assertEqual(type(self._export.export_format), self.export_format_classes[_format])
        # 2.) Test that the cmd parser options specified were processed in correctly
        self.assertEqual(self._export.export_format.path, self.opts.output)
        mode = 'a' if self.opts.append else 'w'
        self.assertEqual(self._export.export_format.mode, mode)
    """



def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')