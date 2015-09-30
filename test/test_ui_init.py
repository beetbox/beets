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
            (pow(2, 10), '1.0 KiB'),
            (pow(2, 20), '1.0 MiB'),
            (pow(2, 30), '1.0 GiB'),
            (pow(2, 40), '1.0 TiB'),
            (pow(2, 50), '1.0 PiB'),
            (pow(2, 60), '1.0 EiB'),
            (pow(2, 70), '1.0 ZiB'),
            (pow(2, 80), '1.0 YiB'),
            (pow(2, 90), '1.0 HiB'),
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


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
