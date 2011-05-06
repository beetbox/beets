# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

"""Tests for BPD and music playing.
"""

import unittest

import _common
from beetsplug import bpd

class CommandParseTest(unittest.TestCase):
    def test_no_args(self):
        s = ur'command'
        c = bpd.Command(s)
        self.assertEqual(c.name, u'command')
        self.assertEqual(c.args, [])

    def test_one_unquoted_arg(self):
        s = ur'command hello'
        c = bpd.Command(s)
        self.assertEqual(c.name, u'command')
        self.assertEqual(c.args, [u'hello'])

    def test_two_unquoted_args(self):
        s = ur'command hello there'
        c = bpd.Command(s)
        self.assertEqual(c.name, u'command')
        self.assertEqual(c.args, [u'hello', u'there'])

    def test_one_quoted_arg(self):
        s = ur'command "hello there"'
        c = bpd.Command(s)
        self.assertEqual(c.name, u'command')
        self.assertEqual(c.args, [u'hello there'])

    def test_heterogenous_args(self):
        s = ur'command "hello there" sir'
        c = bpd.Command(s)
        self.assertEqual(c.name, u'command')
        self.assertEqual(c.args, [u'hello there', u'sir'])

    def test_quote_in_arg(self):
        s = ur'command "hello \" there"'
        c = bpd.Command(s)
        self.assertEqual(c.args, [u'hello " there'])

    def test_backslash_in_arg(self):
        s = ur'command "hello \\ there"'
        c = bpd.Command(s)
        self.assertEqual(c.args, [u'hello \ there'])
    
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

