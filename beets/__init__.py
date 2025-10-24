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


from .config import IncludeLazyConfig, config
from .util import deprecate_imports

__version__: str = "2.5.1"
__author__: str = "Adrian Sampson <adrian@radbox.org>"

__all__: list[str] = ["IncludeLazyConfig", "config"]


def __getattr__(name: str) -> str:
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
