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

"""Various tests for querying the library database.
"""

import unittest, sys, os
sys.path.insert(0, '..')
import beets.library
import test_db

parse_query = beets.library.CollectionQuery._parse_query

some_item = test_db.item()

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

class AnySubstringQueryTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.lib.add(some_item)

    def test_no_restriction(self):
        q = beets.library.AnySubstringQuery('title')
        self.assertEqual(self.lib.get(q).next().title, 'the title')

    def test_restriction_completeness(self):
        q = beets.library.AnySubstringQuery('title', ['title'])
        self.assertEqual(self.lib.get(q).next().title, 'the title')
        
    def test_restriction_soundness(self):
        q = beets.library.AnySubstringQuery('title', ['artist'])
        self.assertRaises(StopIteration, self.lib.get(q).next)


# Convenient asserts for matching items.
class AssertsMixin(object):
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
    
class GetTest(unittest.TestCase, AssertsMixin):
    def setUp(self):
        self.lib = beets.library.Library('rsrc' + os.sep + 'test.blb')

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

class BrowseTest(unittest.TestCase, AssertsMixin):
    def setUp(self):
        self.lib = beets.library.Library('rsrc' + os.sep + 'test.blb')

    def test_artist_list(self):
        artists = list(self.lib.artists())
        self.assertEqual(artists, ['Lily Allen', 'Panda Bear',
                                   'The Little Ones'])

    def test_album_list(self):
        albums = list(self.lib.albums())
        album_names = [a.album for a in albums]
        for aname in ['Alright, Still', 'Person Pitch', 'Sing Song',
                      'Terry Tales & Fallen Gates EP']:
            self.assert_(aname in album_names)
        self.assertEqual(len(albums), 4)

    def test_item_list(self):
        items = self.lib.items()
        self.assert_matched(items, 'Littlest Things')
        self.assert_matched(items, 'Take Pills')
        self.assert_matched(items, 'Lovers Who Uncover')
        self.assert_matched(items, 'Boracay')
        self.assert_done(items)

    def test_artists_matches_artist(self):
        artists = list(self.lib.artists(query='panda'))
        self.assertEqual(artists, ['Panda Bear'])
        
    def test_artists_does_not_match_album(self):
        artists = list(self.lib.artists(query='alright'))
        self.assertEqual(artists, [])

    def test_albums_matches_album(self):
        albums = list(self.lib.albums(query='person'))
        self.assertEqual(len(albums), 1)

    def test_albums_matches_albumartist(self):
        albums = list(self.lib.albums(query='panda'))
        self.assertEqual(len(albums), 1)
        
    def test_items_matches_title(self):
        items = self.lib.items(query='boracay')
        self.assert_matched(items, 'Boracay')
        self.assert_done(items)

    def test_items_does_not_match_year(self):
        items = self.lib.items(query='2007')
        self.assert_done(items)

    #FIXME Haven't tested explicit (non-query) criteria.
        
class CountTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.item = some_item
        self.lib.add(self.item)

    def test_count_gets_single_item(self):
        songs, totaltime = beets.library.TrueQuery().count(self.lib)
        self.assertEqual(songs, 1)
        self.assertEqual(totaltime, self.item.length)

    def test_count_works_for_empty_library(self):
        self.lib.remove(self.item)
        songs, totaltime = beets.library.TrueQuery().count(self.lib)
        self.assertEqual(songs, 0)
        self.assertEqual(totaltime, 0.0)
        
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
