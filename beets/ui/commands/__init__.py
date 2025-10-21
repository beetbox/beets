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

import os
import re
import textwrap
from collections import Counter
from collections.abc import Sequence
from functools import cached_property
from itertools import chain
from platform import python_version
from typing import Any, NamedTuple

import beets
from beets import autotag, config, importer, library, logging, plugins, ui, util
from beets.autotag import Recommendation, hooks
from beets.ui import (
    input_,
    print_,
    print_column_layout,
    print_newline_layout,
    show_path_changes,
)
from beets.util import (
    MoveOperation,
    ancestry,
    displayable_path,
    functemplate,
    normpath,
    syspath,
)
from beets.util.units import human_bytes, human_seconds, human_seconds_short

from . import _store_dict

VARIOUS_ARTISTS = "Various Artists"

# Global logger.
log = logging.getLogger("beets")

# The list of default subcommands. This is populated with Subcommand
# objects that can be fed to a SubcommandsOptionParser.
default_commands = []


# import: Autotagger and importer.

# Importer utilities and support.
