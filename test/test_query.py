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
import _common
from _common import unittest
import beets.library
from beets import dbcore


class AnyFieldQueryTest(_common.LibTestCase):
    def test_no_restriction(self):
        q = dbcore.query.AnyFieldQuery(
            'title', beets.library.Item._fields.keys(),
            dbcore.query.SubstringQuery
        )
        self.assertEqual(self.lib.items(q).get().title, 'the title')

    def test_restriction_completeness(self):
        q = dbcore.query.AnyFieldQuery('title', ['title'],
                                       dbcore.query.SubstringQuery)
        self.assertEqual(self.lib.items(q).get().title, 'the title')

    def test_restriction_soundness(self):
        q = dbcore.query.AnyFieldQuery('title', ['artist'],
                                       dbcore.query.SubstringQuery)
        self.assertEqual(self.lib.items(q).get(), None)


class AssertsMixin(object):
    def assert_matched(self, results, titles):
        self.assertEqual([i.title for i in results], titles)


# A test case class providing a library with some dummy data and some
# assertions involving that data.
class DummyDataTestCase(_common.TestCase, AssertsMixin):
    def setUp(self):
        super(DummyDataTestCase, self).setUp()
        self.lib = beets.library.Library(':memory:')
        items = [_common.item() for _ in range(3)]
        items[0].title = 'foo bar'
        items[0].artist = 'one'
        items[0].album = 'baz'
        items[0].year = 2001
        items[0].comp = True
        items[1].title = 'baz qux'
        items[1].artist = 'two'
        items[1].album = 'baz'
        items[1].year = 2002
        items[1].comp = True
        items[2].title = 'beets 4 eva'
        items[2].artist = 'three'
        items[2].album = 'foo'
        items[2].year = 2003
        items[2].comp = False
        for item in items:
            self.lib.add(item)
        self.lib.add_album(items[:2])

    def assert_matched_all(self, results):
        self.assert_matched(results, [
            'foo bar',
            'baz qux',
            'beets 4 eva',
        ])


