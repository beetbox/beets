#!/usr/bin/env python
import unittest, sys, os
sys.path.append('..')
import beets.library

parse_query = beets.library.AndQuery._parse_query

class QueryParseTest(unittest.TestCase):
    def test_one_basic_term(self):
        q = 'test'
        r = [(None, 'test')]
        self.assertEqual(parse_query(q), r)
    
    def test_three_basic_terms(self):
        q = 'test one two'
        r = [(None, 'test'), (None, 'one'), (None, 'two')]
        self.assertEqual(parse_query(q), r)
    
    def test_one_keyed_term(self):
        q = 'test:val'
        r = [('test', 'val')]
        self.assertEqual(parse_query(q), r)
    
    def test_one_keyed_one_basic(self):
        q = 'test:val one'
        r = [('test', 'val'), (None, 'one')]
        self.assertEqual(parse_query(q), r)
    
    def test_colon_at_end(self):
        q = 'test:'
        r = [(None, 'test:')]
        self.assertEqual(parse_query(q), r)
    
    def test_colon_at_start(self):
        q = ':test'
        r = [(None, ':test')]
        self.assertEqual(parse_query(q), r)
    
    def test_escaped_colon(self):
        q = r'test\:val'
        r = [((None), 'test:val')]
        self.assertEqual(parse_query(q), r)

class GetTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library('rsrc' + os.sep + 'get.blb')
    
    def assert_matched(self, result_iterator, title):
        self.assertEqual(result_iterator.next().title, title)
    def assert_done(self, result_iterator):
        self.assertRaises(StopIteration, result_iterator.next)
    def assert_matched_all(self, result_iterator):
        self.assert_matched(result_iterator, 'Littlest Things')
        self.assert_matched(result_iterator, 'Lovers Who Uncover')
        self.assert_matched(result_iterator, 'Boracay')
        self.assert_matched(result_iterator, 'Take Pills')
        self.assert_done(result_iterator)
    
    def test_get_empty(self):
        q = ''
        results = self.lib.get(q)
        self.assert_matched_all(results)
    
    def test_get_none(self):
        q = None
        results = self.lib.get(q)
        self.assert_matched_all(results)
    
    def test_get_one_keyed_term(self):
        q = 'artist:Lil'
        results = self.lib.get(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_done(results)
    
    def test_get_one_unkeyed_term(self):
        q = 'Terry'
        results = self.lib.get(q)
        self.assert_matched(results, 'Boracay')
        self.assert_done(results)
    
    def test_get_no_matches(self):
        q = 'popebear'
        results = self.lib.get(q)
        self.assert_done(results)
    
    def test_invalid_key(self):
        q = 'pope:bear'
        results = self.lib.get(q)
        self.assert_matched_all(results)
    
    def test_term_case_insensitive(self):
        q = 'UNCoVER'
        results = self.lib.get(q)
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_done(results)
    
    def test_term_case_insensitive_with_key(self):
        q = 'album:stiLL'
        results = self.lib.get(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_done(results)
    
    def test_key_case_insensitive(self):
        q = 'ArTiST:Allen'
        results = self.lib.get(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_done(results)
    
    def test_unkeyed_term_matches_multiple_columns(self):
        q = 'little'
        results = self.lib.get(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_matched(results, 'Boracay')
        self.assert_done(results)
    
    def test_keyed_term_matches_only_one_column(self):
        q = 'artist:little'
        results = self.lib.get(q)
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_matched(results, 'Boracay')
        self.assert_done(results)
    
    def test_mulitple_terms_narrow_search(self):
        q = 'little ones'
        results = self.lib.get(q)
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_matched(results, 'Boracay')
        self.assert_done(results)
        
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')