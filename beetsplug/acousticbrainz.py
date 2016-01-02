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

"""Fetch various AcousticBrainz metadata using MBID.
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import requests

from beets import plugins, ui

ACOUSTIC_BASE = "http://acousticbrainz.org/"


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
        """Function is called upon beet import.
        """

        items = task.imported_items()
        fetch_info(self._log, items)


def fetch_info(log, items):
    """Currently outputs MBID and corresponding request status code.
    """
    for item in items:
        if item.mb_trackid:
            log.info('getting data for: {}', item)

            # Fetch the data from the AB API.
            high_url = generate_url(item.mb_trackid, "/high-level")
            low_url = generate_url(item.mb_trackid, "/low-level")
            log.debug('fetching URL: {}', high_url)
            log.debug('fetching URL: {}', low_url)
            try:
                high = requests.get(high_url)
                low = requests.get(low_url)
            except requests.RequestException as exc:
                log.info('request error: {}', exc)
                continue

            # Check for missing tracks.
            if high.status_code == 404 or low.status_code == 404:
                log.info('recording ID {} not found', item.mb_trackid)
                continue

            # Parse the JSON response.
            try:
                high_data = high.json()
            except ValueError:
                log.debug('Invalid Response: {}', high.text)
            try:
                low_data = low.json()
            except ValueError:
                log.debug('Invalid Response: {}', low.text)

            # Get each field and assign it on the item.
            item.danceable = get_value(
                log,
                high_data,
                ["highlevel", "danceability", "all", "danceable"],
            )
            item.gender = get_value(
                log,
                high_data,
                ["highlevel", "gender", "value"],
            )
            item.genre_rosamerica = get_value(
                log,
                high_data,
                ["highlevel", "genre_rosamerica", "value"],
            )
            item.mood_acoustic = get_value(
                log,
                high_data,
                ["highlevel", "mood_acoustic", "all", "acoustic"],
            )
            item.mood_aggressive = get_value(
                log,
                high_data,
                ["highlevel", "mood_aggresive", "all", "aggresive"],
            )
            item.mood_electronic = get_value(
                log,
                high_data,
                ["highlevel", "mood_electronic", "all", "electronic"],
            )
            item.mood_happy = get_value(
                log,
                high_data,
                ["highlevel", "mood_happy", "all", "happy"],
            )
            item.mood_party = get_value(
                log,
                high_data,
                ["highlevel", "mood_party", "all", "party"],
            )
            item.mood_relaxed = get_value(
                log,
                high_data,
                ["highlevel", "mood_relaxed", "all", "relaxed"],
            )
            item.mood_sad = get_value(
                log,
                high_data,
                ["highlevel", "mood_sad", "all", "sad"],
            )
            item.rhythm = get_value(
                log,
                high_data,
                ["highlevel", "ismir04_rhythm", "value"],
            )
            item.tonal = get_value(
                log,
                high_data,
                ["highlevel", "tonal_atonal", "all", "tonal"],
            )
            item.voice_instrumental = get_value(
                log,
                high_data,
                ["highlevel", "voice_instrumental", "value"],
            )
            item.average_loudness = get_value(
                log,
                low_data,
                ["lowlevel", "average_loudness"],
            )
            item.chords_changes_rate = get_value(
                log,
                low_data,
                ["tonal", "chords_changes_rate"],
            )
            item.chords_key = get_value(
                log,
                low_data,
                ["tonal", "chords_key"],
            )
            item.chords_number_rate = get_value(
                log,
                low_data,
                ["tonal", "chords_number_rate"],
            )
            item.chords_scale = get_value(
                log,
                low_data,
                ["tonal", "chords_scale"],
            )
            item.key_key = get_value(
                log,
                low_data,
                ["tonal", "key_key"],
            )
            item.key_scale = get_value(
                log,
                low_data,
                ["tonal", "key_scale"],
            )
            item.key_strength = get_value(
                log,
                low_data,
                ["tonal", "key_stength"],
            )

            # Store the data. We only update flexible attributes, so we
            # don't call `item.try_write()` here.
            item.store()


def generate_url(mbid, level):
    """Generates AcousticBrainz end point url for given MBID.
    """
    return ACOUSTIC_BASE + mbid + level


def get_value(log, data, map_path):
    """Allows easier traversal of dictionary.
    """
    try:
        return reduce(lambda d, k: d[k], map_path, data)
    except KeyError:
        log.debug('Invalid Path: {}', map_path)
