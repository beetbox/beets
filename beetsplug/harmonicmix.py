# This file is part of beets.
# Copyright 2025, Angelos Exaftopoulos.
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

"""Finds songs that are harmonically compatible with a chosen track.
The results also have a matching BPM (+/- 8% from the source track).
"""

from beets.plugins import BeetsPlugin
from beets import ui


class HarmonicLogic:
    """Pure music theory logic.
    Separated from the plugin for test coverage.
    """

    # Mapping normalized to standard musical notation
    # Also covers enharmonics (i.e. F#=Gb and so on)
    CIRCLE_OF_FIFTHS = {
        # Major Keys
        'C':  ['C', 'B#', 'G', 'F', 'E#', 'Am'],
        'G':  ['G', 'D', 'C', 'B#', 'Em', 'Fbm'],
        'D':  ['D', 'A', 'G', 'Bm', 'Cbm'],
        'A':  ['A', 'E', 'Fb', 'D', 'F#m', 'Gbm'],
        'E':  ['E', 'Fb', 'B', 'Cb', 'A', 'C#m', 'Dbm'],
        'B':  ['B', 'Cb', 'F#', 'Gb', 'E', 'Fb', 'G#m', 'Abm'],
        'Gb': ['Gb', 'F#', 'Db', 'C#', 'Cb', 'B', 'Ebm', 'D#m'],
        'F#': ['F#', 'Gb', 'C#', 'Db', 'B', 'Cb', 'D#m', 'Ebm'],
        'Db': ['Db', 'C#', 'Ab', 'G#', 'Gb', 'F#', 'Bbm', 'A#m'],
        'C#': ['C#', 'Db', 'G#', 'Ab', 'F#', 'Gb', 'A#m', 'Bbm'],
        'Ab': ['Ab', 'G#', 'Eb', 'D#', 'Db', 'C#', 'Fm', 'E#m'],
        'Eb': ['Eb', 'D#', 'Bb', 'A#', 'Ab', 'G#', 'Cm', 'B#m'],
        'Bb': ['Bb', 'A#', 'F', 'E#', 'Eb', 'D#', 'Gm'],
        'F':  ['F', 'E#', 'C', 'B#', 'Bb', 'A#', 'Dm'],

        # Major Enharmonics
        'B#': ['C', 'B#', 'G', 'F', 'E#', 'Am'],
        'E#': ['F', 'E#', 'C', 'B#', 'Bb', 'A#', 'Dm'],
        'Cb': ['B', 'Cb', 'F#', 'Gb', 'E', 'Fb', 'G#m', 'Abm'],
        'Fb': ['E', 'Fb', 'B', 'Cb', 'A', 'C#m', 'Dbm'],

        # Minor Keys
        'Am': ['Am', 'Em', 'Fbm', 'Dm', 'C', 'B#'],
        'Em': ['Em', 'Fbm', 'Bm', 'Cbm', 'Am', 'G'],
        'Bm': ['Bm', 'Cbm', 'F#m', 'Gbm', 'Em', 'Fbm', 'D'],
        'F#m': ['F#m', 'Gbm', 'C#m', 'Dbm', 'Bm', 'Cbm', 'A'],
        'C#m': ['C#m', 'Dbm', 'G#m', 'Abm', 'F#m', 'Gbm', 'E', 'Fb'],
        'G#m': ['G#m', 'Abm', 'D#m', 'Ebm', 'C#m', 'Dbm', 'B', 'Cb'],
        'Ebm': ['Ebm', 'D#m', 'Bbm', 'A#m', 'G#m', 'Abm', 'Gb', 'F#'],
        'D#m': ['D#m', 'Ebm', 'A#m', 'Bbm', 'G#m', 'Abm', 'F#', 'Gb'],
        'Bbm': ['Bbm', 'A#m', 'Fm', 'E#m', 'Ebm', 'D#m', 'Db', 'C#'],
        'Fm': ['Fm', 'E#m', 'Cm', 'B#m', 'Bbm', 'A#m', 'Ab', 'G#'],
        'Cm': ['Cm', 'B#m', 'Gm', 'Fm', 'E#m', 'Eb', 'D#'],
        'Gm': ['Gm', 'Dm', 'Cm', 'B#m', 'Bb', 'A#'],
        'Dm': ['Dm', 'Am', 'Gm', 'F', 'E#'],

        # Minor Enharmonics
        'E#m': ['Fm', 'E#m', 'Cm', 'B#m', 'Bbm', 'A#m', 'Ab', 'G#'],
        'B#m': ['Cm', 'B#m', 'Gm', 'Fm', 'E#m', 'Eb', 'D#'],
        'Cbm': ['Bm', 'Cbm', 'F#m', 'Gbm', 'Em', 'Fbm', 'D'],
        'Fbm': ['Em', 'Fbm', 'Bm', 'Cbm', 'Am', 'G'],
    }

    @staticmethod
    def get_compatible_keys(key):
        """Returns a list of compatible keys for a given input key."""
        # We assume the DB uses standard short notation, i.e. C instead of C major
        if not key:
            return []

        # Strip whitespace
        key = key.strip()
        return HarmonicLogic.CIRCLE_OF_FIFTHS.get(key, [])

    @staticmethod
    def get_bpm_range(bpm, range_percent=0.08):
        """Returns a tuple (min_bpm, max_bpm)"""
        if not bpm:
            return (0, 0)
        return (bpm * (1 - range_percent), bpm * (1 + range_percent))


class HarmonicMixPlugin(BeetsPlugin):
    """The Beets plugin wrapper."""

    def __init__(self):
        super().__init__()

    def commands(self):
        cmd = ui.Subcommand('mix', help='find harmonically compatible songs')
        cmd.func = self.command
        return [cmd]

    def command(self, lib, opts, args):
        query = args
        items = lib.items(query)

        if not items:
            self._log.warning("Song not found!")
            return

        source_song = items[0]
        # Use .get() to avoid crashing if tags are missing
        source_key = source_song.get('key')
        source_bpm = source_song.get('bpm')

        if not source_key:
            self._log.warning(f"No key found for {source_song.title}")
            return

        self._log.info(
            f"Source: {source_song.title} | Key: {source_key} | BPM: {source_bpm}"
        )

        # 1. Get Logic from Helper Class
        compatible_keys = HarmonicLogic.get_compatible_keys(source_key)

        # 2. BPM Range
        # Only use BPM logic if the song actually has a BPM
        bpm_query_part = ""
        if source_bpm:
            min_b, max_b = HarmonicLogic.get_bpm_range(source_bpm)
            # Create a range query string for Beets
            bpm_query_part = f" bpm:{min_b}..{max_b}"

        # 3. Construct Query
        # We want: (Key:A OR Key:B...) AND BPM range
        # Beets query syntax for OR is a bit tricky, so we filter manually
        # for safety and simplicity, using only the BPM filter in the query.
        candidates = lib.items(bpm_query_part.strip())

        found_count = 0
        for song in candidates:
            # skip source
            if song.id == source_song.id:
                continue

            if song.get('key') in compatible_keys:
                self._log.info(
                    f"MATCH: {song.title} ({song.get('key')}, {song.get('bpm')} BPM)"
                )
                found_count += 1

        if found_count == 0:
            self._log.info("No mixable songs found.")
