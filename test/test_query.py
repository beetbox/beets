# This file is part of beets.
# Copyright 2009, Adrian Sampson.
# 
# Beets is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Beets is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with beets.  If not, see <http://www.gnu.org/licenses/>.

"""Various tests for querying the library database.
"""

import unittest, sys, os
sys.path.append('..')
import beets.library

parse_query = beets.library.CollectionQuery._parse_query

some_item = beets.library.Item({
    'title':      u'the title',
    'artist':     u'the artist',
    'album':      u'the album',
    'genre':      u'the genre',
    'composer':   u'the composer',
    'grouping':   u'the grouping',
    'year':       1,
    'month':      2,
    'day':        3,
    'track':      4,
    'tracktotal': 5,
    'disc':       6,
    'disctotal':  7,
    'lyrics':     u'the lyrics',
    'comments':   u'the comments',
    'bpm':        8,
    'comp':       True,
    'path':       'somepath',
    'length':     60.0,
    'bitrate':    128000,
})

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
        self.assertEqual(albums, [
            ('Lily Allen', 'Alright, Still'),
            ('Panda Bear', 'Person Pitch'),
            ('The Little Ones', 'Sing Song'),
            ('The Little Ones', 'Terry Tales & Fallen Gates EP'),
        ])

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
        self.assertEqual(albums, [('Panda Bear', 'Person Pitch')])
        
    def test_albums_does_not_match_title(self):
        albums = list(self.lib.albums(query='boracay'))
        self.assertEqual(albums, [])

    def test_items_matches_title(self):
        items = self.lib.items(query='boracay')
        self.assert_matched(items, 'Boracay')
        self.assert_done(items)

    def test_items_does_not_match_year(self):
        items = self.lib.items(query='2007')
        self.assert_done(items)

    #FIXME Haven't tested explicit (non-query) criteria.
        
        
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
