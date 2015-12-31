# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2015-2016, Ohm Patel.
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

import requests

from beets import plugins, ui

ACOUSTIC_URL = "http://acousticbrainz.org/"
LEVEL = "/high-level"


class AcousticPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(AcousticPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('acousticbrainz',
                            help="fetch metadata from AcousticBrainz")

        def func(lib, opts, args):
            fetch_info(self._log, lib)

        cmd.func = func
        return [cmd]


def fetch_info(log, lib):
    """Currently outputs MBID and corresponding request status code
    """
    for item in lib.items():
        if item.mb_trackid:
            log.info('getting data for: {}', item)

            # Fetch the data from the AB API.
            url = generate_url(item.mb_trackid)
            log.debug('fetching URL: {}', url)
            try:
                rs = requests.get(url)
            except requests.RequestException as exc:
                log.info('request error: {}', exc)
                continue

            # Parse the JSON response.
            try:
                rs.json()
            except ValueError:
                log.debug('Invalid Response: {}', rs.text)

            item.danceable = get_value(log, rs.json(), ["highlevel",
                                                        "danceability",
                                                        "all",
                                                        "danceable"])
            item.mood_happy = get_value(log, rs.json(), ["highlevel",
                                                         "mood_happy",
                                                         "all",
                                                         "happy"])
            item.mood_party = get_value(log, rs.json(), ["highlevel",
                                                         "mood_party",
                                                         "all",
                                                         "party"])

            item.write()
            item.store()


def generate_url(mbid):
    """Generates url of AcousticBrainz end point for given MBID
    """
    return ACOUSTIC_URL + mbid + LEVEL


def get_value(log, data, map_path):
    """Allows traversal of dictionary with cleaner formatting
    """
    try:
        return reduce(lambda d, k: d[k], map_path, data)
    except KeyError:
        log.debug('Invalid Path: {}', map_path)
