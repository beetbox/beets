from __future__ import annotations

import os
import re
import shlex
import time

import beets
import beets.ui
from beets import dbcore, logging, plugins, util
from beets.dbcore import types
from beets.util import bytestring_path, normpath, syspath

log = logging.getLogger("beets")


# Special path format key.
PF_KEY_DEFAULT = "default"


class SingletonQuery(dbcore.FieldQuery[str]):
    """This query is responsible for the 'singleton' lookup.

    It is based on the FieldQuery and constructs a SQL clause
    'album_id is NULL' which yields the same result as the previous filter
    in Python but is more performant since it's done in SQL.

    Using util.str2bool ensures that lookups like singleton:true, singleton:1
    and singleton:false, singleton:0 are handled consistently.
    """

    def __new__(cls, field: str, value: str, *args, **kwargs):
        query = dbcore.query.NoneQuery("album_id")
        if util.str2bool(value):
            return query
        return dbcore.query.NotQuery(query)


class PathQuery(dbcore.FieldQuery[bytes]):
    """A query that matches all items under a given path.

    Matching can either be case-insensitive or case-sensitive. By
    default, the behavior depends on the OS: case-insensitive on Windows
    and case-sensitive otherwise.
    """

    # For tests
    force_implicit_query_detection = False

    def __init__(self, field, pattern, fast=True, case_sensitive=None):
        """Create a path query.

        `pattern` must be a path, either to a file or a directory.

        `case_sensitive` can be a bool or `None`, indicating that the
        behavior should depend on the filesystem.
        """
        super().__init__(field, pattern, fast)

        path = util.normpath(pattern)

        # By default, the case sensitivity depends on the filesystem
        # that the query path is located on.
        if case_sensitive is None:
            case_sensitive = util.case_sensitive(path)
        self.case_sensitive = case_sensitive

        # Use a normalized-case pattern for case-insensitive matches.
        if not case_sensitive:
            # We need to lowercase the entire path, not just the pattern.
            # In particular, on Windows, the drive letter is otherwise not
            # lowercased.
            # This also ensures that the `match()` method below and the SQL
            # from `col_clause()` do the same thing.
            path = path.lower()

        # Match the path as a single file.
        self.file_path = path
        # As a directory (prefix).
        self.dir_path = os.path.join(path, b"")

    @classmethod
    def is_path_query(cls, query_part):
        """Try to guess whether a unicode query part is a path query.

        Condition: separator precedes colon and the file exists.
        """
        colon = query_part.find(":")
        if colon != -1:
            query_part = query_part[:colon]

        # Test both `sep` and `altsep` (i.e., both slash and backslash on
        # Windows).
        if not (
            os.sep in query_part or (os.altsep and os.altsep in query_part)
        ):
            return False

        if cls.force_implicit_query_detection:
            return True
        return os.path.exists(syspath(normpath(query_part)))

    def match(self, item):
        path = item.path if self.case_sensitive else item.path.lower()
        return (path == self.file_path) or path.startswith(self.dir_path)

    def col_clause(self):
        file_blob = BLOB_TYPE(self.file_path)
        dir_blob = BLOB_TYPE(self.dir_path)

        if self.case_sensitive:
            query_part = "({0} = ?) || (substr({0}, 1, ?) = ?)"
        else:
            query_part = "(BYTELOWER({0}) = BYTELOWER(?)) || \
                         (substr(BYTELOWER({0}), 1, ?) = BYTELOWER(?))"

        return query_part.format(self.field), (
            file_blob,
            len(dir_blob),
            dir_blob,
        )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}({self.field!r}, {self.pattern!r}, "
            f"fast={self.fast}, case_sensitive={self.case_sensitive})"
        )


