# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2019, Rahul Ahuja.
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

"""Update library's tags using Discogs.
"""
from __future__ import division, absolute_import, print_function

from beets.plugins import SyncMetadataSourcePlugin, BeetsPlugin

from .discogs import DiscogsPlugin


class DCSyncPlugin(SyncMetadataSourcePlugin, BeetsPlugin):
    def __init__(self):
        super(DCSyncPlugin, self).__init__('dcsync', DiscogsPlugin)
