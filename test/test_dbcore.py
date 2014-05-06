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

import _common
from _common import unittest
from beets import dbcore


# Fixture: concrete database and model classes. For migration tests, we
# have multiple models with different numbers of fields.

class TestModel1(dbcore.Model):
    _table = 'test'
    _flex_table = 'testflex'
    _fields = {
        'id': dbcore.types.Id(),
        'field_one': dbcore.types.Integer(),
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
        'id': dbcore.types.Id(),
        'field_one': dbcore.types.Integer(),
        'field_two': dbcore.types.Integer(),
    }


class TestDatabase2(dbcore.Database):
    _models = (TestModel2,)
    pass


class TestModel3(TestModel1):
    _fields = {
        'id': dbcore.types.Id(),
        'field_one': dbcore.types.Integer(),
        'field_two': dbcore.types.Integer(),
        'field_three': dbcore.types.Integer(),
    }


class TestDatabase3(dbcore.Database):
    _models = (TestModel3,)
    pass


class TestModel4(TestModel1):
    _fields = {
        'id': dbcore.types.Id(),
        'field_one': dbcore.types.Integer(),
        'field_two': dbcore.types.Integer(),
        'field_three': dbcore.types.Integer(),
        'field_four': dbcore.types.Integer(),
    }


class TestDatabase4(dbcore.Database):
    _models = (TestModel4,)
    pass


class AnotherTestModel(TestModel1):
    _table = 'another'
    _flex_table = 'anotherflex'
    _fields = {
        'id': dbcore.types.Id(),
        'foo': dbcore.types.Integer(),
    }


class TestDatabaseTwoModels(dbcore.Database):
    _models = (TestModel2, AnotherTestModel)
    pass


class MigrationTest(_common.TestCase):
    """Tests the ability to change the database schema between
    versions.
    """
    def setUp(self):
        super(MigrationTest, self).setUp()

        # Set up a database with the two-field schema.
        self.libfile = os.path.join(self.temp_dir, 'temp.db')
        old_lib = TestDatabase2(self.libfile)

        # Add an item to the old library.
        old_lib._connection().execute(
            'insert into test (field_one, field_two) values (4, 2)'
        )
        old_lib._connection().commit()
        del old_lib

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


class ModelTest(_common.TestCase):
    def setUp(self):
        super(ModelTest, self).setUp()
        dbfile = os.path.join(self.temp_dir, 'temp.db')
        self.db = TestDatabase1(dbfile)

    def tearDown(self):
        self.db._connection().close()
        super(ModelTest, self).tearDown()

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
        self.assertEqual(row['field_one'], 123)

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


class FormatTest(_common.TestCase):
    def test_format_fixed_field(self):
        model = TestModel1()
        model.field_one = u'caf\xe9'
        value = model._get_formatted('field_one')
        self.assertEqual(value, u'caf\xe9')

    def test_format_flex_field(self):
        model = TestModel1()
        model.other_field = u'caf\xe9'
        value = model._get_formatted('other_field')
        self.assertEqual(value, u'caf\xe9')

    def test_format_flex_field_bytes(self):
        model = TestModel1()
        model.other_field = u'caf\xe9'.encode('utf8')
        value = model._get_formatted('other_field')
        self.assertTrue(isinstance(value, unicode))
        self.assertEqual(value, u'caf\xe9')

    def test_format_unset_field(self):
        model = TestModel1()
        value = model._get_formatted('other_field')
        self.assertEqual(value, u'')


class FormattedMappingTest(_common.TestCase):
    def test_keys_equal_model_keys(self):
        model = TestModel1()
        formatted = model._formatted_mapping()
        self.assertEqual(set(model.keys(True)), set(formatted.keys()))

    def test_get_unset_field(self):
        model = TestModel1()
        formatted = model._formatted_mapping()
        with self.assertRaises(KeyError):
            formatted['other_field']


class ParseTest(_common.TestCase):
    def test_parse_fixed_field(self):
        value = TestModel1._parse('field_one', u'2')
        self.assertEqual(value, 2)

    def test_parse_untyped_field(self):
        value = TestModel1._parse('field_nine', u'2')
        self.assertEqual(value, u'2')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
