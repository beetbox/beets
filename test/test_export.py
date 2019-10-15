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
        self.test_values = {'title': 'xtitle', 'album': 'xalbum'}

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
        item.title = self.test_values['title']
        item.album = self.test_values['album']
        item.write()
        item.store()
        return item

    def test_json_output(self):
        item1 = self.create_item()
        actual = self.execute_command(
            format_type='json',
            artist=item1.artist
        )
        for key, val in self.test_values.items():
            self.check_assertin(
                actual=actual,
                str_format='"{0}":"{1}"',
                key=key,
                val=val
            )

    def test_csv_output(self):
        item1 = self.create_item()
        actual = self.execute_command(
            format_type='csv',
            artist=item1.artist
        )
        for key, val in self.test_values.items():
            self.check_assertin(
                actual=actual,
                str_format='{0}{1}',
                key='',
                val=val
            )

    def test_xml_output(self):
        item1 = self.create_item()
        actual = self.execute_command(
            format_type='xml',
            artist=item1.artist
        )
        for key, val in self.test_values.items():
            self.check_assertin(
                actual=actual,
                str_format='<{0}>{1}</{0}>',
                key=key,
                val=val
            )

    def check_assertin(self, actual, str_format, key, val):
        expected = str_format.format(key, val)
        self.assertIn(
            expected,
            actual
        )


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
