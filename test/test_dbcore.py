# This file is part of beets.
# Copyright 2014, Adrian Sampson.
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
import os
import sqlite3

from _common import unittest
from beets import dbcore
from tempfile import mkstemp


# Fixture: concrete database and model classes. For migration tests, we
# have multiple models with different numbers of fields.

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
        self.assertEqual(0, len(self.db._fetch(TestModel1)))
        TestModel1().add(self.db)
        self.assertEqual(1, len(self.db._fetch(TestModel1)))

    def test_retrieve_by_id(self):
        model = TestModel1()
        model.add(self.db)
        other_model = self.db._get(TestModel1, model.id)
        self.assertEqual(model.id, other_model.id)

    def test_store_fixed_field(self):
        model = TestModel1()
        model.add(self.db)
        model['field_one'] = 123
        model.store()

        model = self.db._get(TestModel1, model.id)
        self.assertEqual(model['field_one'], 123)

    def test_add_fields(self):
        model = TestModel1()
        model['field_one'] = 123
        model.add(self.db)

        model = self.db._get(TestModel1, model.id)
        self.assertEqual(model['field_one'], 123)

    def test_store_and_retrieve_flexattr(self):
        model = TestModel1()
        model.add(self.db)
        model['foo'] = 'bar'
        model.store()

        other_model = self.db._get(TestModel1, model.id)
        self.assertEqual(other_model['foo'], 'bar')

    def test_delete_flexattr(self):
        model = TestModel1()
        model['foo'] = 'bar'
        self.assertTrue('foo' in model)
        del model['foo']
        self.assertFalse('foo' in model)

    def test_delete_flexattr_persists(self):
        model = TestModel1()
        model.add(self.db)
        model['foo'] = 'bar'
        model.store()

        model = self.db._get(TestModel1, model.id)
        del model['foo']
        model.store()

        model = self.db._get(TestModel1, model.id)
        self.assertNotIn('foo', model)

    def test_delete_non_existent_attribute(self):
        model = TestModel1()
        with self.assertRaises(KeyError):
            del model['foo']

    def test_delete_fixed_attribute(self):
        model = TestModel1(field_one=True)
        self.assertIsNotNone(model['field_one'])
        del model['field_one']
        self.assertIsNone(model['field_one'])

    def test_delete_fixed_attribute_persists(self):
        model = TestModel1(db=self.db, field_one=True)
        model.add()

        model = self.db._get(TestModel1, model.id)
        self.assertIsNotNone(model['field_one'])
        del model['field_one']
        model.store()

        model = self.db._get(TestModel1, model.id)
        self.assertIsNone(model['field_one'])

    def test_deleted_attribute_has_default_after_load(self):
        model = TestModel1()
        del model['field_one']
        model.add(self.db)
        model.load()
        self.assertEqual(model.get('field_one'), 0)

    def test_deleted_attribute_has_default_when_fetching(self):
        model = TestModel1()
        del model['field_one']
        model.add(self.db)

        model = self.db._get(TestModel1, model.id)
        self.assertEqual(model.get('field_one'), 0)

    def test_flex_default(self):
        model = TestModel1()
        model['some_float_field'] = 1
        del model['some_float_field']
        self.assertEqual(model.get('some_float_field'), 0.0)


class FormattedMappingTest(unittest.TestCase):

    def test_keys_equal_model_keys(self):
        model = TestModel1()
        formatted = model.formatted()
        self.assertEqual(set(model.keys(True)), set(formatted.keys()))

    def test_unset_flex_with_string_default(self):
        model = TestModel1()
        formatted = model.formatted()
        self.assertEqual(formatted['flex_field'], u'')
        self.assertEqual(formatted.get('flex_field'), u'')

    def test_unset_flex_with_custom_default(self):
        model = TestModel1()
        formatted = model.formatted()
        self.assertEqual(formatted.get('flex_field', 'default'), 'default')

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


class ParseTest(unittest.TestCase):
    def test_parse_fixed_field(self):
        model = TestModel1()
        model.set('field_one', u'2')
        self.assertIsInstance(model['field_one'], int)
        self.assertEqual(model['field_one'], 2)

    def test_parse_flex_field(self):
        model = TestModel1()
        model.set('some_float_field', u'2')
        self.assertIsInstance(model['some_float_field'], float)
        self.assertEqual(model['some_float_field'], 2.0)

    def test_parse_untyped_field(self):
        model = TestModel1()
        model.set('unknown_flex', u'2')
        self.assertEqual(model['unknown_flex'], u'2')


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


class SortFromStringsTest(unittest.TestCase):
    def sfs(self, strings):
        return dbcore.queryparse.sort_from_strings(
            TestModel1,
            strings,
        )

    def test_zero_parts(self):
        s = self.sfs([])
        self.assertIsNone(s)

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
        self.assertIsInstance(s.sorts[0], dbcore.query.FlexFieldSort)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
