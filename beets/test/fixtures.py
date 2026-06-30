"""Provide lightweight dbcore model fixtures for tests.

These fixtures supply predictable query, sort, and model behavior for tests that
exercise metadata registration and model integration.
"""

from typing import ClassVar

from beets.dbcore import sort, types
from beets.dbcore.db import FormattedMapping, Index
from beets.library import LibModel
from beets.util import cached_classproperty
from beets.util.artresizer import IMBackend


class SortFixture(sort.FieldSort):
    pass


class ModelFixture1(LibModel):
    _table = "test"
    _flex_table = "testflex"
    _fields: ClassVar[dict[str, types.Type]] = {
        "id": types.PRIMARY_ID,
        "field_one": types.INTEGER,
        "field_two": types.STRING,
    }

    _sorts: ClassVar[dict[str, type[sort.FieldSort]]] = {
        "some_sort": SortFixture
    }
    _indices = (Index("field_one_index", ("field_one",)),)
    _formatter = FormattedMapping

    @cached_classproperty
    def _types(cls):
        return {"some_float_field": types.FLOAT}

    @classmethod
    def _getters(cls):
        return {}


class DummyIMBackend(IMBackend):
    """An `IMBackend` which pretends that ImageMagick is available.

    The version is sufficiently recent to support image comparison.
    """

    def __init__(self):
        """Init a dummy backend class for mocked ImageMagick tests."""
        self.version = (7, 0, 0)
        self.legacy = False
        self.convert_cmd = ["magick"]
        self.identify_cmd = ["magick", "identify"]
        self.compare_cmd = ["magick", "compare"]
