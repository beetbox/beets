"""Parsing of strings into DBCore queries."""

from __future__ import annotations

import operator
import re
import shlex
from dataclasses import dataclass
from functools import partial, reduce
from typing import TYPE_CHECKING, NamedTuple

from typing_extensions import Self

from beets import logging, plugins
from beets.util import cached_classproperty

from . import query, sort

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from beets.library.models import LibModel


PARSE_QUERY_PART_REGEX = re.compile(
    # Non-capturing optional segment for the keyword.
    r"(-|\^)?"  # Negation prefixes.
    r"(?:"
    r"(\S+?)"  # The field key.
    r"(?<!\\):"  # Unescaped :
    r")?"
    r"(.*)",  # The term itself.
    re.I,  # Case-insensitive.
)

log = logging.getLogger(__name__)
escape_commas = partial(re.compile(r"(?<=\S),(?=\S)").sub, r"\,")


@dataclass
class QueryTerm:
    """Represents a parsed query component with field, operator, and pattern.

    Encapsulates the structure of database query terms, handling negation,
    field-specific queries, and operator prefixes. Provides the foundation
    for converting user input into executable database queries.
    """

    negate: bool
    field: str | None
    prefix: str | None
    pattern: str

    @cached_classproperty
    def query_by_prefix(cls) -> query.QueryByField:
        """Map operator prefixes to their corresponding query class types."""
        return {
            ":": query.RegexpQuery,
            "=~": query.StringQuery,
            "=": query.MatchQuery,
            **plugins.queries(),
        }

    @cached_classproperty
    def prefix_query_regex(cls) -> re.Pattern[str]:
        """Compile regex pattern for parsing query syntax components."""
        return re.compile(
            rf"""
    (?P<negate>[-^])?   # Optional negation
    (                   # Optional field
        (?P<field>[^:]+?)
        (?<!\\):        # Needs to end with an unescaped colon
    )?
    (                   # Optional prefix
        (?<!\\)         # Not escaped
        (?P<prefix>{"|".join(map(re.escape, cls.query_by_prefix))})
    )?
    (?P<pattern>.*)     # The query term
        """,
            re.I + re.VERBOSE,
        )

    @classmethod
    def make(cls, part: str) -> QueryTerm:
        """Parse a query string into structured query term components."""
        if query.PathQuery.is_path_query(part):
            part = f"path:{part}"

        if m := cls.prefix_query_regex.match(part):
            data = m.groupdict()
            return cls(
                negate=bool(data["negate"]),
                field=data["field"],
                prefix=data["prefix"],
                pattern=data["pattern"].replace(r"\:", ":"),
            )

        raise query.InvalidQueryError(part, "Unrecognised query format")

    def get_query_cls(
        self, model_cls: type[LibModel]
    ) -> type[query.FieldQuery]:
        """Determine the most appropriate query class for filtering this field.

        Resolves query type by checking prefix-specific queries first, then
        field-specific queries, falling back to substring matching as default.
        """
        all_fields = model_cls._fields | model_cls._types
        model_queries = {
            **{k: v.query for k, v in all_fields.items()},
            **model_cls._queries,
        }
        return (
            self.query_by_prefix.get(self.prefix or "")
            or model_queries.get(self.field)  # type: ignore[arg-type]
            or query.SubstringQuery
        )

    def get_query(self, model_cls: type[LibModel]) -> query.Query:
        """Create an executable query object tailored to the target model."""
        out_query: query.Query
        if self.pattern:
            # Field queries get constructed according to the name of the field
            # they are querying.
            fields = (
                [self.field.lower()] if self.field else model_cls._search_fields
            )

            query_cls = self.get_query_cls(model_cls)
            queries = [
                query_cls.from_model(model_cls, f, self.pattern) for f in fields
            ]
            out_query = reduce(operator.or_, queries)
        else:
            out_query = query.TrueQuery()

        return query.NotQuery(out_query) if self.negate else out_query


# TYPING ERROR
def query_from_strings(
    query_cls: type[query.CollectionQuery],
    model_cls: type[LibModel],
    query_parts: Collection[str],
) -> query.Query:
    """Creates a collection query of type `query_cls` from a list of
    strings in the format used by parse_query_part. `model_cls`
    determines how queries are constructed from strings.
    """
    if not query_parts:
        return query.TrueQuery()
    subqueries = [QueryTerm.make(p).get_query(model_cls) for p in query_parts]
    return query_cls(subqueries) if len(subqueries) > 1 else subqueries[0]


