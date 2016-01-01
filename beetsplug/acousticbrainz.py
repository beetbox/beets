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

        self.config.add({'auto': True})
        if self.config['auto']:
            self.register_listener('import_task_files',
                                   self.import_task_files)

    def commands(self):
        cmd = ui.Subcommand('acousticbrainz',
                            help="fetch metadata from AcousticBrainz")

        def func(lib, opts, args):
            items = lib.items(ui.decargs(args))
            fetch_info(self._log, items)

        cmd.func = func
        return [cmd]

    def import_task_files(self, session, task):
        """Automatically tag imported files
        """

        items = task.imported_items()
        fetch_info(self._log, items)


def fetch_info(log, items):
    """Currently outputs MBID and corresponding request status code
    """
    for item in items:
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

            # Check for missing tracks.
            if rs.status_code == 404:
                log.info('recording ID {} not found', item.mb_trackid)
                continue

            # Parse the JSON response.
            try:
                data = rs.json()
            except ValueError:
                log.debug('Invalid Response: {}', rs.text)

            # Get each field and assign it on the item.
            item.danceable = get_value(
                log,
                data,
                ["highlevel", "danceability", "all", "danceable"],
            )
            item.gender = get_value(
                log,
                data,
                ["highlevel", "gender", "value"],
            )
            item.genre_rosamerica = get_value(
                log,
                data,
                ["highlevel", "genre_rosamerica", "value"],
            )
            item.mood_acoustic = get_value(
                log,
                data,
                ["highlevel", "mood_acoustic", "all", "acoustic"],
            )
            item.mood_aggressive = get_value(
                log,
                data,
                ["highlevel", "mood_aggresive", "all", "aggresive"],
            )
            item.mood_electronic = get_value(
                log,
                data,
                ["highlevel", "mood_electronic", "all", "electronic"],
            )
            item.mood_happy = get_value(
                log,
                data,
                ["highlevel", "mood_happy", "all", "happy"],
            )
            item.mood_party = get_value(
                log,
                data,
                ["highlevel", "mood_party", "all", "party"],
            )
            item.mood_relaxed = get_value(
                log,
                data,
                ["highlevel", "mood_relaxed", "all", "relaxed"],
            )
            item.mood_sad = get_value(
                log,
                data,
                ["highlevel", "mood_sad", "all", "sad"],
            )
            item.rhythm = get_value(
                log,
                data
                ["highlevel", "ismir04_rhythm", "value"],
            )
            item.tonal = get_value(
                log,
                data,
                ["highlevel", "tonal_atonal", "all", "tonal"],
            )
            item.voice_instrumental = get_value(
                log,
                data,
                ["highlevel", "voice_instrumental", "value"],
            )

            # Store the data. We only update flexible attributes, so we
            # don't call `item.try_write()` here.
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
