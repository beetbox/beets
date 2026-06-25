"""Provides a fuzzy matching query."""

import difflib

from beets import config
from beets.dbcore.query import StringFieldQuery
from beets.plugins import BeetsPlugin


class FuzzyQuery(StringFieldQuery[str]):
    def __init__(self, field_name: str, pattern: str, *_) -> None:
        # Fuzzy matching is only available via `string_match`.
        super().__init__(field_name, pattern, fast=False)

    @classmethod
    def string_match(cls, pattern: str, val: str) -> bool:
        # smartcase
        if pattern.islower():
            val = val.lower()
        query_matcher = difflib.SequenceMatcher(None, pattern, val)
        threshold = config["fuzzy"]["threshold"].as_number()
        # Adjust match threshold for the case that the pattern is shorter
        # than the value being matched. This allows the pattern to match
        # substrings of the value, not just the entire value.
        if len(pattern) < len(val):
            max_possible_ratio = 2 * len(pattern) / (len(pattern) + len(val))
            threshold *= max_possible_ratio

        # If upper bound of the ratio meets threshold, then calculate
        # the actual ratio.
        if query_matcher.quick_ratio() >= threshold:
            return query_matcher.ratio() >= threshold

        return False


class FuzzyPlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add({"prefix": "~", "threshold": 0.7})

    def queries(self):
        prefix = self.config["prefix"].as_str()
        return {prefix: FuzzyQuery}
