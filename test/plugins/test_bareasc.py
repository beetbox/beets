"""Tests for the bare-ASCII query plugin."""

import pytest

from beets.test.helper import PluginTestHelper


class TestBareascPlugin(PluginTestHelper):
    plugin = "bareasc"

    @pytest.mark.parametrize(
        "query,expected_titles",
        [
            pytest.param("#tiento", ["tiénto"], id="accent-insensitive"),
            pytest.param("#TIENTO", ["tiénto"], id="smartcase-sensitive"),
            pytest.param("title:#tiento", ["tiénto"], id="field-query"),
            pytest.param("#zzz", [], id="no-match"),
        ],
    )
    def test_bareasc_queries(self, query, expected_titles):
        self.add_item(title="tiénto", artist="alpha")
        self.add_item(title="bread", artist="beta")

        with self.configure_plugin({}):
            items = self.lib.items(query)

        assert [item.title for item in items] == expected_titles

    def test_bareasc_query_with_null_field(self):
        """
        A bare-ASCII query must not crash when a searched column is NULL.
        """
        item = self.add_item(title="tiénto", artist="alpha")

        # Force a searched column to NULL, which `add_item` never does on
        # its own (fixed string fields default to the empty string).
        with self.lib.transaction() as tx:
            tx.mutate(
                "UPDATE items SET albumartist = NULL WHERE id = ?",
                (item.id,),
            )

        # A non-matching term defeats OR short-circuiting, so the NULL
        # column is handed to `unidecode`. This must not raise.
        with self.configure_plugin({}):
            items = self.lib.items("#zzz")

        assert [i.title for i in items] == []
