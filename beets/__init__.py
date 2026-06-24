# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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


from __future__ import annotations

from sys import stderr
from typing import TYPE_CHECKING

import confuse

from .util.deprecation import deprecate_imports

if TYPE_CHECKING:
    from .logging import Logger

__version__ = "2.12.0"
__author__ = "Adrian Sampson <adrian@radbox.org>"


def __getattr__(name: str):
    """Handle deprecated imports."""
    return deprecate_imports(
        __name__, {"art": "beetsplug._utils", "vfs": "beetsplug._utils"}, name
    )


class IncludeLazyConfig(confuse.LazyConfig):
    """A version of Confuse's LazyConfig that also merges in data from
    YAML files specified in an `include` setting.
    """

    def read(self, user: bool = True, defaults: bool = True) -> None:
        super().read(user, defaults)

        try:
            for view in self["include"].sequence():
                self.set_file(view.as_filename())
        except confuse.NotFoundError:
            pass
        except confuse.ConfigReadError as err:
            stderr.write(f"configuration `import` failed: {err.reason}")

    def log_sources(self, log: Logger) -> None:
        """Log all configuration sources in priority order."""

        log.debug("configuration sources (highest → lowest priority):")
        # skip first source as it is always the root source/empty
        for source in self.sources[1:]:
            log.debug(
                "{} {}", type(source).__name__, getattr(source, "filename", "")
            )


config = IncludeLazyConfig("beets", __name__)
