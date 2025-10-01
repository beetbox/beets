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


from sys import stderr

import confuse

# Version management using poetry-dynamic-versioning
from ._version import __version__, __version_tuple__

from .util import deprecate_imports

__version__ = "2.4.0"
__author__ = "Adrian Sampson <adrian@radbox.org>"


def __getattr__(name: str):
    """Handle deprecated imports."""
    return deprecate_imports(
        old_module=__name__,
        new_module_by_name={
            "art": "beetsplug._utils",
            "vfs": "beetsplug._utils",
        },
        name=name,
        version="3.0.0",
    )


class IncludeLazyConfig(confuse.LazyConfig):
    """A version of Confuse's LazyConfig that also merges in data from
    YAML files specified in an `include` setting.
    """

    def read(self, user=True, defaults=True):
        super().read(user, defaults)

        try:
            for view in self["include"]:
                self.set_file(view.as_filename())
        except confuse.NotFoundError:
            pass
        except confuse.ConfigReadError as err:
            stderr.write(f"configuration `import` failed: {err.reason}")


config = IncludeLazyConfig("beets", __name__)


__all__ = ["__version__", "__version_tuple__", "config"]
