"""Tests for the 'the' plugin"""

from _common import unittest
from beetsplug import the


class ThePluginTest(unittest.TestCase):
    
    
    def test_unthe_with_default_patterns(self):
        self.assertEqual(the.unthe('', the.PATTERN_THE), '')
        self.assertEqual(the.unthe('The Something', the.PATTERN_THE), 
                         'Something, The')
        self.assertEqual(the.unthe('The The', the.PATTERN_THE), 'The, The')
        self.assertEqual(the.unthe('The    The', the.PATTERN_THE), 'The, The')
        self.assertEqual(the.unthe('The   The   X', the.PATTERN_THE), 
                         u'The   X, The')
        self.assertEqual(the.unthe('the The', the.PATTERN_THE), 'The, the')
        self.assertEqual(the.unthe('Protected The', the.PATTERN_THE), 
                         'Protected The')
        self.assertEqual(the.unthe('A Boy', the.PATTERN_A), 'Boy, A')
        self.assertEqual(the.unthe('a girl', the.PATTERN_A), 'girl, a')
        self.assertEqual(the.unthe('An Apple', the.PATTERN_A), 'Apple, An')
        self.assertEqual(the.unthe('An A Thing', the.PATTERN_A), 'A Thing, An')
        self.assertEqual(the.unthe('the An Arse', the.PATTERN_A), 
                         'the An Arse')
        self.assertEqual(the.unthe('The Something', the.PATTERN_THE, 
                                   strip=True), 'Something') 
        self.assertEqual(the.unthe('An A', the.PATTERN_A, strip=True), 'A') 
    
    def test_template_function_with_defaults(self):
        the.the_options['patterns'] = [the.PATTERN_THE, the.PATTERN_A]
        the.the_options['format'] = the.FORMAT
        self.assertEqual(the.func_the('The The'), 'The, The')
        self.assertEqual(the.func_the('An A'), 'A, An')
    
    def test_custom_pattern(self):
        the.the_options['patterns'] = [ u'^test\s']
        the.the_options['format'] = the.FORMAT
        self.assertEqual(the.func_the('test passed'), 'passed, test')
    
    def test_custom_format(self):
        the.the_options['patterns'] = [the.PATTERN_THE, the.PATTERN_A]
        the.the_options['format'] = '{1} ({0})'
        self.assertEqual(the.func_the('The A'), 'The (A)')
        
           
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
