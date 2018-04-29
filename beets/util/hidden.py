# -*- coding: utf-8 -*-
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

"""Simple library to work out if a file is hidden on different platforms."""
from __future__ import division, absolute_import, print_function

import os
import stat
import ctypes
import sys
import beets.util


def _is_hidden_osx(path):
    """Return whether or not a file is hidden on OS X.

    This uses os.lstat to work out if a file has the "hidden" flag.
    """
    file_stat = os.lstat(beets.util.syspath(path))

    if hasattr(file_stat, 'st_flags') and hasattr(stat, 'UF_HIDDEN'):
        return bool(file_stat.st_flags & stat.UF_HIDDEN)
    else:
        return False


def _is_hidden_win(path):
    """Return whether or not a file is hidden on Windows.

    This uses GetFileAttributes to work out if a file has the "hidden" flag
    (FILE_ATTRIBUTE_HIDDEN).
    """
    # FILE_ATTRIBUTE_HIDDEN = 2 (0x2) from GetFileAttributes documentation.
    hidden_mask = 2

    # Retrieve the attributes for the file.
    attrs = ctypes.windll.kernel32.GetFileAttributesW(beets.util.syspath(path))

    # Ensure we have valid attribues and compare them against the mask.
    return attrs >= 0 and attrs & hidden_mask


def _is_hidden_dot(path):
    """Return whether or not a file starts with a dot.

    Files starting with a dot are seen as "hidden" files on Unix-based OSes.
    """
    return os.path.basename(path).startswith(b'.')


def is_hidden(path):
    """Return whether or not a file is hidden. `path` should be a
    bytestring filename.

    This method works differently depending on the platform it is called on.

    On OS X, it uses both the result of `is_hidden_osx` and `is_hidden_dot` to
    work out if a file is hidden.

    On Windows, it uses the result of `is_hidden_win` to work out if a file is
    hidden.

    On any other operating systems (i.e. Linux), it uses `is_hidden_dot` to
    work out if a file is hidden.
    """
    # Run platform specific functions depending on the platform
    if sys.platform == 'darwin':
        return _is_hidden_osx(path) or _is_hidden_dot(path)
    elif sys.platform == 'win32':
        return _is_hidden_win(path)
    else:
        return _is_hidden_dot(path)

__all__ = ['is_hidden']
