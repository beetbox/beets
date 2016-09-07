#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A tiny tool used to test the `convert` plugin. It copies a file and appends
a specified text tag.
"""

from __future__ import division, absolute_import, print_function
from os.path import dirname, abspath
import six
import sys
import platform

beets_src = dirname(dirname(dirname(abspath(__file__))))
sys.path.insert(0, beets_src)

from beets.util import arg_encoding  # noqa: E402


def convert(in_file, out_file, tag):
    """Copy `in_file` to `out_file` and append the string `tag`.
    """
    # On Python 3, encode the tag argument as bytes.
    if not isinstance(tag, bytes):
        tag = tag.encode('utf-8')

    # On Windows, use Unicode paths. (The test harness gives them to us
    # as UTF-8 bytes.)
    if platform.system() == 'Windows':
        if not six.PY2:
            in_file = in_file.encode(arg_encoding())
            out_file = out_file.encode(arg_encoding())
        in_file = in_file.decode('utf-8')
        out_file = out_file.decode('utf-8')

    with open(out_file, 'wb') as out_f:
        with open(in_file, 'rb') as in_f:
            out_f.write(in_f.read())
        out_f.write(tag)


if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
