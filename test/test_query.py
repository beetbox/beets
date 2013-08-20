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

"""Various tests for querying the library database.
"""
import os

import _common
from _common import unittest
import beets.library

pqp = beets.library.parse_query_part

some_item = _common.item()

class QueryParseTest(unittest.TestCase):
    def test_one_basic_term(self):
        q = 'test'
        r = (None, 'test', beets.library.SubstringQuery)
        self.assertEqual(pqp(q), r)

    def test_one_keyed_term(self):
        q = 'test:val'
        r = ('test', 'val', beets.library.SubstringQuery)
        self.assertEqual(pqp(q), r)

    def test_colon_at_end(self):
        q = 'test:'
        r = (None, 'test:', beets.library.SubstringQuery)
        self.assertEqual(pqp(q), r)

    def test_one_basic_regexp(self):
        q = r':regexp'
        r = (None, 'regexp', beets.library.RegexpQuery)
        self.assertEqual(pqp(q), r)

    def test_keyed_regexp(self):
        q = r'test::regexp'
        r = ('test', 'regexp', beets.library.RegexpQuery)
        self.assertEqual(pqp(q), r)

    def test_escaped_colon(self):
        q = r'test\:val'
        r = (None, 'test:val', beets.library.SubstringQuery)
        self.assertEqual(pqp(q), r)

    def test_escaped_colon_in_regexp(self):
        q = r':test\:regexp'
        r = (None, 'test:regexp', beets.library.RegexpQuery)
        self.assertEqual(pqp(q), r)

    def test_single_year(self):
        q = 'year:1999'
        r = ('year', '1999', beets.library.NumericQuery)
        self.assertEqual(pqp(q), r)

    def test_multiple_years(self):
        q = 'year:1999..2010'
        r = ('year', '1999..2010', beets.library.NumericQuery)
        self.assertEqual(pqp(q), r)

class AnyFieldQueryTest(unittest.TestCase):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')
        self.lib.add(some_item)

    def test_no_restriction(self):
        q = beets.library.AnyFieldQuery('title', beets.library.ITEM_KEYS,
                                        beets.library.SubstringQuery)
        self.assertEqual(self.lib.items(q).next().title, 'the title')

    def test_restriction_completeness(self):
        q = beets.library.AnyFieldQuery('title', ['title'],
                                        beets.library.SubstringQuery)
        self.assertEqual(self.lib.items(q).next().title, 'the title')

    def test_restriction_soundness(self):
        q = beets.library.AnyFieldQuery('title', ['artist'],
                                        beets.library.SubstringQuery)
        self.assertRaises(StopIteration, self.lib.items(q).next)

# Convenient asserts for matching items.
class AssertsMixin(object):
    def assert_matched(self, result_iterator, title):
        self.assertEqual(result_iterator.next().title, title)
    def assert_done(self, result_iterator):
        self.assertRaises(StopIteration, result_iterator.next)
    def assert_matched_all(self, result_iterator):
        self.assert_matched(result_iterator, 'Littlest Things')
        self.assert_matched(result_iterator, 'Take Pills')
        self.assert_matched(result_iterator, 'Lovers Who Uncover')
        self.assert_matched(result_iterator, 'Boracay')
        self.assert_done(result_iterator)

