# -*- coding: utf-8 -*-
"""main module.

This module will be executed when beets module is run with `-m`.

Example : `python -m beets`

Related links about __main__.py:

* python3 docs entry: https://docs.python.org/3/library/__main__.html
* related SO: http://stackoverflow.com/q/4042905
"""
# This file is part of beets.
# Copyright 2017, Adrian Sampson.
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

import sys
from .ui import main

if __name__ == "__main__":
    main(sys.argv[1:])
