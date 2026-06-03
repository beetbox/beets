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

"""Print a random quote after every beets command."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import TYPE_CHECKING

from beets import ui
from beets.plugins import BeetsPlugin

if TYPE_CHECKING:
    from beets.library import Library

try:
    import quotes_generator

    HAS_QUOTES_GENERATOR = True
except ImportError:
    HAS_QUOTES_GENERATOR = False


QUOTE_SOURCES: dict[str, Callable[[], str]] = {
    "motivational": quotes_generator.motivational_quotes,
    "albert_einstein": quotes_generator.albert_einstein_quotes,
    "mahatma_gandhi": quotes_generator.mahatma_gandhi_quotes,
    "steve_jobs": quotes_generator.steve_jobs_quotes,
    "bill_gates": quotes_generator.bill_gates_quotes,
    "elon_musk": quotes_generator.elon_musk_quotes,
    "mark_zuckerberg": quotes_generator.mark_zuckerberg_quotes,
} if HAS_QUOTES_GENERATOR else {}


class NonsensePlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()

        self.config.add({"source": None})

        if not HAS_QUOTES_GENERATOR:
            self._log.warning(
                "quotes-generator not found; install with pip install "
                '"beets[nonsense]"'
            )
            return

        self.register_listener("cli_exit", self.cli_exit)

    def cli_exit(self, lib: Library) -> None:
        try:
            quote = self._get_quote()
        except Exception as exc:
            self._log.warning("Failed to fetch quote: {}", exc)
            return

        ui.print_(quote)

    def _get_quote(self) -> str:
        source = self.config["source"].get()
        if source:
            try:
                quote_func = QUOTE_SOURCES[source]
            except KeyError as exc:
                valid = ", ".join(sorted(QUOTE_SOURCES))
                raise ValueError(
                    f"unknown nonsense source {source!r}; choose from: {valid}"
                ) from exc
        else:
            quote_func = random.choice(list(QUOTE_SOURCES.values()))

        return quote_func()
