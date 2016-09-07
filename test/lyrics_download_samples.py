# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Fabrice Laporte
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

from __future__ import division, absolute_import, print_function

import os
import sys
import requests

import test_lyrics


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError:
        if os.path.isdir(path):
            pass
        else:
            raise


def safe_open_w(path):
    """Open "path" for writing, creating any parent directories as needed.
    """
    mkdir_p(os.path.dirname(path))
    return open(path, 'w')


def main(argv=None):
    """Download one lyrics sample page per referenced source.
    """
    if argv is None:
        argv = sys.argv
    print(u'Fetching samples from:')
    for s in test_lyrics.GOOGLE_SOURCES + test_lyrics.DEFAULT_SOURCES:
        print(s['url'])
        url = s['url'] + s['path']
        fn = test_lyrics.url_to_filename(url)
        if not os.path.isfile(fn):
            html = requests.get(url, verify=False).text
            with safe_open_w(fn) as f:
                f.write(html.encode('utf-8'))

if __name__ == "__main__":
    sys.exit(main())
