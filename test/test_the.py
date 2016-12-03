# -*- coding: utf-8 -*-

"""Tests for the 'the' plugin"""

from __future__ import division, absolute_import, print_function

import unittest
from test import _common
from beets import config
from beetsplug.the import ThePlugin, PATTERN_A, PATTERN_THE, FORMAT


class ThePluginTest(_common.TestCase):

    def test_unthe_with_default_patterns(self):
        self.assertEqual(ThePlugin().unthe(u'', PATTERN_THE), '')
        self.assertEqual(ThePlugin().unthe(u'The Something', PATTERN_THE),
                         u'Something, The')
        self.assertEqual(ThePlugin().unthe(u'The The', PATTERN_THE),
                         u'The, The')
        self.assertEqual(ThePlugin().unthe(u'The    The', PATTERN_THE),
                         u'The, The')
        self.assertEqual(ThePlugin().unthe(u'The   The   X', PATTERN_THE),
                         u'The   X, The')
        self.assertEqual(ThePlugin().unthe(u'the The', PATTERN_THE),
                         u'The, the')
        self.assertEqual(ThePlugin().unthe(u'Protected The', PATTERN_THE),
                         u'Protected The')
        self.assertEqual(ThePlugin().unthe(u'A Boy', PATTERN_A),
                         u'Boy, A')
        self.assertEqual(ThePlugin().unthe(u'a girl', PATTERN_A),
                         u'girl, a')
        self.assertEqual(ThePlugin().unthe(u'An Apple', PATTERN_A),
                         u'Apple, An')
        self.assertEqual(ThePlugin().unthe(u'An A Thing', PATTERN_A),
                         u'A Thing, An')
        self.assertEqual(ThePlugin().unthe(u'the An Arse', PATTERN_A),
                         u'the An Arse')

    def test_unthe_with_strip(self):
        config['the']['strip'] = True
        self.assertEqual(ThePlugin().unthe(u'The Something', PATTERN_THE),
                         u'Something')
        self.assertEqual(ThePlugin().unthe(u'An A', PATTERN_A), u'A')

    def test_template_function_with_defaults(self):
        ThePlugin().patterns = [PATTERN_THE, PATTERN_A]
        self.assertEqual(ThePlugin().the_template_func(u'The The'),
                         u'The, The')
        self.assertEqual(ThePlugin().the_template_func(u'An A'), u'A, An')

    def test_custom_pattern(self):
        config['the']['patterns'] = [u'^test\s']
        config['the']['format'] = FORMAT
        self.assertEqual(ThePlugin().the_template_func(u'test passed'),
                         u'passed, test')

    def test_custom_format(self):
        config['the']['patterns'] = [PATTERN_THE, PATTERN_A]
        config['the']['format'] = u'{1} ({0})'
        self.assertEqual(ThePlugin().the_template_func(u'The A'), u'The (A)')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
