# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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

from _common import unittest
from beets import util


class UtilTest(unittest.TestCase):
    def test_sanitize_choices(self):
        self.assertEqual(util.sanitize_choices(['A', 'Z'], ('A', 'B')),
                         ['A'])
        self.assertEqual(util.sanitize_choices(['A', 'A'], ('A')), ['A'])
        self.assertEqual(util.sanitize_choices(['D', '*', 'A'],
                         ('A', 'B', 'C', 'D')), ['D', 'B', 'C', 'A'])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
