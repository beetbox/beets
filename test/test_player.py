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

class FauxPathTest(unittest.TestCase):
        
    def test_single_element_preserved(self):
        seq = ['hello']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_multiple_elements_preserved(self):
        seq = ['hello', 'there', 'how', 'are', 'you']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_spaces_preserved(self):
        seq = ['hel lo', 'what', 'is up']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_empty_string_preserved_in_middle(self):
        seq = ['hello', '', 'sup']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_empty_strings_preserved_on_ends(self):
        seq = ['', 'whatever', '']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_empty_strings_only(self):
        seq = ['', '', '']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_slashes_preserved(self):
        seq = ['hel/lo', 'what', 'is', 'up']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_backslashes_preserved(self):
        seq = ['hel\\lo', 'what', 'is', 'up']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_unicode_preserved(self):
        seq = [u'hello', u'what \x99 is', u'up']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq)), seq)
    
    def test_slashes_not_encoded_as_slashes(self):
        no_slashes = bpd.seq_to_path(['goodday', 'sir'])
        with_slashes = bpd.seq_to_path(['good/day', 'sir'])
        self.assertEqual(no_slashes.count('/'), with_slashes.count('/'))
    
    def test_empty_seq_preserved_with_placeholder(self):
        seq = []
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq, 'PH'), 'PH'),
                         seq)

    def test_empty_strings_preserved_with_placeholder(self):
        seq = ['hello', '', 'sup']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq, 'PH'), 'PH'),
                         seq)
    
    def test_empty_strings_only_preserved_with_placeholder(self):
        seq = ['', '', '']
        self.assertEqual(bpd.path_to_list(bpd.seq_to_path(seq, 'PH'), 'PH'),
                         seq)
    
    def test_placeholder_does_replace(self):
        seq = ['hello', '', 'sup']
        self.assertFalse('//' in bpd.seq_to_path(seq, 'PH'))
    
    # Note that the path encodes doesn't currently try to distinguish
    # between the placeholder and strings identical to the placeholder.
    # This might be a nice feature but is not currently essential.

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

