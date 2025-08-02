"""Tests for the DBCore database abstraction."""

import os
import shutil
import sqlite3
import unittest
from tempfile import mkstemp
from typing import ClassVar

import pytest

from beets import dbcore
from beets.dbcore import query, sort, types
from beets.dbcore.db import DBCustomFunctionError, Index
from beets.library import Album, Item
from beets.test.fixtures import ModelFixture1

# Fixture: concrete database and model classes. For migration tests, we
# have multiple models with different numbers of fields.


@pytest.fixture
def db(model):
    db = model(":memory:")
    yield db
    db._connection().close()


class DatabaseFixture1(dbcore.Database):
    _models = (ModelFixture1,)


class ModelFixture2(ModelFixture1):
    _fields: ClassVar[dict[str, dbcore.types.Type]] = {
        "id": dbcore.types.PRIMARY_ID,
        "field_one": dbcore.types.INTEGER,
        "field_two": dbcore.types.INTEGER,
    }


class DatabaseFixture2(dbcore.Database):
    _models = (ModelFixture2,)


class ModelFixture3(ModelFixture1):
    _fields: ClassVar[dict[str, dbcore.types.Type]] = {
        "id": dbcore.types.PRIMARY_ID,
        "field_one": dbcore.types.INTEGER,
        "field_two": dbcore.types.INTEGER,
        "field_three": dbcore.types.INTEGER,
    }


class DatabaseFixture3(dbcore.Database):
    _models = (ModelFixture3,)


class ModelFixture4(ModelFixture1):
    _fields: ClassVar[dict[str, dbcore.types.Type]] = {
        "id": dbcore.types.PRIMARY_ID,
        "field_one": dbcore.types.INTEGER,
        "field_two": dbcore.types.INTEGER,
        "field_three": dbcore.types.INTEGER,
        "field_four": dbcore.types.INTEGER,
    }


class DatabaseFixture4(dbcore.Database):
    _models = (ModelFixture4,)


class AnotherModelFixture(ModelFixture1):
    _table = "another"
    _flex_table = "anotherflex"
    _fields: ClassVar[dict[str, dbcore.types.Type]] = {
        "id": dbcore.types.PRIMARY_ID,
        "foo": dbcore.types.INTEGER,
    }
    _indices = (Index("another_foo_index", ("foo",)),)


class ModelFixture5(ModelFixture1):
    _fields: ClassVar[dict[str, dbcore.types.Type]] = {
        "some_string_field": dbcore.types.STRING,
        "some_float_field": dbcore.types.FLOAT,
        "some_boolean_field": dbcore.types.BOOLEAN,
    }


class DatabaseFixtureTwoModels(dbcore.Database):
    _models = (ModelFixture2, AnotherModelFixture)


class ModelFixtureWithGetters(dbcore.Model):
    @classmethod
    def _getters(cls):
        return {"aComputedField": (lambda s: "thing")}

    def _template_funcs(self):
        return {}


