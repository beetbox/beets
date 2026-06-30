"""Tests for the fuzzy query plugin."""

import pytest

from beets.test.helper import PluginTestHelper


class TestFuzzyPlugin(PluginTestHelper):
    plugin = "fuzzy"

    @pytest.mark.parametrize(
        "query,expected_titles",
        [
            pytest.param("~foo", ["seafood"], id="all-fields-substring"),
            pytest.param("title:~foo", ["seafood"], id="field-substring"),
            pytest.param("~seafood", ["seafood"], id="all-fields-equal-length"),
            pytest.param("~zzz", [], id="all-fields-no-match"),
        ],
    )
    def test_fuzzy_queries(self, query, expected_titles):
        self.add_item(title="seafood", artist="alpha")
        self.add_item(title="bread", artist="beta")

        with self.configure_plugin({}):
            items = self.lib.items(query)

        assert [item.title for item in items] == expected_titles
