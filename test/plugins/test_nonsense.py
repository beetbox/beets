# This file is part of beets.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Tests for the nonsense plugin."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar
from unittest.mock import patch

import pytest

from beets import plugins
from beets.test.helper import PluginTestHelper


@pytest.mark.usefixtures("io")
class NonsenseTestCase(PluginTestHelper):
    plugin = "nonsense"
    preload_plugin = False

    QUOTE_FUNCS: ClassVar[dict[str, Callable[[], str]]] = {
        "motivational": lambda: "Stay hungry.",
        "albert_einstein": lambda: "Imagination is more important than knowledge.",
        "mahatma_gandhi": lambda: "Be the change.",
        "steve_jobs": lambda: "Stay foolish.",
        "bill_gates": lambda: "Patience is a key element.",
        "elon_musk": lambda: "When something is important enough, you do it.",
        "mark_zuckerberg": lambda: "Move fast and break things.",
    }

    @pytest.fixture(autouse=True)
    def enable_quotes_generator(self):
        with patch("beetsplug.nonsense.HAS_QUOTES_GENERATOR", True):
            with patch(
                "beetsplug.nonsense.QUOTE_SOURCES", self.QUOTE_FUNCS
            ):
                yield


class TestNonsensePlugin(NonsenseTestCase):
    def test_prints_quote_on_cli_exit(self):
        with self.configure_plugin({}):
            self.io.getoutput()
            plugins.send("cli_exit", lib=self.lib)

        assert self.io.getoutput().strip() in {
            func() for func in self.QUOTE_FUNCS.values()
        }

    def test_uses_configured_source(self):
        with self.configure_plugin({"source": "motivational"}):
            self.io.getoutput()
            plugins.send("cli_exit", lib=self.lib)

        assert self.io.getoutput().strip() == "Stay hungry."

    def test_random_source_picks_from_pool(self):
        chosen = self.QUOTE_FUNCS["steve_jobs"]

        with (
            patch("beetsplug.nonsense.random.choice", return_value=chosen),
            self.configure_plugin({}),
        ):
            self.io.getoutput()
            plugins.send("cli_exit", lib=self.lib)

        assert self.io.getoutput().strip() == "Stay foolish."

    def test_missing_dependency(self, caplog: pytest.LogCaptureFixture):
        with (
            patch("beetsplug.nonsense.HAS_QUOTES_GENERATOR", False),
            caplog.at_level("WARNING"),
            self.configure_plugin({}),
        ):
            self.io.getoutput()
            plugins.send("cli_exit", lib=self.lib)

        assert self.io.getoutput() == ""
        assert "quotes-generator not found" in caplog.text

    def test_fetch_failure(self, caplog: pytest.LogCaptureFixture):
        def fail() -> str:
            raise RuntimeError("boom")

        failing_sources = {"motivational": fail}

        with (
            patch("beetsplug.nonsense.QUOTE_SOURCES", failing_sources),
            caplog.at_level("WARNING"),
            self.configure_plugin({"source": "motivational"}),
        ):
            self.io.getoutput()
            plugins.send("cli_exit", lib=self.lib)

        assert self.io.getoutput() == ""
        assert "Failed to fetch quote: boom" in caplog.text
