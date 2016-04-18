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
from __future__ import division, absolute_import, print_function

import requests
import operator

from beets import plugins, ui

ACOUSTIC_BASE = "http://acousticbrainz.org/"
LEVELS = ["/low-level", "/high-level"]


class AcousticPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(AcousticPlugin, self).__init__()

        self.config.add({'auto': True})
        if self.config['auto']:
            self.register_listener('import_task_files',
                                   self.import_task_files)

    def commands(self):
        cmd = ui.Subcommand('acousticbrainz',
                            help=u"fetch metadata from AcousticBrainz")

        def func(lib, opts, args):
            items = lib.items(ui.decargs(args))
            fetch_info(self._log, items, ui.should_write())

        cmd.func = func
        return [cmd]

    def import_task_files(self, session, task):
        """Function is called upon beet import.
        """

        items = task.imported_items()
        fetch_info(self._log, items, False)


def fetch_info(log, items, write):
    """Get data from AcousticBrainz for the items.
    """

    def get_value(*map_path):
        try:
            return reduce(operator.getitem, map_path, data)
        except KeyError:
            log.debug(u'Invalid Path: {}', map_path)

    for item in items:
        if item.mb_trackid:
            log.info(u'getting data for: {}', item)

            # Fetch the data from the AB API.
            urls = [generate_url(item.mb_trackid, path) for path in LEVELS]
            log.debug(u'fetching URLs: {}', ' '.join(urls))
            try:
                res = [requests.get(url) for url in urls]
            except requests.RequestException as exc:
                log.info(u'request error: {}', exc)
                continue

            # Check for missing tracks.
            if any(r.status_code == 404 for r in res):
                log.info(u'recording ID {} not found', item.mb_trackid)
                continue

            # Parse the JSON response.
            try:
                data = res[0].json()
                data.update(res[1].json())
            except ValueError:
                log.debug(u'Invalid Response: {} & {}', [r.text for r in res])

            # Get each field and assign it on the item.
            item.danceable = get_value(
                "highlevel", "danceability", "all", "danceable",
            )
            item.gender = get_value(
                "highlevel", "gender", "value",
            )
            item.genre_rosamerica = get_value(
                "highlevel", "genre_rosamerica", "value"
            )
            item.mood_acoustic = get_value(
                "highlevel", "mood_acoustic", "all", "acoustic"
            )
            item.mood_aggressive = get_value(
                "highlevel", "mood_aggressive", "all", "aggressive"
            )
            item.mood_electronic = get_value(
                "highlevel", "mood_electronic", "all", "electronic"
            )
            item.mood_happy = get_value(
                "highlevel", "mood_happy", "all", "happy"
            )
            item.mood_party = get_value(
                "highlevel", "mood_party", "all", "party"
            )
            item.mood_relaxed = get_value(
                "highlevel", "mood_relaxed", "all", "relaxed"
            )
            item.mood_sad = get_value(
                "highlevel", "mood_sad", "all", "sad"
            )
            item.rhythm = get_value(
                "highlevel", "ismir04_rhythm", "value"
            )
            item.tonal = get_value(
                "highlevel", "tonal_atonal", "all", "tonal"
            )
            item.voice_instrumental = get_value(
                "highlevel", "voice_instrumental", "value"
            )
            item.average_loudness = get_value(
                "lowlevel", "average_loudness"
            )
            item.chords_changes_rate = get_value(
                "tonal", "chords_changes_rate"
            )
            item.chords_key = get_value(
                "tonal", "chords_key"
            )
            item.chords_number_rate = get_value(
                "tonal", "chords_number_rate"
            )
            item.chords_scale = get_value(
                "tonal", "chords_scale"
            )
            item.initial_key = '{} {}'.format(
                get_value("tonal", "key_key"),
                get_value("tonal", "key_scale")
            )
            item.key_strength = get_value(
                "tonal", "key_strength"
            )

            # Store the data.
            item.store()
            if write:
                item.try_write()


def generate_url(mbid, level):
    """Generates AcousticBrainz end point url for given MBID.
    """
    return ACOUSTIC_BASE + mbid + level