class MigrationTest(unittest.TestCase):
    """Tests the ability to change the database schema between
    versions.
    """

    @classmethod
    def setUpClass(cls):
        handle, cls.orig_libfile = mkstemp("orig_db")
        os.close(handle)
        # Set up a database with the two-field schema.
        old_lib = DatabaseFixture2(cls.orig_libfile)

        # Add an item to the old library.
        old_lib._connection().execute(
            "insert into test (field_one, field_two) values (4, 2)"
        )
        old_lib._connection().commit()
        old_lib._connection().close()
        del old_lib

    @classmethod
    def tearDownClass(cls):
        os.remove(cls.orig_libfile)

    def setUp(self):
        handle, self.libfile = mkstemp("db")
        os.close(handle)
        shutil.copyfile(self.orig_libfile, self.libfile)

    def tearDown(self):
        os.remove(self.libfile)

    def test_open_with_same_fields_leaves_untouched(self):
        new_lib = DatabaseFixture2(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        c.connection.close()
        assert len(row.keys()) == len(ModelFixture2._fields)

    def test_open_with_new_field_adds_column(self):
        new_lib = DatabaseFixture3(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        c.connection.close()
        assert len(row.keys()) == len(ModelFixture3._fields)

    def test_open_with_fewer_fields_leaves_untouched(self):
        new_lib = DatabaseFixture1(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        c.connection.close()
        assert len(row.keys()) == len(ModelFixture2._fields)

    def test_open_with_multiple_new_fields(self):
        new_lib = DatabaseFixture4(self.libfile)
        c = new_lib._connection().cursor()
        c.execute("select * from test")
        row = c.fetchone()
        c.connection.close()
        assert len(row.keys()) == len(ModelFixture4._fields)

    def test_extra_model_adds_table(self):
        new_lib = DatabaseFixtureTwoModels(self.libfile)
        try:
            c = new_lib._connection()
            c.execute("select * from another")
            c.close()
        except sqlite3.OperationalError:
            self.fail("select failed")

    def test_index_creation(self):
        """Test that declared indices are created on database initialization."""
        db = DatabaseFixture1(":memory:")
        with db.transaction() as tx:
            rows = tx.query("PRAGMA index_info(field_one_index)")
            assert len(rows) > 0  # Index exists
        db._connection().close()


class TransactionTest(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseFixture1(":memory:")

    def tearDown(self):
        self.db._connection().close()

    def test_mutate_increase_revision(self):
        old_rev = self.db.revision
        with self.db.transaction() as tx:
            tx.mutate(
                f"INSERT INTO {ModelFixture1._table} (field_one) VALUES (?);",
                (111,),
            )
        assert self.db.revision > old_rev

    def test_query_no_increase_revision(self):
        old_rev = self.db.revision
        with self.db.transaction() as tx:
            tx.query(f"PRAGMA table_info({ModelFixture1._table})")
        assert self.db.revision == old_rev


class ModelTest(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseFixture1(":memory:")

    def tearDown(self):
        self.db._connection().close()

    def test_add_model(self):
        model = ModelFixture1()
        model.add(self.db)
        rows = self.db._connection().execute("select * from test").fetchall()
        assert len(rows) == 1

    def test_store_fixed_field(self):
        model = ModelFixture1()
        model.add(self.db)
        model.field_one = 123
        model.store()
        row = self.db._connection().execute("select * from test").fetchone()
        assert row["field_one"] == 123

    def test_revision(self):
        old_rev = self.db.revision
        model = ModelFixture1()
        model.add(self.db)
        model.store()
        assert model._revision == self.db.revision
        assert self.db.revision > old_rev

        mid_rev = self.db.revision
        model2 = ModelFixture1()
        model2.add(self.db)
        model2.store()
        assert model2._revision > mid_rev
        assert self.db.revision > model._revision

        # revision changed, so the model should be re-loaded
        model.load()
        assert model._revision == self.db.revision

        # revision did not change, so no reload
        mod2_old_rev = model2._revision
        model2.load()
        assert model2._revision == mod2_old_rev

    def test_retrieve_by_id(self):
        model = ModelFixture1()
        model.add(self.db)
        other_model = self.db._get(ModelFixture1, model.id)
        assert model.id == other_model.id

    def test_store_and_retrieve_flexattr(self):
        model = ModelFixture1()
        model.add(self.db)
        model.foo = "bar"
        model.store()

        other_model = self.db._get(ModelFixture1, model.id)
        assert other_model.foo == "bar"

    def test_delete_flexattr(self):
        model = ModelFixture1()
        model["foo"] = "bar"
        assert "foo" in model
        del model["foo"]
        assert "foo" not in model

    def test_delete_flexattr_via_dot(self):
        model = ModelFixture1()
        model["foo"] = "bar"
        assert "foo" in model
        del model.foo
        assert "foo" not in model

    def test_delete_flexattr_persists(self):
        model = ModelFixture1()
        model.add(self.db)
        model.foo = "bar"
        model.store()

        model = self.db._get(ModelFixture1, model.id)
        del model["foo"]
        model.store()

        model = self.db._get(ModelFixture1, model.id)
        assert "foo" not in model

    def test_delete_non_existent_attribute(self):
        model = ModelFixture1()
        with pytest.raises(KeyError):
            del model["foo"]

    def test_delete_fixed_attribute(self):
        model = ModelFixture5()
        model.some_string_field = "foo"
        model.some_float_field = 1.23
        model.some_boolean_field = True

        for field, type_ in model._fields.items():
            assert model[field] != type_.null

        for field, type_ in model._fields.items():
            del model[field]
            assert model[field] == type_.null

    def test_null_value_normalization_by_type(self):
        model = ModelFixture1()
        model.field_one = None
        assert model.field_one == 0

    def test_null_value_stays_none_for_untyped_field(self):
        model = ModelFixture1()
        model.foo = None
        assert model.foo is None

    def test_normalization_for_typed_flex_fields(self):
        model = ModelFixture1()
        model.some_float_field = None
        assert model.some_float_field == 0.0

    def test_load_deleted_flex_field(self):
        model1 = ModelFixture1()
        model1["flex_field"] = True
        model1.add(self.db)

        model2 = self.db._get(ModelFixture1, model1.id)
        assert "flex_field" in model2

        del model1["flex_field"]
        model1.store()

        model2.load()
        assert "flex_field" not in model2

    def test_check_db_fails(self):
        with pytest.raises(ValueError, match="no database"):
            dbcore.Model()._check_db()
        with pytest.raises(ValueError, match="no id"):
            ModelFixture1(self.db)._check_db()

        dbcore.Model(self.db)._check_db(need_id=False)

    def test_missing_field(self):
        with pytest.raises(AttributeError):
            ModelFixture1(self.db).nonExistingKey

    def test_computed_field(self):
        model = ModelFixtureWithGetters()
        assert model.aComputedField == "thing"
        with pytest.raises(KeyError, match=r"computed field .+ deleted"):
            del model.aComputedField

    def test_items(self):
        model = ModelFixture1(self.db)
        model.id = 5
        assert {("id", 5), ("field_one", 0), ("field_two", "")} == set(
            model.items()
        )

    def test_delete_internal_field(self):
        model = dbcore.Model()
        del model._db
        with pytest.raises(AttributeError):
            model._db

    def test_parse_nonstring(self):
        with pytest.raises(TypeError, match="must be a string"):
            dbcore.Model._parse(None, 42)

    def test_pickle_dump(self):
        """Tries to pickle an item. This tests the __getstate__ method
        of the Model ABC"""
        import pickle

        model = ModelFixture1(self.db)
        model.add(self.db)
        model.field_one = 123

        model.store()
        assert model._db is not None

        pickle.dumps(model)


class FormatTest(unittest.TestCase):
    def test_format_fixed_field_integer(self):
        model = ModelFixture1()
        model.field_one = 155
        value = model.formatted().get("field_one")
        assert value == "155"

    def test_format_fixed_field_integer_normalized(self):
        """The normalize method of the Integer class rounds floats"""
        model = ModelFixture1()
        model.field_one = 142.432
        value = model.formatted().get("field_one")
        assert value == "142"

        model.field_one = 142.863
        value = model.formatted().get("field_one")
        assert value == "143"

    def test_format_fixed_field_string(self):
        model = ModelFixture1()
        model.field_two = "caf\xe9"
        value = model.formatted().get("field_two")
        assert value == "caf\xe9"

    def test_format_flex_field(self):
        model = ModelFixture1()
        model.other_field = "caf\xe9"
        value = model.formatted().get("other_field")
        assert value == "caf\xe9"

    def test_format_flex_field_bytes(self):
        model = ModelFixture1()
        model.other_field = "caf\xe9".encode()
        value = model.formatted().get("other_field")
        assert isinstance(value, str)
        assert value == "caf\xe9"

    def test_format_unset_field(self):
        model = ModelFixture1()
        value = model.formatted().get("other_field")
        assert value == ""

    def test_format_typed_flex_field(self):
        model = ModelFixture1()
        model.some_float_field = 3.14159265358979
        value = model.formatted().get("some_float_field")
        assert value == "3.1"


class FormattedMappingTest(unittest.TestCase):
    def test_keys_equal_model_keys(self):
        model = ModelFixture1()
        formatted = model.formatted()
        assert set(model.keys(True)) == set(formatted.keys())

    def test_get_unset_field(self):
        model = ModelFixture1()
        formatted = model.formatted()
        with pytest.raises(KeyError):
            formatted["other_field"]

    def test_get_method_with_default(self):
        model = ModelFixture1()
        formatted = model.formatted()
        assert formatted.get("other_field") == ""

    def test_get_method_with_specified_default(self):
        model = ModelFixture1()
        formatted = model.formatted()
        assert formatted.get("other_field", "default") == "default"


class ParseTest(unittest.TestCase):
    def test_parse_fixed_field(self):
        value = ModelFixture1._parse("field_one", "2")
        assert isinstance(value, int)
        assert value == 2

    def test_parse_flex_field(self):
        value = ModelFixture1._parse("some_float_field", "2")
        assert isinstance(value, float)
        assert value == 2.0

    def test_parse_untyped_field(self):
        value = ModelFixture1._parse("field_nine", "2")
        assert value == "2"


class TestModelTypeFallback:
    def test_album_type_falls_back_to_item_type(self):
        typ = Album._type("artists")
        assert isinstance(typ, types.DelimitedString)
        assert typ is types.MULTI_VALUE_DSV

    def test_album_type_falls_back_to_item_type_other_list_fields(self):
        for field in ["genres", "composers", "artists_sort"]:
            typ = Album._type(field)
            assert isinstance(typ, types.DelimitedString), field

    def test_item_type_does_not_change(self):
        typ = Item._type("artists")
        assert isinstance(typ, types.DelimitedString)

    def test_unknown_key_falls_through_to_default(self):
        typ = Album._type("nonexistent_field_xyz")
        assert isinstance(typ, types.Default)


class ResultsIteratorTest(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseFixture1(":memory:")
        model = ModelFixture1()
        model["foo"] = "baz"
        model.add(self.db)
        model = ModelFixture1()
        model["foo"] = "bar"
        model.add(self.db)

    def tearDown(self):
        self.db._connection().close()

    def test_iterate_once(self):
        objs = self.db.get_results(ModelFixture1)
        assert len(list(objs)) == 2

    def test_iterate_twice(self):
        objs = self.db.get_results(ModelFixture1)
        list(objs)
        assert len(list(objs)) == 2

    def test_concurrent_iterators(self):
        results = self.db.get_results(ModelFixture1)
        it1 = iter(results)
        it2 = iter(results)
        next(it1)
        list(it2)
        assert len(list(it1)) == 1

    def test_slow_query(self):
        q = query.SubstringQuery("foo", "ba", False)
        objs = self.db.get_results(ModelFixture1, q)
        assert len(list(objs)) == 2

    def test_slow_query_negative(self):
        q = query.SubstringQuery("foo", "qux", False)
        objs = self.db.get_results(ModelFixture1, q)
        assert len(list(objs)) == 0

    def test_iterate_slow_sort(self):
        s = sort.SlowFieldSort("foo")
        res = self.db.get_results(ModelFixture1, sort=s)
        objs = list(res)
        assert objs[0].foo == "bar"
        assert objs[1].foo == "baz"

    def test_unsorted_subscript(self):
        objs = self.db.get_results(ModelFixture1)
        assert objs[0].foo == "baz"
        assert objs[1].foo == "bar"

    def test_slow_sort_subscript(self):
        s = sort.SlowFieldSort("foo")
        objs = self.db.get_results(ModelFixture1, sort=s)
        assert objs[0].foo == "bar"
        assert objs[1].foo == "baz"

    def test_length(self):
        objs = self.db.get_results(ModelFixture1)
        assert len(objs) == 2

    def test_out_of_range(self):
        objs = self.db.get_results(ModelFixture1)
        with pytest.raises(IndexError):
            objs[100]

    def test_no_results(self):
        assert (
            self.db.get_results(ModelFixture1, query.FalseQuery()).get() is None
        )


class TestException:
    @pytest.mark.parametrize("model", [DatabaseFixture1])
    @pytest.mark.filterwarnings(
        "ignore: .*plz_raise.*: pytest.PytestUnraisableExceptionWarning"
    )
    @pytest.mark.filterwarnings(
        "error: .*: pytest.PytestUnraisableExceptionWarning"
    )
    def test_custom_function_error(self, db: DatabaseFixture1):
        def plz_raise():
            raise Exception("i haz raized")

        db._connection().create_function("plz_raise", 0, plz_raise)

        with db.transaction() as tx:
            tx.mutate("insert into test (field_one) values (1)")

        with pytest.raises(DBCustomFunctionError):
            with db.transaction() as tx:
                tx.query("select * from test where plz_raise()")
