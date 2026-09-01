"""Plugin to rewrite fields based on a given query."""

from __future__ import annotations

import re
import shlex
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar, TypedDict

import confuse

from beets.dbcore import AndQuery, query_from_strings
from beets.dbcore.types import MULTI_VALUE_DSV
from beets.library import Album, Item
from beets.plugins import BeetsPlugin
from beets.ui import UserError

from .rewrite import apply_rewrite_rules

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from beets.library import LibModel


class AdvancedRewriteConfig(TypedDict):
    match: str
    replacements: dict[str, str | list[str]]


def rewriter(
    field: str,
    simple_rules: list[tuple[re.Pattern[str], str]],
    advanced_rules: list[tuple[AndQuery, str | list[str]]],
) -> Callable[[LibModel], str | list[str]]:
    """Template field function factory.

    Create a template field function that rewrites the given field
    with the given rewriting rules.
    ``simple_rules`` must be a list of (pattern, replacement) pairs.
    ``advanced_rules`` must be a list of (query, replacement) pairs.
    """

    def fieldfunc(item: LibModel) -> str | list[str]:
        value = item._values_fixed[field]
        if (new_value := apply_rewrite_rules(value, simple_rules)) != value:
            # Rewrite activated.
            return new_value

        for query, replacement in advanced_rules:
            if query.match(item):
                # Rewrite activated.
                return replacement
        # Not activated; return original value.
        return value

    return fieldfunc


class AdvancedRewritePlugin(BeetsPlugin):
    """Plugin to rewrite fields based on a given query."""

    # Used to apply the same rewrite to the corresponding album field.
    corresponding_album_fields: ClassVar[dict[str, str]] = {
        "artist": "albumartist",
        "artists": "albumartists",
        "artist_sort": "albumartist_sort",
        "artists_sort": "albumartists_sort",
    }

    def __init__(self) -> None:
        """Parse configuration and register template fields for rewriting."""
        super().__init__()
        self.register_listener("pluginload", self.loaded)

    def parse_simple_rule(
        self, rule: dict[str, str]
    ) -> Iterator[tuple[str, tuple[re.Pattern[str], str]]]:
        if len(rule) != 1:
            raise UserError(
                "Simple rewrites must have only one rule, "
                "but found multiple entries. "
                "Did you forget to prepend a dash (-)?"
            )
        key, value = next(iter(rule.items()))
        try:
            fieldname, pattern = key.split(None, 1)
        except ValueError:
            raise UserError(f"Invalid simple rewrite specification {key}")
        if fieldname not in Item._fields:
            raise UserError(f"invalid field name {fieldname} in rewriter")
        self._log.debug(
            f"adding simple rewrite '{pattern}' → '{value}' "
            f"for field {fieldname}"
        )
        compiled_pattern = re.compile(pattern.lower())
        yield fieldname, (compiled_pattern, value)

        # Apply the same rewrite to the corresponding album field.
        if album_field := self.corresponding_album_fields.get(fieldname):
            yield album_field, (compiled_pattern, value)

    def parse_advanced_rule(
        self, rule: AdvancedRewriteConfig
    ) -> Iterator[tuple[str, tuple[AndQuery, str | list[str]]]]:
        match = rule["match"]
        replacements = rule["replacements"]
        if len(replacements) == 0:
            raise UserError(
                "Advanced rewrites must have at least one replacement"
            )
        query = query_from_strings(
            AndQuery, Item, prefixes={}, query_parts=shlex.split(match)
        )
        for fieldname, replacement in replacements.items():
            if fieldname not in Item._fields:
                raise UserError(f"Invalid field name {fieldname} in rewriter")
            self._log.debug(
                f"adding advanced rewrite to '{replacement}' "
                f"for field {fieldname}"
            )
            if isinstance(replacement, list):
                if Item._fields[fieldname] is not MULTI_VALUE_DSV:
                    raise UserError(
                        f"Field {fieldname} is not a multi-valued field "
                        f"but a list was given: {', '.join(replacement)}"
                    )
            elif isinstance(replacement, str):
                if Item._fields[fieldname] is MULTI_VALUE_DSV:
                    replacement = [replacement]
            else:
                raise UserError(
                    f"Invalid type of replacement {replacement} "
                    f"for field {fieldname}"
                )

            yield fieldname, (query, replacement)

            # Apply the same rewrite to the corresponding album field.
            if album_field := self.corresponding_album_fields.get(fieldname):
                yield album_field, (query, replacement)

    def loaded(self) -> None:
        template = confuse.Sequence(
            confuse.OneOf[dict[str, str] | AdvancedRewriteConfig](
                [
                    confuse.MappingValues(str),
                    {
                        "match": str,
                        "replacements": confuse.MappingValues(
                            confuse.OneOf([str, confuse.Sequence(str)])
                        ),
                    },
                ]
            )
        )

        # Gather all the rewrite rules for each field.
        class RulesContainer:
            simple: list[tuple[re.Pattern[str], str]]
            advanced: list[tuple[AndQuery, str | list[str]]]

            def __init__(self) -> None:
                self.simple = []
                self.advanced = []

        rules = defaultdict[str, RulesContainer](RulesContainer)
        for rule in self.config.get(template):
            if "match" not in rule:
                for field, repl in self.parse_simple_rule(rule):
                    rules[field].simple.append(repl)
            else:
                for field, advanced_repl in self.parse_advanced_rule(rule):  # type: ignore[arg-type]
                    rules[field].advanced.append(advanced_repl)

        # Replace each template field with the new rewriter function.
        for fieldname, fieldrules in rules.items():
            getter = rewriter(fieldname, fieldrules.simple, fieldrules.advanced)
            self.template_fields[fieldname] = getter
            if fieldname in Album._fields:
                self.album_template_fields[fieldname] = getter
