import warnings
from importlib import import_module

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
    if name in NEW_MODULE_BY_NAME:
        new_module = NEW_MODULE_BY_NAME[name]
        warnings.warn(
            (
                f"'beets.library.{name}' import is deprecated and will be removed"
                f"in v3.0.0; import '{new_module}.{name}' instead."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(import_module(new_module), name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


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