class PathType(types.Type[bytes, bytes]):
    """A dbcore type for filesystem paths.

    These are represented as `bytes` objects, in keeping with
    the Unix filesystem abstraction.
    """

    sql = "BLOB"
    query = PathQuery
    model_type = bytes

    def __init__(self, nullable=False):
        """Create a path type object.

        `nullable` controls whether the type may be missing, i.e., None.
        """
        self.nullable = nullable

    @property
    def null(self):
        if self.nullable:
            return None
        else:
            return b""

    def format(self, value):
        return util.displayable_path(value)

    def parse(self, string):
        return normpath(bytestring_path(string))

    def normalize(self, value):
        if isinstance(value, str):
            # Paths stored internally as encoded bytes.
            return bytestring_path(value)

        elif isinstance(value, BLOB_TYPE):
            # We unwrap buffers to bytes.
            return bytes(value)

        else:
            return value

    def from_sql(self, sql_value):
        return self.normalize(sql_value)

    def to_sql(self, value):
        if isinstance(value, bytes):
            value = BLOB_TYPE(value)
        return value


# To use the SQLite "blob" type, it doesn't suffice to provide a byte
# string; SQLite treats that as encoded text. Wrapping it in a
# `memoryview` tells it that we actually mean non-text data.
BLOB_TYPE = memoryview


class DateType(types.Float):
    # TODO representation should be `datetime` object
    # TODO distinguish between date and time types
    query = dbcore.query.DateQuery

    def format(self, value):
        return time.strftime(
            beets.config["time_format"].as_str(), time.localtime(value or 0)
        )

    def parse(self, string):
        try:
            # Try a formatted date string.
            return time.mktime(
                time.strptime(string, beets.config["time_format"].as_str())
            )
        except ValueError:
            # Fall back to a plain timestamp number.
            try:
                return float(string)
            except ValueError:
                return self.null


class MusicalKey(types.String):
    """String representing the musical key of a song.

    The standard format is C, Cm, C#, C#m, etc.
    """

    ENHARMONIC = {
        r"db": "c#",
        r"eb": "d#",
        r"gb": "f#",
        r"ab": "g#",
        r"bb": "a#",
    }

    null = None

    def parse(self, key):
        key = key.lower()
        for flat, sharp in self.ENHARMONIC.items():
            key = re.sub(flat, sharp, key)
        key = re.sub(r"[\W\s]+minor", "m", key)
        key = re.sub(r"[\W\s]+major", "", key)
        return key.capitalize()

    def normalize(self, key):
        if key is None:
            return None
        else:
            return self.parse(key)


class DurationType(types.Float):
    """Human-friendly (M:SS) representation of a time interval."""

    query = dbcore.query.DurationQuery

    def format(self, value):
        if not beets.config["format_raw_length"].get(bool):
            return beets.ui.human_seconds_short(value or 0.0)
        else:
            return value

    def parse(self, string):
        try:
            # Try to format back hh:ss to seconds.
            return util.raw_seconds_short(string)
        except ValueError:
            # Fall back to a plain float.
            try:
                return float(string)
            except ValueError:
                return self.null


# ------------------------------ Utils functions ----------------------------- #


def parse_query_parts(parts, model_cls):
    """Given a beets query string as a list of components, return the
    `Query` and `Sort` they represent.

    Like `dbcore.parse_sorted_query`, with beets query prefixes and
    ensuring that implicit path queries are made explicit with 'path::<query>'
    """
    # Get query types and their prefix characters.
    prefixes = {
        ":": dbcore.query.RegexpQuery,
        "=~": dbcore.query.StringQuery,
        "=": dbcore.query.MatchQuery,
    }
    prefixes.update(plugins.queries())

    # Special-case path-like queries, which are non-field queries
    # containing path separators (/).
    parts = [f"path:{s}" if PathQuery.is_path_query(s) else s for s in parts]

    case_insensitive = beets.config["sort_case_insensitive"].get(bool)

    query, sort = dbcore.parse_sorted_query(
        model_cls, parts, prefixes, case_insensitive
    )
    log.debug("Parsed query: {!r}", query)
    log.debug("Parsed sort: {!r}", sort)
    return query, sort


def parse_query_string(s, model_cls):
    """Given a beets query string, return the `Query` and `Sort` they
    represent.

    The string is split into components using shell-like syntax.
    """
    message = f"Query is not unicode: {s!r}"
    assert isinstance(s, str), message
    try:
        parts = shlex.split(s)
    except ValueError as exc:
        raise dbcore.InvalidQueryError(s, exc)
    return parse_query_parts(parts, model_cls)
