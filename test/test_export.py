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
import re


class ExportPluginTest(unittest.TestCase, TestHelper):
    def setUp(self):
        self.setup_beets()
        self.load_plugins('export')

    def tearDown(self):
        self.unload_plugins()
        self.teardown_beets()

    def execute_command(self, format_type, artist):
        actual = self.run_with_output(
            'export',
            '-f', format_type,
            '-i', 'album,title',
            artist
        )
        return re.sub("\\s+", '', actual)

    def create_item(self):
        item, = self.add_item_fixtures()
        item.artist = 'xartist'
        item.title = 'xtitle'
        item.album = 'xalbum'
        item.write()
        item.store()
        return item

    def test_json_output(self):
        item1 = self.create_item()
        actual = self.execute_command(
            format_type='json',
            artist=item1.artist
        )
        expected = u'[{"album":"%s","title":"%s"}]'\
            % (item1.album, item1.title)
        self.assertIn(
            expected,
            actual
        )

    def test_csv_output(self):
        item1 = self.create_item()
        actual = self.execute_command(
            format_type='csv',
            artist=item1.artist
        )
        expected = u'album,title%s,%s'\
            % (item1.album, item1.title)
        self.assertIn(
            expected,
            actual
        )

    def test_xml_output(self):
        item1 = self.create_item()
        actual = self.execute_command(
            format_type='xml',
            artist=item1.artist
        )
        expected = u'<album>%s</album><title>%s</title>'\
            % (item1.album, item1.title)
        self.assertIn(
            expected,
            actual
        )


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
