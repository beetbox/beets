# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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

"""Tests for template engine.
"""
import unittest

import _common
from beets.util import functemplate

def _normparse(text):
    """Parse a template and then normalize the result, collapsing
    multiple adjacent text blocks and removing empty text blocks.
    Generates a sequence of parts.
    """
    textbuf = []
    for part in functemplate._parse(text):
        if isinstance(part, basestring):
            textbuf.append(part)
        else:
            if textbuf:
                text = u''.join(textbuf)
                if text:
                    yield text
                    textbuf = []
            yield part
    if textbuf:
        text = u''.join(textbuf)
        if text:
            yield text

class ParseTest(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(list(_normparse(u'')), [])

    def _assert_symbol(self, obj, ident):
        """Assert that an object is a Symbol with the given identifier.
        """
        self.assertTrue(isinstance(obj, functemplate.Symbol),
                        u"not a Symbol: %s" % repr(obj))
        self.assertEqual(obj.ident, ident,
                         u"wrong identifier: %s vs. %s" %
                         (repr(obj.ident), repr(ident)))

    def test_plain_text(self):
        self.assertEqual(list(_normparse(u'hello world')), [u'hello world'])

    def test_escaped_character_only(self):
        self.assertEqual(list(_normparse(u'$$')), [u'$'])

    def test_escaped_character_in_text(self):
        self.assertEqual(list(_normparse(u'a $$ b')), [u'a $ b'])

    def test_escaped_character_at_start(self):
        self.assertEqual(list(_normparse(u'$$ hello')), [u'$ hello'])

    def test_escaped_character_at_end(self):
        self.assertEqual(list(_normparse(u'hello $$')), [u'hello $'])

    def test_escaped_function_delim(self):
        self.assertEqual(list(_normparse(u'a %% b')), [u'a % b'])

    def test_escaped_sep(self):
        self.assertEqual(list(_normparse(u'a ,, b')), [u'a , b'])

    def test_escaped_open_brace(self):
        self.assertEqual(list(_normparse(u'a {{ b')), [u'a { b'])

    def test_escaped_close_brace(self):
        self.assertEqual(list(_normparse(u'a } b')), [u'a } b'])

    def test_bare_value_delim_kept_intact(self):
        self.assertEqual(list(_normparse(u'a $ b')), [u'a $ b'])

    def test_bare_function_delim_kept_intact(self):
        self.assertEqual(list(_normparse(u'a % b')), [u'a % b'])

    def test_symbol_alone(self):
        parts = list(_normparse(u'$foo'))
        self.assertEqual(len(parts), 1)
        self._assert_symbol(parts[0], u"foo")

    def test_symbol_in_text(self):
        parts = list(_normparse(u'hello $foo world'))
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], u'hello ')
        self._assert_symbol(parts[1], u"foo")
        self.assertEqual(parts[2], u' world')

    def test_symbol_with_braces(self):
        parts = list(_normparse(u'hello${foo}world'))
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], u'hello')
        self._assert_symbol(parts[1], u"foo")
        self.assertEqual(parts[2], u'world')

    def test_unclosed_braces_symbol(self):
        self.assertEqual(list(_normparse(u'a ${ b')), [u'a ${ b'])
    
    def test_empty_braces_symbol(self):
        self.assertEqual(list(_normparse(u'a ${} b')), [u'a ${} b'])
    
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

