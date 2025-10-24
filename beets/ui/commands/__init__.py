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

"""This module provides the default commands for beets' command-line
interface.
"""

from beets.util import deprecate_imports

from .default_commands import default_commands


def __getattr__(name: str):
    """Handle deprecated imports."""
    return deprecate_imports(
        old_module=__name__,
        new_module_by_name={
            "TerminalImportSession": "beets.ui.commands.import_.session",
            "PromptChoice": "beets.ui.commands.import_.session",
            # TODO: We might want to add more deprecated imports here
        },
        name=name,
        version="3.0.0",
    )


__all__ = ["default_commands"]