class GetTest(DummyDataTestCase):
    def test_get_empty(self):
        q = ''
        results = self.lib.items(q)
        self.assert_matched_all(results)

    def test_get_none(self):
        q = None
        results = self.lib.items(q)
        self.assert_matched_all(results)

    def test_get_one_keyed_term(self):
        q = 'title:qux'
        results = self.lib.items(q)
        self.assert_matched(results, ['baz qux'])

    def test_get_one_keyed_regexp(self):
        q = r'artist::t.+r'
        results = self.lib.items(q)
        self.assert_matched(results, ['beets 4 eva'])

    def test_get_one_unkeyed_term(self):
        q = 'three'
        results = self.lib.items(q)
        self.assert_matched(results, ['beets 4 eva'])

    def test_get_one_unkeyed_regexp(self):
        q = r':x$'
        results = self.lib.items(q)
        self.assert_matched(results, ['baz qux'])

    def test_get_no_matches(self):
        q = 'popebear'
        results = self.lib.items(q)
        self.assert_matched(results, [])

    def test_invalid_key(self):
        q = 'pope:bear'
        results = self.lib.items(q)
        # Matches nothing since the flexattr is not present on the
        # objects.
        self.assert_matched(results, [])

    def test_term_case_insensitive(self):
        q = 'oNE'
        results = self.lib.items(q)
        self.assert_matched(results, ['foo bar'])

    def test_regexp_case_sensitive(self):
        q = r':oNE'
        results = self.lib.items(q)
        self.assert_matched(results, [])
        q = r':one'
        results = self.lib.items(q)
        self.assert_matched(results, ['foo bar'])

    def test_term_case_insensitive_with_key(self):
        q = 'artist:thrEE'
        results = self.lib.items(q)
        self.assert_matched(results, ['beets 4 eva'])

    def test_key_case_insensitive(self):
        q = 'ArTiST:three'
        results = self.lib.items(q)
        self.assert_matched(results, ['beets 4 eva'])

    def test_unkeyed_term_matches_multiple_columns(self):
        q = 'baz'
        results = self.lib.items(q)
        self.assert_matched(results, [
            'foo bar',
            'baz qux',
        ])

    def test_unkeyed_regexp_matches_multiple_columns(self):
        q = r':z$'
        results = self.lib.items(q)
        self.assert_matched(results, [
            'foo bar',
            'baz qux',
        ])

    def test_keyed_term_matches_only_one_column(self):
        q = 'title:baz'
        results = self.lib.items(q)
        self.assert_matched(results, ['baz qux'])

    def test_keyed_regexp_matches_only_one_column(self):
        q = r'title::baz'
        results = self.lib.items(q)
        self.assert_matched(results, [
            'baz qux',
        ])

    def test_multiple_terms_narrow_search(self):
        q = 'qux baz'
        results = self.lib.items(q)
        self.assert_matched(results, [
            'baz qux',
        ])

    def test_multiple_regexps_narrow_search(self):
        q = r':baz :qux'
        results = self.lib.items(q)
        self.assert_matched(results, ['baz qux'])

    def test_mixed_terms_regexps_narrow_search(self):
        q = r':baz qux'
        results = self.lib.items(q)
        self.assert_matched(results, ['baz qux'])

    def test_single_year(self):
        q = 'year:2001'
        results = self.lib.items(q)
        self.assert_matched(results, ['foo bar'])

    def test_year_range(self):
        q = 'year:2000..2002'
        results = self.lib.items(q)
        self.assert_matched(results, [
            'foo bar',
            'baz qux',
        ])

    def test_bad_year(self):
        q = 'year:delete from items'
        results = self.lib.items(q)
        self.assert_matched(results, [])

    def test_singleton_true(self):
        q = 'singleton:true'
        results = self.lib.items(q)
        self.assert_matched(results, ['beets 4 eva'])

    def test_singleton_false(self):
        q = 'singleton:false'
        results = self.lib.items(q)
        self.assert_matched(results, ['foo bar', 'baz qux'])

    def test_compilation_true(self):
        q = 'comp:true'
        results = self.lib.items(q)
        self.assert_matched(results, ['foo bar', 'baz qux'])

    def test_compilation_false(self):
        q = 'comp:false'
        results = self.lib.items(q)
        self.assert_matched(results, ['beets 4 eva'])

    def test_unknown_field_name_no_results(self):
        q = 'xyzzy:nonsense'
        results = self.lib.items(q)
        titles = [i.title for i in results]
        self.assertEqual(titles, [])

    def test_unknown_field_name_no_results_in_album_query(self):
        q = 'xyzzy:nonsense'
        results = self.lib.albums(q)
        names = [a.album for a in results]
        self.assertEqual(names, [])

    def test_item_field_name_matches_nothing_in_album_query(self):
        q = 'format:nonsense'
        results = self.lib.albums(q)
        names = [a.album for a in results]
        self.assertEqual(names, [])

    def test_unicode_query(self):
        item = self.lib.items().get()
        item.title = u'caf\xe9'
        item.store()

        q = u'title:caf\xe9'
        results = self.lib.items(q)
        self.assert_matched(results, [u'caf\xe9'])

    def test_numeric_search_positive(self):
        q = dbcore.query.NumericQuery('year', '2001')
        results = self.lib.items(q)
        self.assertTrue(results)

    def test_numeric_search_negative(self):
        q = dbcore.query.NumericQuery('year', '1999')
        results = self.lib.items(q)
        self.assertFalse(results)

    def test_numeric_empty(self):
        q = dbcore.query.NumericQuery('year', '')
        results = self.lib.items(q)
        self.assertTrue(results)


