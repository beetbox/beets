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

    def execute_command(self, format_type, artist):
        options = ' -f %s -i "track,album" s'.format(format_type, artist)
        actual = self.run_with_output('export', options)
        return actual.replace(" ", "")
    
    def create_item(self, album='talbum', artist='tartist', track='ttrack'):
        item1, = self.add_item_fixtures()
        item1.album = album
        item1.artist = artist
        item1.track = track
        item1.write()
        item1.store()
        return item1

    def test_json_output(self):
        item1 = self.create_item()
        actual = self.execute_command(format_type='json',artist=item1.artist)
        expected = '[{"track":%s,"album":%s}]'.format(item1.track,item1.album)
        self.assertIn(first=expected,second=actual,msg="export in JSON format failed")

    def test_csv_output(self):
        item1 = self.create_item()
        actual = self.execute_command(format_type='json',artist=item1.artist)
        expected = 'track,album\n%s,%s'.format(item1.track,item1.album)
        self.assertIn(first=expected,second=actual,msg="export in CSV format failed")

    def test_xml_output(self):
        item1 = self.create_item()
        actual = self.execute_command(format_type='json',artist=item1.artist)
        expected = '<title>%s</title><album>%s</album>'.format(item1.track,item1.album)
        self.assertIn(first=expected,second=actual,msg="export in XML format failed")


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