class SortTerm(NamedTuple):
    """Represents a parsed sort specification with field name and direction."""

    field: str
    ascending: bool

    @staticmethod
    def check_valid(part: str) -> bool:
        return len(part) > 1 and part.endswith(("+", "-")) and ":" not in part

    @classmethod
    def make(cls, part: str) -> SortTerm:
        """Parse a sort specification string into a SortPart instance.

        Recognizes field names suffixed with '+' for ascending or '-' for
        descending order. Rejects strings containing colons to avoid conflicts
        with other query syntax.
        """
        return cls(part[:-1], part[-1] == "+")

    def get_sort(self, model_cls: type[LibModel]) -> sort.FieldSort:
        """Create an appropriate FieldSort instance for the target model.

        Selects the optimal sort implementation based on field availability
        and type, handling special cases like smart artist sorting that maps
        to different fields depending on the model.
        """
        field = self.field
        if sort_cls := model_cls._sorts.get(field):
            if sort_cls is sort.SmartArtistSort:
                field = (
                    "albumartist" if model_cls.__name__ == "Album" else "artist"
                )
        elif field in model_cls._fields:
            sort_cls = sort.FixedFieldSort
        else:
            # Flexible or computed.
            sort_cls = sort.SlowFieldSort

        return sort_cls(field, self.ascending)


def sort_from_strings(
    model_cls: type[LibModel], sort_parts: Sequence[str]
) -> sort.Sort:
    """Construct a Sort object from a sequence of sort field strings.

    Interpret, validate, and translate user-provided sort field strings into
    a composite sort order for querying the database. It supports multi-field
    sorting by combining individual sort terms, and ensures that only valid
    fields are included in the resulting sort.

    The main purpose is to provide a flexible way to specify sorting criteria
    (such as from command-line arguments or configuration) and convert them
    into a form that the query engine can use to order results.

    If no valid sort fields are provided, a default "no sort" object is returned.
    """
    if not sort_parts:
        return sort.NullSort()

    terms = map(SortTerm.make, filter(SortTerm.check_valid, sort_parts))
    sorts = [p.get_sort(model_cls) for p in terms]

    return sort.MultipleSort(sorts) if len(sorts) > 1 else sorts[0]


def parse_sorted_query(
    model_cls: type[LibModel], parts: Sequence[str]
) -> tuple[query.Query, sort.Sort]:
    """Given a list of strings, create the `Query` and `Sort` that they
    represent.
    """
    # Separate query token and sort token.
    query_parts = []
    sort_parts = []

    # Split up query in to comma-separated subqueries, each representing
    # an AndQuery, which need to be joined together in one OrQuery
    subquery_parts = []
    for part in [*parts, ","]:
        if part.endswith(","):
            # Ensure we can catch "foo, bar" as well as "foo , bar"
            last_subquery_part = part[:-1]
            if last_subquery_part:
                subquery_parts.append(last_subquery_part)
            # Parse the subquery in to a single Query
            query_parts.append(
                query_from_strings(query.AndQuery, model_cls, subquery_parts)
            )
            del subquery_parts[:]
        elif SortTerm.check_valid(part):
            sort_parts.append(part)
        else:
            subquery_parts.append(part)

    # Avoid needlessly wrapping single statements in an OR
    q = query.OrQuery(query_parts) if len(query_parts) > 1 else query_parts[0]
    s = sort_from_strings(model_cls, sort_parts)
    return q, s


class ModelQuery(NamedTuple):
    """Parses a user-provided string into a query and a sort order.

    The query string can contain both search terms and sorting directives.
    Search terms are combined with AND, and comma-separated groups of terms are
    combined with OR. For example, `foo bar, baz` becomes
    `(foo AND bar) OR baz`.

    Sorting is specified by appending `+` (ascending) or `-` (descending) to a
    field name, e.g., `artist+ album-`.
    """

    query: query.Query
    sort: sort.Sort

    @classmethod
    def parse(
        cls, model_cls: type[LibModel], parts: str | Sequence[str] | None = None
    ) -> Self:
        """Construct a query and sort object from a variety of inputs.

        Create `ModelQuery` instance to parse the provided string or sequence of
        strings.
        """
        parts = parts or []
        query_str = (
            parts
            if isinstance(parts, str)
            else " ".join(map(shlex.quote, parts))
        )
        if parts:
            log.debug("Query string: {!r}", query_str)

        lex = shlex.shlex(
            escape_commas(query_str), punctuation_chars=",", posix=True
        )
        lex.commenters = ""  # make sure we keep '#example' as it is
        lex.whitespace_split = True

        try:
            _query, _sort = parse_sorted_query(model_cls, list(lex))
        except ValueError as exc:
            raise query.InvalidQueryError(query_str, exc) from exc

        if parts:
            log.debug("Parsed query: {!r}", _query)
            log.debug("Parsed sort: {!r}", _sort)
        return cls(_query, _sort)
