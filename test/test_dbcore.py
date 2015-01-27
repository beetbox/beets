# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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

"""Tests for the DBCore database abstraction.
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import os
import sqlite3

from test._common import unittest
from beets import dbcore
from tempfile import mkstemp


# Fixture: concrete database and model classes. For migration tests, we
# have multiple models with different numbers of fields.

class TestSort(dbcore.query.FieldSort):
    pass


class TestModel1(dbcore.Model):
    _table = 'test'
    _flex_table = 'testflex'
    _fields = {
        'id': dbcore.types.PRIMARY_ID,
        'field_one': dbcore.types.INTEGER,
    }
    _types = {
        'some_float_field': dbcore.types.FLOAT,
    }
    _sorts = {
        'some_sort': TestSort,
    }

    @classmethod
    def _getters(cls):
        return {}

    def _template_funcs(self):
        return {}


class TestDatabase1(dbcore.Database):
    _models = (TestModel1,)
    pass


class TestModel2(TestModel1):
    _fields = {
        'id': dbcore.types.PRIMARY_ID,
        'field_one': dbcore.types.INTEGER,
        'field_two': dbcore.types.INTEGER,
    }


class TestDatabase2(dbcore.Database):
    _models = (TestModel2,)
    pass


class TestModel3(TestModel1):
    _fields = {
        'id': dbcore.types.PRIMARY_ID,
        'field_one': dbcore.types.INTEGER,
        'field_two': dbcore.types.INTEGER,
        'field_three': dbcore.types.INTEGER,
    }


class TestDatabase3(dbcore.Database):
    _models = (TestModel3,)
    pass


class TestModel4(TestModel1):
    _fields = {
        'id': dbcore.types.PRIMARY_ID,
        'field_one': dbcore.types.INTEGER,
        'field_two': dbcore.types.INTEGER,
        'field_three': dbcore.types.INTEGER,
        'field_four': dbcore.types.INTEGER,
    }


class TestDatabase4(dbcore.Database):
    _models = (TestModel4,)
    pass


class AnotherTestModel(TestModel1):
    _table = 'another'
    _flex_table = 'anotherflex'
    _fields = {
        'id': dbcore.types.PRIMARY_ID,
        'foo': dbcore.types.INTEGER,
    }


class TestDatabaseTwoModels(dbcore.Database):
    _models = (TestModel2, AnotherTestModel)
    pass


class MigrationTest(unittest.TestCase):
    """Tests the ability to change the database schema between
    versions.
    """
    def setUp(self):
        handle, self.libfile = mkstemp('db')
        os.close(handle)
        # Set up a database with the two-field schema.
        old_lib = TestDatabase2(self.libfile)

        # Add an item to the old library.
        old_lib._connection().execute(
            'insert into test (field_one, field_two) values (4, 2)'
        )
        old_lib._connection().commit()
        del old_lib

    def tearDown(self):
        os.remove(self.libfile)

    def test_open_with_same_fields_leaves_untouched(self):
        new_lib = TestDatabase2(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        self.assertEqual(len(row.keys()), len(TestModel2._fields))

    def test_open_with_new_field_adds_column(self):
        new_lib = TestDatabase3(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        self.assertEqual(len(row.keys()), len(TestModel3._fields))

    def test_open_with_fewer_fields_leaves_untouched(self):
        new_lib = TestDatabase1(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        self.assertEqual(len(row.keys()), len(TestModel2._fields))

    def test_open_with_multiple_new_fields(self):
        new_lib = TestDatabase4(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        self.assertEqual(len(row.keys()), len(TestModel4._fields))

    def test_extra_model_adds_table(self):
        new_lib = TestDatabaseTwoModels(self.libfile)
        try:
            new_lib._connection().execute("select * from another")
        except sqlite3.OperationalError:
            self.fail("select failed")


class ModelTest(unittest.TestCase):
    def setUp(self):
        self.db = TestDatabase1(':memory:')

    def tearDown(self):
        self.db._connection().close()

    def test_add_model(self):
        model = TestModel1()
        model.add(self.db)
        rows = self.db._connection().execute('select * from test').fetchall()
        self.assertEqual(len(rows), 1)

    def test_store_fixed_field(self):
        model = TestModel1()
        model.add(self.db)
        model.field_one = 123
        model.store()
        row = self.db._connection().execute('select * from test').fetchone()
        self.assertEqual(row[b'field_one'], 123)

    def test_retrieve_by_id(self):
        model = TestModel1()
        model.add(self.db)
        other_model = self.db._get(TestModel1, model.id)
        self.assertEqual(model.id, other_model.id)

    def test_store_and_retrieve_flexattr(self):
        model = TestModel1()
        model.add(self.db)
        model.foo = 'bar'
        model.store()

        other_model = self.db._get(TestModel1, model.id)
        self.assertEqual(other_model.foo, 'bar')

    def test_delete_flexattr(self):
        model = TestModel1()
        model['foo'] = 'bar'
        self.assertTrue('foo' in model)
        del model['foo']
        self.assertFalse('foo' in model)

    def test_delete_flexattr_via_dot(self):
        model = TestModel1()
        model['foo'] = 'bar'
        self.assertTrue('foo' in model)
        del model.foo
        self.assertFalse('foo' in model)

    def test_delete_flexattr_persists(self):
        model = TestModel1()
        model.add(self.db)
        model.foo = 'bar'
        model.store()

        model = self.db._get(TestModel1, model.id)
        del model['foo']
        model.store()

        model = self.db._get(TestModel1, model.id)
        self.assertFalse('foo' in model)

    def test_delete_non_existent_attribute(self):
        model = TestModel1()
        with self.assertRaises(KeyError):
            del model['foo']

    def test_delete_fixed_attribute(self):
        model = TestModel1()
        with self.assertRaises(KeyError):
            del model['field_one']

    def test_null_value_normalization_by_type(self):
        model = TestModel1()
        model.field_one = None
        self.assertEqual(model.field_one, 0)

    def test_null_value_stays_none_for_untyped_field(self):
        model = TestModel1()
        model.foo = None
        self.assertEqual(model.foo, None)

    def test_normalization_for_typed_flex_fields(self):
        model = TestModel1()
        model.some_float_field = None
        self.assertEqual(model.some_float_field, 0.0)

    def test_load_deleted_flex_field(self):
        model1 = TestModel1()
        model1['flex_field'] = True
        model1.add(self.db)

        model2 = self.db._get(TestModel1, model1.id)
        self.assertIn('flex_field', model2)

        del model1['flex_field']
        model1.store()

        model2.load()
        self.assertNotIn('flex_field', model2)


class FormatTest(unittest.TestCase):
    def test_format_fixed_field(self):
        model = TestModel1()
        model.field_one = u'caf\xe9'
        value = model.formatted().get('field_one')
        self.assertEqual(value, u'caf\xe9')

    def test_format_flex_field(self):
        model = TestModel1()
        model.other_field = u'caf\xe9'
        value = model.formatted().get('other_field')
        self.assertEqual(value, u'caf\xe9')

    def test_format_flex_field_bytes(self):
        model = TestModel1()
        model.other_field = u'caf\xe9'.encode('utf8')
        value = model.formatted().get('other_field')
        self.assertTrue(isinstance(value, unicode))
        self.assertEqual(value, u'caf\xe9')

    def test_format_unset_field(self):
        model = TestModel1()
        value = model.formatted().get('other_field')
        self.assertEqual(value, u'')

    def test_format_typed_flex_field(self):
        model = TestModel1()
        model.some_float_field = 3.14159265358979
        value = model.formatted().get('some_float_field')
        self.assertEqual(value, u'3.1')


class FormattedMappingTest(unittest.TestCase):
    def test_keys_equal_model_keys(self):
        model = TestModel1()
        formatted = model.formatted()
        self.assertEqual(set(model.keys(True)), set(formatted.keys()))

    def test_get_unset_field(self):
        model = TestModel1()
        formatted = model.formatted()
        with self.assertRaises(KeyError):
            formatted['other_field']

    def test_get_method_with_default(self):
        model = TestModel1()
        formatted = model.formatted()
        self.assertEqual(formatted.get('other_field'), u'')

    def test_get_method_with_specified_default(self):
        model = TestModel1()
        formatted = model.formatted()
        self.assertEqual(formatted.get('other_field', 'default'), 'default')


class ParseTest(unittest.TestCase):
    def test_parse_fixed_field(self):
        value = TestModel1._parse('field_one', u'2')
        self.assertIsInstance(value, int)
        self.assertEqual(value, 2)

    def test_parse_flex_field(self):
        value = TestModel1._parse('some_float_field', u'2')
        self.assertIsInstance(value, float)
        self.assertEqual(value, 2.0)

    def test_parse_untyped_field(self):
        value = TestModel1._parse('field_nine', u'2')
        self.assertEqual(value, u'2')


class QueryParseTest(unittest.TestCase):
    def pqp(self, part):
        return dbcore.queryparse.parse_query_part(
            part,
            {'year': dbcore.query.NumericQuery},
            {':': dbcore.query.RegexpQuery},
        )

    def test_one_basic_term(self):
        q = 'test'
        r = (None, 'test', dbcore.query.SubstringQuery)
        self.assertEqual(self.pqp(q), r)

    def test_one_keyed_term(self):
        q = 'test:val'
        r = ('test', 'val', dbcore.query.SubstringQuery)
        self.assertEqual(self.pqp(q), r)

    def test_colon_at_end(self):
        q = 'test:'
        r = ('test', '', dbcore.query.SubstringQuery)
        self.assertEqual(self.pqp(q), r)

    def test_one_basic_regexp(self):
        q = r':regexp'
        r = (None, 'regexp', dbcore.query.RegexpQuery)
        self.assertEqual(self.pqp(q), r)

    def test_keyed_regexp(self):
        q = r'test::regexp'
        r = ('test', 'regexp', dbcore.query.RegexpQuery)
        self.assertEqual(self.pqp(q), r)

    def test_escaped_colon(self):
        q = r'test\:val'
        r = (None, 'test:val', dbcore.query.SubstringQuery)
        self.assertEqual(self.pqp(q), r)

    def test_escaped_colon_in_regexp(self):
        q = r':test\:regexp'
        r = (None, 'test:regexp', dbcore.query.RegexpQuery)
        self.assertEqual(self.pqp(q), r)

    def test_single_year(self):
        q = 'year:1999'
        r = ('year', '1999', dbcore.query.NumericQuery)
        self.assertEqual(self.pqp(q), r)

    def test_multiple_years(self):
        q = 'year:1999..2010'
        r = ('year', '1999..2010', dbcore.query.NumericQuery)
        self.assertEqual(self.pqp(q), r)

    def test_empty_query_part(self):
        q = ''
        r = (None, '', dbcore.query.SubstringQuery)
        self.assertEqual(self.pqp(q), r)


class QueryFromStringsTest(unittest.TestCase):
    def qfs(self, strings):
        return dbcore.queryparse.query_from_strings(
            dbcore.query.AndQuery,
            TestModel1,
            {':': dbcore.query.RegexpQuery},
            strings,
        )

    def test_zero_parts(self):
        q = self.qfs([])
        self.assertIsInstance(q, dbcore.query.AndQuery)
        self.assertEqual(len(q.subqueries), 1)
        self.assertIsInstance(q.subqueries[0], dbcore.query.TrueQuery)

    def test_two_parts(self):
        q = self.qfs(['foo', 'bar:baz'])
        self.assertIsInstance(q, dbcore.query.AndQuery)
        self.assertEqual(len(q.subqueries), 2)
        self.assertIsInstance(q.subqueries[0], dbcore.query.AnyFieldQuery)
        self.assertIsInstance(q.subqueries[1], dbcore.query.SubstringQuery)

    def test_parse_fixed_type_query(self):
        q = self.qfs(['field_one:2..3'])
        self.assertIsInstance(q.subqueries[0], dbcore.query.NumericQuery)

    def test_parse_flex_type_query(self):
        q = self.qfs(['some_float_field:2..3'])
        self.assertIsInstance(q.subqueries[0], dbcore.query.NumericQuery)

    def test_empty_query_part(self):
        q = self.qfs([''])
        self.assertIsInstance(q.subqueries[0], dbcore.query.TrueQuery)


class SortFromStringsTest(unittest.TestCase):
    def sfs(self, strings):
        return dbcore.queryparse.sort_from_strings(
            TestModel1,
            strings,
        )

    def test_zero_parts(self):
        s = self.sfs([])
        self.assertIsInstance(s, dbcore.query.NullSort)

    def test_one_parts(self):
        s = self.sfs(['field+'])
        self.assertIsInstance(s, dbcore.query.Sort)

    def test_two_parts(self):
        s = self.sfs(['field+', 'another_field-'])
        self.assertIsInstance(s, dbcore.query.MultipleSort)
        self.assertEqual(len(s.sorts), 2)

    def test_fixed_field_sort(self):
        s = self.sfs(['field_one+'])
        self.assertIsInstance(s, dbcore.query.MultipleSort)
        self.assertIsInstance(s.sorts[0], dbcore.query.FixedFieldSort)

    def test_flex_field_sort(self):
        s = self.sfs(['flex_field+'])
        self.assertIsInstance(s, dbcore.query.MultipleSort)
        self.assertIsInstance(s.sorts[0], dbcore.query.SlowFieldSort)

    def test_special_sort(self):
        s = self.sfs(['some_sort+'])
        self.assertIsInstance(s.sorts[0], TestSort)


class ResultsIteratorTest(unittest.TestCase):
    def setUp(self):
        self.db = TestDatabase1(':memory:')
        model = TestModel1()
        model['foo'] = 'baz'
        model.add(self.db)
        model = TestModel1()
        model['foo'] = 'bar'
        model.add(self.db)

    def tearDown(self):
        self.db._connection().close()

    def test_iterate_once(self):
        objs = self.db._fetch(TestModel1)
        self.assertEqual(len(list(objs)), 2)

    def test_iterate_twice(self):
        objs = self.db._fetch(TestModel1)
        list(objs)
        self.assertEqual(len(list(objs)), 2)

    def test_concurrent_iterators(self):
        results = self.db._fetch(TestModel1)
        it1 = iter(results)
        it2 = iter(results)
        it1.next()
        list(it2)
        self.assertEqual(len(list(it1)), 1)

    def test_slow_query(self):
        q = dbcore.query.SubstringQuery('foo', 'ba', False)
        objs = self.db._fetch(TestModel1, q)
        self.assertEqual(len(list(objs)), 2)

    def test_slow_query_negative(self):
        q = dbcore.query.SubstringQuery('foo', 'qux', False)
        objs = self.db._fetch(TestModel1, q)
        self.assertEqual(len(list(objs)), 0)

    def test_iterate_slow_sort(self):
        s = dbcore.query.SlowFieldSort('foo')
        res = self.db._fetch(TestModel1, sort=s)
        objs = list(res)
        self.assertEqual(objs[0].foo, 'bar')
        self.assertEqual(objs[1].foo, 'baz')

    def test_unsorted_subscript(self):
        objs = self.db._fetch(TestModel1)
        self.assertEqual(objs[0].foo, 'baz')
        self.assertEqual(objs[1].foo, 'bar')

    def test_slow_sort_subscript(self):
        s = dbcore.query.SlowFieldSort('foo')
        objs = self.db._fetch(TestModel1, sort=s)
        self.assertEqual(objs[0].foo, 'bar')
        self.assertEqual(objs[1].foo, 'baz')

    def test_length(self):
        objs = self.db._fetch(TestModel1)
        self.assertEqual(len(objs), 2)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
