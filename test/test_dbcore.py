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

ID_TYPE = dbcore.Type('INTEGER PRIMARY KEY', dbcore.query.NumericQuery,
                      unicode)
INT_TYPE = dbcore.Type('INTEGER', dbcore.query.NumericQuery,
                       unicode)

class TestModel1(dbcore.Model):
    _table = 'test'
    _flex_table = 'testflex'
    _fields = {
        'id': ID_TYPE,
        'field_one': INT_TYPE,
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
        'id': ID_TYPE,
        'field_one': INT_TYPE,
        'field_two': INT_TYPE,
    }

class TestDatabase2(dbcore.Database):
    _models = (TestModel2,)
    pass

class TestModel3(TestModel1):
    _fields = {
        'id': ID_TYPE,
        'field_one': INT_TYPE,
        'field_two': INT_TYPE,
        'field_three': INT_TYPE,
    }

class TestDatabase3(dbcore.Database):
    _models = (TestModel3,)
    pass

class TestModel4(TestModel1):
    _fields = {
        'id': ID_TYPE,
        'field_one': INT_TYPE,
        'field_two': INT_TYPE,
        'field_three': INT_TYPE,
        'field_four': INT_TYPE,
    }

class TestDatabase4(dbcore.Database):
    _models = (TestModel4,)
    pass

class AnotherTestModel(TestModel1):
    _table = 'another'
    _flex_table = 'anotherflex'
    _fields = {
        'id': ID_TYPE,
        'foo': INT_TYPE,
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

def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
