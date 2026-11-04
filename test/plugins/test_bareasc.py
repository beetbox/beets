"""Tests for the bare-ASCII query plugin."""

import pytest

from beets.test.helper import IOMixin, PluginTestHelper


class TestBareascPlugin(IOMixin, PluginTestHelper):
    plugin = "bareasc"

    def add_library(self):
        """Add the fixture items used by the migrated tests.

        ``self.lib.add`` overrides any ``id=<n>`` and assigns the next free
        id number.
        """
        self.add_item(title="with accents", album_id=2, artist="Antonín Dvořák")
        self.add_item(title="without accents", artist="Antonín Dvorak")
        self.add_item(title="with umlaut", album_id=2, artist="Brüggen")
        self.add_item(title="without umlaut or e", artist="Bruggen")
        self.add_item(title="without umlaut with e", artist="Brueggen")

    @pytest.mark.parametrize(
        "query,expected_titles",
        [
            # Normal search, no accents, not using bare-ASCII match.
            pytest.param("dvorak", ["without accents"], id="plain-no-accents"),
            # Normal search, with accents, not using bare-ASCII match.
            pytest.param("dvořák", ["with accents"], id="plain-accents"),
            # Bare-ASCII search, no accents.
            pytest.param(
                "#dvorak",
                ["without accents", "with accents"],
                id="bareasc-no-accents",
            ),
            # Bare-ASCII search, with accents.
            pytest.param(
                "#dvořák",
                ["without accents", "with accents"],
                id="bareasc-accents",
            ),
            # Bare-ASCII search, with incorrect accent.
            pytest.param(
                "#dvořäk",
                ["without accents", "with accents"],
                id="bareasc-wrong-accent",
            ),
            # Bare-ASCII search, with no umlaut.
            pytest.param(
                "#Bruggen",
                ["without umlaut or e", "with umlaut"],
                id="bareasc-no-umlaut",
            ),
            # Bare-ASCII search, with umlaut.
            pytest.param(
                "#Brüggen",
                ["without umlaut or e", "with umlaut"],
                id="bareasc-umlaut",
            ),
            # Smartcase: an upper-case pattern is still case- and
            # accent-insensitive.
            pytest.param(
                "#DVORAK",
                ["without accents", "with accents"],
                id="smartcase-uppercase",
            ),
            # Field-qualified bare-ASCII search against an accented field.
            pytest.param(
                "artist:#dvorak",
                ["without accents", "with accents"],
                id="field-query",
            ),
            # A term that matches nothing.
            pytest.param("#zzz", [], id="no-match"),
        ],
    )
    def test_bareasc_search(self, query, expected_titles):
        self.add_library()

        with self.configure_plugin({"prefix": "#"}):
            items = self.lib.items(query)

        assert [item.title for item in items] == expected_titles

    def test_bareasc_list_output(self):
        """Bare-ASCII version of list command - check output."""
        self.add_library()

        with self.configure_plugin({"prefix": "#"}):
            output = self.run_with_output("bareasc", "with accents")

        assert "Antonin Dvorak" in output

    def test_bareasc_format_output(self):
        """Bare-ASCII version of list -f command - check output."""
        self.add_library()

        with self.configure_plugin({"prefix": "#"}):
            output = self.run_with_output(
                "bareasc", "with accents", "-f", "$artist:: $title"
            )

        assert output == "Antonin Dvorak:: with accents\n"

    def test_bareasc_query_with_null_field(self):
        """
        A bare-ASCII query must not crash when a searched column is NULL.
        """
        item = self.add_item(title="tiénto", artist="alpha")

        # Force a searched column to NULL, which `add_item` never does on
        # its own (fixed string fields default to the empty string).
        with self.lib.transaction() as tx:
            tx.mutate(
                "UPDATE items SET albumartist = NULL WHERE id = ?", (item.id,)
            )

        # A non-matching term defeats OR short-circuiting, so the NULL
        # column is handed to `unidecode`. This must not raise.
        with self.configure_plugin({"prefix": "#"}):
            items = self.lib.items("#zzz")

        assert [i.title for i in items] == []
