#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A tiny tool used to test the `convert` plugin. It copies a file and appends
a specified text tag.
"""

from __future__ import division, absolute_import, print_function
import sys
import platform
import locale

PY2 = sys.version_info[0] == 2


# From `beets.util`.
def arg_encoding():
    try:
        return locale.getdefaultlocale()[1] or 'utf-8'
    except ValueError:
        return 'utf-8'


def convert(in_file, out_file, tag):
    """Copy `in_file` to `out_file` and append the string `tag`.
    """
    # On Python 3, encode the tag argument as bytes.
    if not isinstance(tag, bytes):
        tag = tag.encode('utf-8')

    # On Windows, use Unicode paths. On Python 3, we get the actual,
    # Unicode filenames. On Python 2, we get them as UTF-8 byes.
    if platform.system() == 'Windows' and PY2:
        in_file = in_file.decode('utf-8')
        out_file = out_file.decode('utf-8')

    with open(out_file, 'wb') as out_f:
        with open(in_file, 'rb') as in_f:
            out_f.write(in_f.read())
        out_f.write(tag)


if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2], sys.argv[3])
