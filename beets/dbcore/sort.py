"""Module for representing sorting criteria for database queries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import beets
from beets.util import cached_classproperty

if TYPE_CHECKING:
    from collections.abc import Sequence

    from beets.dbcore.db import AnyModel, Model


class Sort:
    """An abstract class representing a sort operation for a query into
    the database.
    """

    def order_clause(self) -> str | None:
        """Generates a SQL fragment to be used in a ORDER BY clause, or
        None if no fragment is used (i.e., this is a slow sort).
        """
        return None

    def sort(self, items: list[AnyModel]) -> list[AnyModel]:
        """Sort the list of objects and return a list."""
        return sorted(items)

    def is_slow(self) -> bool:
        """Indicate whether this query is *slow*, meaning that it cannot
        be executed in SQL and must be executed in Python.
        """
        return False

    def __hash__(self) -> int:
        return 0

    def __eq__(self, other) -> bool:
        return type(self) is type(other)

    def __repr__(self):
        return f"{self.__class__.__name__}()"


class MultipleSort(Sort):
    """Sort that encapsulates multiple sub-sorts."""

    def __init__(self, sorts: Sequence[Sort] | None = None):
        self.sorts = list(sorts or [])

    def add_sort(self, sort: Sort):
        self.sorts.append(sort)

    def order_clause(self) -> str:
        """Return the list SQL clauses for those sub-sorts for which we can be
        (at least partially) fast.

        A contiguous suffix of fast (SQL-capable) sub-sorts are
        executable in SQL. The remaining, even if they are fast
        independently, must be executed slowly.
        """
        order_strings = []
        for sort in reversed(self.sorts):
            clause = sort.order_clause()
            if clause is None:
                break
            order_strings.append(clause)
        order_strings.reverse()

        return ", ".join(order_strings)

    def is_slow(self) -> bool:
        for sort in self.sorts:
            if sort.is_slow():
                return True
        return False

    def sort(self, items):
        slow_sorts = []
        switch_slow = False
        for sort in reversed(self.sorts):
            if switch_slow:
                slow_sorts.append(sort)
            elif sort.order_clause() is None:
                switch_slow = True
                slow_sorts.append(sort)
            else:
                pass

        for sort in slow_sorts:
            items = sort.sort(items)
        return items

    def __repr__(self):
        return f"{self.__class__.__name__}({self.sorts!r})"

    def __hash__(self):
        return hash(tuple(self.sorts))

    def __eq__(self, other):
        return super().__eq__(other) and self.sorts == other.sorts


class FieldSort(Sort):
    """An abstract sort criterion that orders by a specific field (of
    any kind).
    """

    def __init__(self, field: str, ascending: bool = True):
        self.field = field
        self.ascending = ascending

    @cached_classproperty
    def case_insensitive(cls) -> bool:
        return beets.config["sort_case_insensitive"].get(bool)

    def sort(self, objs: list[AnyModel]) -> list[AnyModel]:
        # TODO: Conversion and null-detection here. In Python 3,
        # comparisons with None fail. We should also support flexible
        # attributes with different types without falling over.

        def key(obj: Model) -> Any:
            field_val = obj.get(self.field, None)
            if field_val is None:
                if _type := obj._types.get(self.field):
                    # If the field is typed, use its null value.
                    field_val = obj._types[self.field].null
                else:
                    # If not, fall back to using an empty string.
                    field_val = ""
            if self.case_insensitive and isinstance(field_val, str):
                field_val = field_val.lower()
            return field_val

        return sorted(objs, key=key, reverse=not self.ascending)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"({self.field!r}, ascending={self.ascending!r})"
        )

    def __hash__(self) -> int:
        return hash((self.field, self.ascending))

    def __eq__(self, other) -> bool:
        return (
            super().__eq__(other)
            and self.field == other.field
            and self.ascending == other.ascending
        )


class FixedFieldSort(FieldSort):
    """Sort object to sort on a fixed field."""

    def order_clause(self) -> str:
        order = "ASC" if self.ascending else "DESC"
        if self.case_insensitive:
            field = (
                "(CASE "
                f"WHEN TYPEOF({self.field})='text' THEN LOWER({self.field}) "
                f"WHEN TYPEOF({self.field})='blob' THEN LOWER({self.field}) "
                f"ELSE {self.field} END)"
            )
        else:
            field = self.field
        return f"{field} {order}"


class SlowFieldSort(FieldSort):
    """A sort criterion by some model field other than a fixed field:
    i.e., a computed or flexible field.
    """

    def is_slow(self) -> bool:
        return True


class NullSort(Sort):
    """No sorting. Leave results unsorted."""

    def sort(self, items: list[AnyModel]) -> list[AnyModel]:
        return items

    def __nonzero__(self) -> bool:
        return self.__bool__()

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other) -> bool:
        return type(self) is type(other) or other is None

    def __hash__(self) -> int:
        return 0


class SmartArtistSort(FieldSort):
    """Sort by artist (either album artist or track artist),
    prioritizing the sort field over the raw field.
    """

    def order_clause(self):
        order = "ASC" if self.ascending else "DESC"
        collate = "COLLATE NOCASE" if self.case_insensitive else ""
        field = self.field

        return f"COALESCE(NULLIF({field}_sort, ''), {field}) {collate} {order}"

    def sort(self, objs: list[AnyModel]) -> list[AnyModel]:
        def key(o):
            val = o[f"{self.field}_sort"] or o[self.field]
            return val.lower() if self.case_insensitive else val

        return sorted(objs, key=key, reverse=not self.ascending)
