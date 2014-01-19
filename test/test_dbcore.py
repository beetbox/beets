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

"""Tests for non-query database functions of Item.
"""
import os
import sqlite3

import _common
from beets import dbcore


# Fixture: concrete database and model classes. For migration tests, we
# have multiple models with different numbers of fields.

class TestModel1(dbcore.Model):
    _table = 'test'
    _flex_table = 'testflex'
    _fields = {
        'field_one': dbcore.Type(int, 'INTEGER'),
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
        'field_one': dbcore.Type(int, 'INTEGER'),
        'field_two': dbcore.Type(int, 'INTEGER'),
    }

class TestDatabase2(dbcore.Database):
    _models = (TestModel2,)
    pass

class TestModel3(TestModel1):
    _fields = {
        'field_one': dbcore.Type(int, 'INTEGER'),
        'field_two': dbcore.Type(int, 'INTEGER'),
        'field_three': dbcore.Type(int, 'INTEGER'),
    }

class TestDatabase3(dbcore.Database):
    _models = (TestModel3,)
    pass

class TestModel4(TestModel1):
    _fields = {
        'field_one': dbcore.Type(int, 'INTEGER'),
        'field_two': dbcore.Type(int, 'INTEGER'),
        'field_three': dbcore.Type(int, 'INTEGER'),
        'field_four': dbcore.Type(int, 'INTEGER'),
    }

class TestDatabase4(dbcore.Database):
    _models = (TestModel4,)
    pass

class AnotherTestModel(TestModel1):
    _table = 'another'
    _flex_table = 'anotherflex'
    _fields = {
        'foo': dbcore.Type(int, 'INTEGER'),
    }

class TestDatabaseTwoModels(dbcore.Database):
    _models = (TestModel2, AnotherTestModel)
    pass



TEMP_LIB = os.path.join(_common.RSRC, 'test_copy.blb')
class MigrationTest(_common.TestCase):
    """Tests the ability to change the database schema between
    versions.
    """
    def setUp(self):
        super(MigrationTest, self).setUp()

        # Set up a database with the two-field schema.
        self.libfile = os.path.join(_common.RSRC, 'temp.db')
        old_lib = TestDatabase2(self.libfile)

        # Add an item to the old library.
        old_lib._connection().execute(
            'insert into test (field_one, field_two) values (4, 2)'
        )
        old_lib._connection().commit()
        del old_lib

    def tearDown(self):
        super(MigrationTest, self).tearDown()
        os.unlink(self.libfile)

    def test_open_with_same_fields_leaves_untouched(self):
        new_lib = TestDatabase2(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        self.assertEqual(len(row.keys()), 2)

    def test_open_with_new_field_adds_column(self):
        new_lib = TestDatabase3(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        self.assertEqual(len(row.keys()), 3)

    def test_open_with_fewer_fields_leaves_untouched(self):
        new_lib = TestDatabase1(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        self.assertEqual(len(row.keys()), 2)

    def test_open_with_multiple_new_fields(self):
        new_lib = TestDatabase4(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        self.assertEqual(len(row.keys()), 4)

    def test_extra_model_adds_table(self):
        new_lib = TestDatabaseTwoModels(self.libfile)
        try:
            new_lib._connection().execute("select * from another")
        except sqlite3.OperationalError:
            self.fail("select failed")
