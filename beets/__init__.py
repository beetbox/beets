# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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

from __future__ import absolute_import, unicode_literals

import os

import beets.library
from beets.util import confit

__version__ = '1.3.15'
__author__ = 'Adrian Sampson <adrian@radbox.org>'

Library = beets.library.Library

config = confit.LazyConfig('beets', __name__)

try:
    included_filenames = config['include'].get(list)
except confit.NotFoundError:
    included_filenames = []

for filename in included_filenames:
    filename = os.path.join(config.config_dir(), filename)
    if os.path.isfile(filename):
        config.set_file(filename)
