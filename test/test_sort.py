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



# A test case class providing a library with some dummy data and some
# assertions involving that data.
class DummyDataTestCase(_common.TestCase):
    def setUp(self):
        super(DummyDataTestCase, self).setUp()
        self.lib = beets.library.Library(':memory:')
        items = [_common.item() for _ in range(3)]
        items[0].title = 'foo bar'
        items[0].artist = 'one'
        items[0].album = 'baz'
        items[0].year = 2001
        items[0].comp = True
        items[0].flex1 = "flex1-0"
        items[0].flex2 = "flex2-A"
        items[1].title = 'baz qux'
        items[1].artist = 'two'
        items[1].album = 'baz'
        items[1].year = 2002
        items[1].comp = True
        items[1].flex1 = "flex1-1"
        items[1].flex2 = "flex2-A"
        items[2].title = 'beets 4 eva'
        items[2].artist = 'three'
        items[2].album = 'foo'
        items[2].year = 2003
        items[2].comp = False
        items[2].flex1 = "flex1-2"
        items[2].flex2 = "flex1-B"
        for item in items:
            self.lib.add(item)
        self.lib.add_album(items[:2])


class SortFixedFieldTest(DummyDataTestCase):
    def test_sort_asc(self):
        q = ''
        sort = dbcore.query.FixedFieldSort("year", True)
        results = self.lib.items(q, sort)
        self.assertTrue(results[0]['year']<results[1]['year'])
        self.assertEqual(results[0]['year'],2001)
        # same thing with query string
        q = 'year+'
        results2 = self.lib.items(q)
        for r1, r2 in zip(results, results2) :
            self.assertEqual(r1.id, r2.id)

    def test_sort_desc(self):
        q = ''
        sort = dbcore.query.FixedFieldSort("year", False)
        results = self.lib.items(q, sort)
        self.assertTrue(results[0]['year']>results[1]['year'])
        self.assertEqual(results[0]['year'],2003)
        # same thing with query string
        q = 'year-'
        results2 = self.lib.items(q)
        for r1, r2 in zip(results, results2) :
            self.assertEqual(r1.id, r2.id)

    def test_sort_two_field_asc(self):
        q = ''
        s1 = dbcore.query.FixedFieldSort("album", True)
        s2 = dbcore.query.FixedFieldSort("year", True)
        sort = dbcore.query.MultipleSort()
        sort.add_criteria(s1)
        sort.add_criteria(s2)
        results = self.lib.items(q, sort)
        self.assertTrue(results[0]['album']<=results[1]['album'])
        self.assertTrue(results[1]['album']<=results[2]['album'])
        self.assertEqual(results[0]['album'],'baz')
        self.assertEqual(results[1]['album'],'baz')
        self.assertTrue(results[0]['year']<=results[1]['year'])
        #same thing with query string
        q = 'album+ year+'
        results2 = self.lib.items(q)
        for r1, r2 in zip(results, results2) :
            self.assertEqual(r1.id, r2.id)


class SortFlexFieldTest(DummyDataTestCase):
    def test_sort_asc(self):
        q = ''
        sort = dbcore.query.FlexFieldSort(beets.library.Item, "flex1", True)
        results = self.lib.items(q, sort)
        self.assertTrue(results[0]['flex1']<results[1]['flex1'])
        self.assertEqual(results[0]['flex1'],'flex1-0')
        # same thing with query string
        q = 'flex1+'
        results2 = self.lib.items(q)
        for r1, r2 in zip(results, results2) :
            self.assertEqual(r1.id, r2.id)

    def test_sort_desc(self):
        q = ''
        sort = dbcore.query.FlexFieldSort(beets.library.Item, "flex1", False)
        results = self.lib.items(q, sort)
        self.assertTrue(results[0]['flex1']>results[1]['flex1'])
        self.assertEqual(results[0]['flex1'],'flex1-2')
        # same thing with query string
        q = 'flex1-'
        results2 = self.lib.items(q)
        for r1, r2 in zip(results, results2) :
            self.assertEqual(r1.id, r2.id)

    def test_sort_two_field(self):
        q = ''
        s1 = dbcore.query.FlexFieldSort(beets.library.Item, "flex2", False)
        s2 = dbcore.query.FlexFieldSort(beets.library.Item, "flex1", True)
        sort = dbcore.query.MultipleSort()
        sort.add_criteria(s1)
        sort.add_criteria(s2)
        results = self.lib.items(q, sort)
        self.assertTrue(results[0]['flex2']>=results[1]['flex2'])
        self.assertTrue(results[1]['flex2']>=results[2]['flex2'])
        self.assertEqual(results[0]['flex2'],'flex2-A')
        self.assertEqual(results[1]['flex2'],'flex2-A')
        self.assertTrue(results[0]['flex1']<=results[1]['flex1'])
        #same thing with query string
        q = 'flex2- flex1+'
        results2 = self.lib.items(q)
        for r1, r2 in zip(results, results2) :
            self.assertEqual(r1.id, r2.id)





def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