class GetTest(unittest.TestCase, AssertsMixin):
    def setUp(self):
        self.lib = beets.library.Library(
            os.path.join(_common.RSRC, 'test.blb')
        )

    def test_get_empty(self):
        q = ''
        results = self.lib.items(q)
        self.assert_matched_all(results)

    def test_get_none(self):
        q = None
        results = self.lib.items(q)
        self.assert_matched_all(results)

    def test_get_one_keyed_term(self):
        q = 'artist:Lil'
        results = self.lib.items(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_done(results)

    def test_get_one_keyed_regexp(self):
        q = r'artist::L.+y'
        results = self.lib.items(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_done(results)

    def test_get_one_unkeyed_term(self):
        q = 'Terry'
        results = self.lib.items(q)
        self.assert_matched(results, 'Boracay')
        self.assert_done(results)

    def test_get_one_unkeyed_regexp(self):
        q = r':y$'
        results = self.lib.items(q)
        self.assert_matched(results, 'Boracay')
        self.assert_done(results)

    def test_get_no_matches(self):
        q = 'popebear'
        results = self.lib.items(q)
        self.assert_done(results)

    def test_invalid_key(self):
        q = 'pope:bear'
        results = self.lib.items(q)
        self.assert_matched_all(results)

    def test_term_case_insensitive(self):
        q = 'UNCoVER'
        results = self.lib.items(q)
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_done(results)

    def test_regexp_case_sensitive(self):
        q = r':UNCoVER'
        results = self.lib.items(q)
        self.assert_done(results)
        q = r':Uncover'
        results = self.lib.items(q)
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_done(results)

    def test_term_case_insensitive_with_key(self):
        q = 'album:stiLL'
        results = self.lib.items(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_done(results)

    def test_key_case_insensitive(self):
        q = 'ArTiST:Allen'
        results = self.lib.items(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_done(results)

    def test_unkeyed_term_matches_multiple_columns(self):
        q = 'little'
        results = self.lib.items(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_matched(results, 'Boracay')
        self.assert_done(results)

    def test_unkeyed_regexp_matches_multiple_columns(self):
        q = r':^T'
        results = self.lib.items(q)
        self.assert_matched(results, 'Take Pills')
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_matched(results, 'Boracay')
        self.assert_done(results)

    def test_keyed_term_matches_only_one_column(self):
        q = 'artist:little'
        results = self.lib.items(q)
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_matched(results, 'Boracay')
        self.assert_done(results)

    def test_keyed_regexp_matches_only_one_column(self):
        q = r'album::\sS'
        results = self.lib.items(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_done(results)

    def test_multiple_terms_narrow_search(self):
        q = 'little ones'
        results = self.lib.items(q)
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_matched(results, 'Boracay')
        self.assert_done(results)

    def test_multiple_regexps_narrow_search(self):
        q = r':\sS :^T'
        results = self.lib.items(q)
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_done(results)

    def test_mixed_terms_regexps_narrow_search(self):
        q = r':\sS lily'
        results = self.lib.items(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_done(results)

    def test_single_year(self):
        q = 'year:2006'
        results = self.lib.items(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_done(results)

    def test_year_range(self):
        q = 'year:2000..2010'
        results = self.lib.items(q)
        self.assert_matched(results, 'Littlest Things')
        self.assert_matched(results, 'Take Pills')
        self.assert_matched(results, 'Lovers Who Uncover')
        self.assert_done(results)

    def test_bad_year(self):
        q = 'year:delete from items'
        self.assertRaises(ValueError, self.lib.items, q)

class MemoryGetTest(unittest.TestCase, AssertsMixin):
    def setUp(self):
        self.album_item = _common.item()
        self.album_item.title = 'album item'
        self.single_item = _common.item()
        self.single_item.title = 'singleton item'
        self.single_item.comp = False

        self.lib = beets.library.Library(':memory:')
        self.lib.add(self.single_item)
        self.album = self.lib.add_album([self.album_item])

    def test_singleton_true(self):
        q = 'singleton:true'
        results = self.lib.items(q)
        self.assert_matched(results, 'singleton item')
        self.assert_done(results)

    def test_singleton_false(self):
        q = 'singleton:false'
        results = self.lib.items(q)
        self.assert_matched(results, 'album item')
        self.assert_done(results)

    def test_compilation_true(self):
        q = 'comp:true'
        results = self.lib.items(q)
        self.assert_matched(results, 'album item')
        self.assert_done(results)

    def test_compilation_false(self):
        q = 'comp:false'
        results = self.lib.items(q)
        self.assert_matched(results, 'singleton item')
        self.assert_done(results)

    def test_unknown_field_name_ignored(self):
        q = 'xyzzy:nonsense'
        results = self.lib.items(q)
        titles = [i.title for i in results]
        self.assertTrue('singleton item' in titles)
        self.assertTrue('album item' in titles)
        self.assertEqual(len(titles), 2)

    def test_unknown_field_name_ignored_in_album_query(self):
        q = 'xyzzy:nonsense'
        results = self.lib.albums(q)
        names = [a.album for a in results]
        self.assertEqual(names, ['the album'])

    def test_item_field_name_ignored_in_album_query(self):
        q = 'format:nonsense'
        results = self.lib.albums(q)
        names = [a.album for a in results]
        self.assertEqual(names, ['the album'])

    def test_unicode_query(self):
        self.single_item.title = u'caf\xe9'
        self.lib.store(self.single_item)

        q = u'title:caf\xe9'
        results = self.lib.items(q)
        self.assert_matched(results, u'caf\xe9')
        self.assert_done(results)

class MatchTest(unittest.TestCase):
    def setUp(self):
        self.item = _common.item()

    def test_regex_match_positive(self):
        q = beets.library.RegexpQuery('album', '^the album$')
        self.assertTrue(q.match(self.item))

    def test_regex_match_negative(self):
        q = beets.library.RegexpQuery('album', '^album$')
        self.assertFalse(q.match(self.item))

    def test_regex_match_non_string_value(self):
        q = beets.library.RegexpQuery('disc', '^6$')
        self.assertTrue(q.match(self.item))

    def test_substring_match_positive(self):
        q = beets.library.SubstringQuery('album', 'album')
        self.assertTrue(q.match(self.item))

    def test_substring_match_negative(self):
        q = beets.library.SubstringQuery('album', 'ablum')
        self.assertFalse(q.match(self.item))

    def test_substring_match_non_string_value(self):
        q = beets.library.SubstringQuery('disc', '6')
        self.assertTrue(q.match(self.item))

    def test_year_match_positive(self):
        q = beets.library.NumericQuery('year', '1')
        self.assertTrue(q.match(self.item))

    def test_year_match_negative(self):
        q = beets.library.NumericQuery('year', '10')
        self.assertFalse(q.match(self.item))

    def test_bitrate_range_positive(self):
        q = beets.library.NumericQuery('bitrate', '100000..200000')
        self.assertTrue(q.match(self.item))

    def test_bitrate_range_negative(self):
        q = beets.library.NumericQuery('bitrate', '200000..300000')
        self.assertFalse(q.match(self.item))

class PathQueryTest(unittest.TestCase, AssertsMixin):
    def setUp(self):
        self.lib = beets.library.Library(':memory:')

        path_item = _common.item()
        path_item.path = '/a/b/c.mp3'
        path_item.title = 'path item'
        self.lib.add(path_item)

    def test_path_exact_match(self):
        q = 'path:/a/b/c.mp3'
        results = self.lib.items(q)
        self.assert_matched(results, 'path item')
        self.assert_done(results)

    def test_parent_directory_no_slash(self):
        q = 'path:/a'
        results = self.lib.items(q)
        self.assert_matched(results, 'path item')
        self.assert_done(results)

    def test_parent_directory_with_slash(self):
        q = 'path:/a/'
        results = self.lib.items(q)
        self.assert_matched(results, 'path item')
        self.assert_done(results)

    def test_no_match(self):
        q = 'path:/xyzzy/'
        results = self.lib.items(q)
        self.assert_done(results)

    def test_fragment_no_match(self):
        q = 'path:/b/'
        results = self.lib.items(q)
        self.assert_done(results)

    def test_nonnorm_path(self):
        q = 'path:/x/../a/b'
        results = self.lib.items(q)
        self.assert_matched(results, 'path item')
        self.assert_done(results)

    def test_slashed_query_matches_path(self):
        q = '/a/b'
        results = self.lib.items(q)
        self.assert_matched(results, 'path item')
        self.assert_done(results)

    def test_non_slashed_does_not_match_path(self):
        q = 'c.mp3'
        results = self.lib.items(q)
        self.assert_done(results)

    def test_slashes_in_explicit_field_does_not_match_path(self):
        q = 'title:/a/b'
        results = self.lib.items(q)
        self.assert_done(results)

    def test_path_regex(self):
        q = 'path::\\.mp3$'
        results = self.lib.items(q)
        self.assert_matched(results, 'path item')
        self.assert_done(results)

class BrowseTest(unittest.TestCase, AssertsMixin):
    def setUp(self):
        self.lib = beets.library.Library(
            os.path.join(_common.RSRC, 'test.blb')
        )

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

    def test_albums_matches_album(self):
        albums = list(self.lib.albums('person'))
        self.assertEqual(len(albums), 1)

    def test_albums_matches_albumartist(self):
        albums = list(self.lib.albums('panda'))
        self.assertEqual(len(albums), 1)

    def test_items_matches_title(self):
        items = self.lib.items('boracay')
        self.assert_matched(items, 'Boracay')
        self.assert_done(items)

    def test_items_does_not_match_year(self):
        items = self.lib.items('2007')
        self.assert_done(items)

class StringParseTest(unittest.TestCase):
    def test_single_field_query(self):
        q = beets.library.AndQuery.from_string(u'albumtype:soundtrack')
        self.assertEqual(len(q.subqueries), 1)
        subq = q.subqueries[0]
        self.assertTrue(isinstance(subq, beets.library.SubstringQuery))
        self.assertEqual(subq.field, 'albumtype')
        self.assertEqual(subq.pattern, 'soundtrack')

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
