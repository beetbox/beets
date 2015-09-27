# -*- coding: utf8 -*-
# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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

"""Test module for file ui/__init__.py
"""
import textwrap

from test import _common
from test._common import unittest

from beets import ui


class InitTest(_common.LibTestCase):
    def setUp(self):
        super(InitTest, self).setUp()

    def test_human_bytes(self):
        tests = [
            (0, '0.0 B'),
            (30, '30.0 B'),
            (pow(2, 10), '1.0 KB'),
            (pow(2, 20), '1.0 MB'),
            (pow(2, 30), '1.0 GB'),
            (pow(2, 40), '1.0 TB'),
            (pow(2, 50), '1.0 PB'),
            (pow(2, 60), '1.0 EB'),
            (pow(2, 70), '1.0 ZB'),
            (pow(2, 80), '1.0 YB'),
            (pow(2, 90), '1.0 HB'),
            (pow(2, 100), 'big'),
        ]
        for i, h in tests:
            self.assertEqual(h, ui.human_bytes(i))

    def test_human_seconds(self):
        tests = [
            (0, '0.0 seconds'),
            (30, '30.0 seconds'),
            (60, '1.0 minutes'),
            (90, '1.5 minutes'),
            (125, '2.1 minutes'),
            (3600, '1.0 hours'),
            (86400, '1.0 days'),
            (604800, '1.0 weeks'),
            (31449600, '1.0 years'),
            (314496000, '1.0 decades'),
        ]
        for i, h in tests:
            self.assertEqual(h, ui.human_seconds(i))


class SubcommandTest(_common.LibTestCase):
    def setUp(self):
        super(SubcommandTest, self).setUp()

        self.io.install()

    def tearDown(self):
        self.io.restore()

    def _add_subcommand(self, parser=None):
        self.test_cmd = ui.Subcommand(
            'test', parser,
            help='This is the help text for test')

    def test_print_help(self):
        parser = ui.CommonOptionsParser(usage="Test")
        parser.add_all_common_options()
        self._add_subcommand(parser)
        self.test_cmd.print_help()
        desired_output = textwrap.dedent(
            """            Usage: Test

            Options:
              -h, --help            show this help message and exit
              -a, --album           match albums instead of tracks
              -p PATH, --path=PATH  print paths for matched items or albums
              -f FORMAT, --format=FORMAT
                                    print with custom format
            """)
        self.assertEqual(self.io.stdout.get(), desired_output)

    def test_get_root_parser(self):
        self._add_subcommand()
        root_parser = self.test_cmd.root_parser
        # Following is just a workaround for FLAKE8 rule F841
        root_parser = root_parser


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
