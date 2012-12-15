"""Tests for the 'the' plugin"""

from _common import unittest
import _common
from beets import config
from beetsplug.the import ThePlugin, PATTERN_A, PATTERN_THE, FORMAT


class ThePluginTest(_common.TestCase):

    def test_unthe_with_default_patterns(self):
        self.assertEqual(ThePlugin().unthe('', PATTERN_THE), '')
        self.assertEqual(ThePlugin().unthe('The Something', PATTERN_THE), 
                         'Something, The')
        self.assertEqual(ThePlugin().unthe('The The', PATTERN_THE), 
                         'The, The')
        self.assertEqual(ThePlugin().unthe('The    The', PATTERN_THE), 
                         'The, The')
        self.assertEqual(ThePlugin().unthe('The   The   X', PATTERN_THE), 
                         'The   X, The')
        self.assertEqual(ThePlugin().unthe('the The', PATTERN_THE), 
                         'The, the')
        self.assertEqual(ThePlugin().unthe('Protected The', PATTERN_THE), 
                         'Protected The')
        self.assertEqual(ThePlugin().unthe('A Boy', PATTERN_A), 
                         'Boy, A')
        self.assertEqual(ThePlugin().unthe('a girl', PATTERN_A), 
                         'girl, a')
        self.assertEqual(ThePlugin().unthe('An Apple', PATTERN_A), 
                         'Apple, An')
        self.assertEqual(ThePlugin().unthe('An A Thing', PATTERN_A), 
                         'A Thing, An')
        self.assertEqual(ThePlugin().unthe('the An Arse', PATTERN_A), 
                         'the An Arse')

    def test_unthe_with_strip(self):
        config['the']['strip'] = True
        self.assertEqual(ThePlugin().unthe('The Something', PATTERN_THE), 
                        'Something') 
        self.assertEqual(ThePlugin().unthe('An A', PATTERN_A), 'A') 

    def test_template_function_with_defaults(self):
        ThePlugin().patterns = [PATTERN_THE, PATTERN_A]
        ThePlugin().format = FORMAT
        self.assertEqual(ThePlugin().the_template_func('The The'), 'The, The')
        self.assertEqual(ThePlugin().the_template_func('An A'), 'A, An')

    def test_custom_pattern(self):
        config['the']['patterns'] = [u'^test\s']
        config['the']['format'] = FORMAT
        self.assertEqual(ThePlugin().the_template_func('test passed'), 
                         'passed, test')

    def test_custom_format(self):
        config['the']['patterns'] = [PATTERN_THE, PATTERN_A]
        config['the']['format'] = u'{1} ({0})'
        self.assertEqual(ThePlugin().the_template_func('The A'), 'The (A)')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
