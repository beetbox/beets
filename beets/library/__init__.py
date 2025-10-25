from beets.util.deprecation import deprecate_imports

from .exceptions import FileOperationError, ReadError, WriteError
from .library import Library
from .models import Album, Item, LibModel
from .queries import parse_query_parts, parse_query_string

NEW_MODULE_BY_NAME = dict.fromkeys(
    ("DateType", "DurationType", "MusicalKey", "PathType"), "beets.dbcore.types"
) | dict.fromkeys(
    ("BLOB_TYPE", "SingletonQuery", "PathQuery"), "beets.dbcore.query"
)


def __getattr__(name: str):
    return deprecate_imports(__name__, NEW_MODULE_BY_NAME, name)


__all__ = [
    "Library",
    "LibModel",
    "Album",
    "Item",
    "parse_query_parts",
    "parse_query_string",
    "FileOperationError",
    "ReadError",
    "WriteError",
]
