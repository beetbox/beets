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

""" Fetch various AcousticBrainz metadata using MBID
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)


from beets import plugins, ui
import requests

ACOUSTIC_URL = "http://acousticbrainz.org/"
LEVEL = "/high-level"


class AcousticPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(AcousticPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('acoustic',
                            help="fetch metadata from AcousticBrainz")

        def func(lib, opts, args):
            fetch_info(lib)

        cmd.func = func
        return [cmd]


def fetch_info(lib):
    """Currently outputs MBID and corresponding request status code
    """
    for item in lib.items():
        if item.mb_trackid:
            r = requests.get(generate_url(item.mb_trackid))
            print(item.mb_trackid)
            print(r.status_code)


def generate_url(mbid):
    """Generates url of AcousticBrainz end point for given MBID
    """
    return ACOUSTIC_URL + mbid + LEVEL