class MatchTest(_common.TestCase):
    def setUp(self):
        super(MatchTest, self).setUp()
        self.item = _common.item()

    def test_regex_match_positive(self):
        q = dbcore.query.RegexpQuery('album', '^the album$')
        self.assertTrue(q.match(self.item))

    def test_regex_match_negative(self):
        q = dbcore.query.RegexpQuery('album', '^album$')
        self.assertFalse(q.match(self.item))

    def test_regex_match_non_string_value(self):
        q = dbcore.query.RegexpQuery('disc', '^6$')
        self.assertTrue(q.match(self.item))

    def test_substring_match_positive(self):
        q = dbcore.query.SubstringQuery('album', 'album')
        self.assertTrue(q.match(self.item))

    def test_substring_match_negative(self):
        q = dbcore.query.SubstringQuery('album', 'ablum')
        self.assertFalse(q.match(self.item))

    def test_substring_match_non_string_value(self):
        q = dbcore.query.SubstringQuery('disc', '6')
        self.assertTrue(q.match(self.item))

    def test_year_match_positive(self):
        q = dbcore.query.NumericQuery('year', '1')
        self.assertTrue(q.match(self.item))

    def test_year_match_negative(self):
        q = dbcore.query.NumericQuery('year', '10')
        self.assertFalse(q.match(self.item))

    def test_bitrate_range_positive(self):
        q = dbcore.query.NumericQuery('bitrate', '100000..200000')
        self.assertTrue(q.match(self.item))

    def test_bitrate_range_negative(self):
        q = dbcore.query.NumericQuery('bitrate', '200000..300000')
        self.assertFalse(q.match(self.item))


class PathQueryTest(_common.LibTestCase, AssertsMixin):
    def setUp(self):
        super(PathQueryTest, self).setUp()
        self.i.path = '/a/b/c.mp3'
        self.i.title = 'path item'
        self.i.store()

    def test_path_exact_match(self):
        q = 'path:/a/b/c.mp3'
        results = self.lib.items(q)
        self.assert_matched(results, ['path item'])

    def test_parent_directory_no_slash(self):
        q = 'path:/a'
        results = self.lib.items(q)
        self.assert_matched(results, ['path item'])

    def test_parent_directory_with_slash(self):
        q = 'path:/a/'
        results = self.lib.items(q)
        self.assert_matched(results, ['path item'])

    def test_no_match(self):
        q = 'path:/xyzzy/'
        results = self.lib.items(q)
        self.assert_matched(results, [])

    def test_fragment_no_match(self):
        q = 'path:/b/'
        results = self.lib.items(q)
        self.assert_matched(results, [])

    def test_nonnorm_path(self):
        q = 'path:/x/../a/b'
        results = self.lib.items(q)
        self.assert_matched(results, ['path item'])

    def test_slashed_query_matches_path(self):
        q = '/a/b'
        results = self.lib.items(q)
        self.assert_matched(results, ['path item'])

    def test_non_slashed_does_not_match_path(self):
        q = 'c.mp3'
        results = self.lib.items(q)
        self.assert_matched(results, [])

    def test_slashes_in_explicit_field_does_not_match_path(self):
        q = 'title:/a/b'
        results = self.lib.items(q)
        self.assert_matched(results, [])

    def test_path_regex(self):
        q = 'path::\\.mp3$'
        results = self.lib.items(q)
        self.assert_matched(results, ['path item'])


class DefaultSearchFieldsTest(DummyDataTestCase):
    def test_albums_matches_album(self):
        albums = list(self.lib.albums('baz'))
        self.assertEqual(len(albums), 1)

    def test_albums_matches_albumartist(self):
        albums = list(self.lib.albums(['album artist']))
        self.assertEqual(len(albums), 1)

    def test_items_matches_title(self):
        items = self.lib.items('beets')
        self.assert_matched(items, ['beets 4 eva'])

    def test_items_does_not_match_year(self):
        items = self.lib.items('2001')
        self.assert_matched(items, [])


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
