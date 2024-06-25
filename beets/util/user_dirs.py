# This file is part of beets.
# Copyright 2024, Arav K.
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

"""
Support for "well-known" user directories via XDG.

This module implements a simple parser for 'user-dirs.dirs(5)', allowing users
to instruct beets on where their music directory in an application-agnostic
fashion.  This file is a mapping from directory names to paths, using a limited
syntax that is compatible with 'sh'.

XDG is a Unix-oriented mechanism; on other platforms, this module will simply
return an empty mapping.  Users of this module should not rely on the existence
of any particular entry -- always provide a reasonable default.
"""

import os
import re
from pathlib import Path
from typing import Optional

from beets import logging

log = logging.getLogger("beets")
user_dir_regex = re.compile(b'XDG_(.*)_DIR=("[^"]*"|.*)')


def parse_user_dirs(
    home: Optional[Path] = None,
    xdg_config_home: Optional[Path] = None,
) -> dict[str, Path]:
    """
    Parse the 'user-dirs.dirs' file in the given configuration directory.

    If this is not a Unix-like platform, an empty mapping is returned.

    :param home: the user's home directory.
      If not provided, this defaults to `$HOME`.

    :param xdg_config_home: the user's configuration directory.
      If not provided, this defaults to `~/.config`.

    :return: a mapping from (lower-cased) keys to paths.
    """

    # Ensure we're on an XDG-compatible system.
    if os.name != "posix":
        return {}

    # Resolve the user's home directory.
    home = home or Path.home()

    # Resolve the user's configuration directory.
    if xdg_config_home is None and "XDG_CONFIG_HOME" in os.environ:
        xdg_config_home = Path(os.environ["XDG_CONFIG_HOME"])
    xdg_config_home = xdg_config_home or (home / ".config")

    # Find and read the 'user-dirs.dirs' file.
    path = xdg_config_home / "user-dirs.dirs"
    try:
        with open(path, "rb") as file:
            data = file.readlines()
    except OSError:
        return {}

    # Parse the loaded data line by line.
    mapping: dict[str, Path] = {}
    for line in map(bytes.strip, data):

        # Skip blank lines.
        if len(line) == 0:
            continue

        # Skip comment lines.
        if line.startswith(b"#"):
            continue

        # Check for the expected syntax.
        m = user_dir_regex.fullmatch(line)
        if m is None:
            log.warning("malformed line in '{}': '{}'", path, line)
            continue
        key, val = m.groups()

        # Parse the key.
        key = key.decode().lower()

        # Parse the path value.
        if val.startswith(b"$HOME/"):
            val = home / Path(os.fsdecode(val[6:]))
        elif val.startswith(b"/"):
            val = Path(os.fsdecode(val))
        else:
            log.warning("malformed line in '{}': '{}'", path, line)
            continue

        mapping[key] = val

    return mapping
