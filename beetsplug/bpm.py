# This file is part of beets.
# Copyright 2014, aroquen
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

"""Uses the `KeyFinder` program to add the `initial_key` field.
"""

import logging

from beets import ui
from beets import util
from beets.plugins import BeetsPlugin

log = logging.getLogger('beets')

import time

def bpm(max_strokes=4):
    """Determine BPM (possibly of a playing song) listening to Enter strokes"""
    t0 = None
    dt = []
    for i in range(max_strokes):
        s = raw_input()

        # Press enter to the rhythm...
        if s == '':
            t1 = time.time()
            # Only start measuring at the second stroke
            if t0:
                dt.append(t1 - t0)
            t0 = t1
        else:
            break

    # Return average BPM
    #bpm = (max_strokes-1) / sum(dt) * 60.0
    ave = sum([1./dti*60.0 for dti in dt]) / len(dt)
    return ave

class BPMPlugin(BeetsPlugin):

    def __init__(self):
        super(BPMPlugin, self).__init__()
        self.config.add({
            u'max_strokes': 3,
            u'overwrite': True,
        })

    def commands(self):
        cmd = ui.Subcommand('bpm',
                            help='detect bpm of a song listening to key strokes')
        cmd.func = self.command
        return [cmd]

    def command(self, lib, opts, args):
        self.get_bpm(lib.items(ui.decargs(args)))

    def get_bpm(self, items, write=False):
        overwrite = self.config['overwrite'].get(bool)
        if len(items) > 1:
            log.warning('Can only get bpm of one song at time')
            return
            #raise ValueError('Can only get bpm of one song at time')
        item = items[0]
        
        if item['bpm']:
            log.info('existing bpm {0}'.format(item['bpm']))
            if not overwrite:
                return

        log.info('Press enter {0} times'.format(self.config['max_strokes'].get(int)))
        new_bpm = bpm(self.config['max_strokes'].get(int))
        log.info('adding bpm {0} [old={1}]'.format(int(new_bpm), item['bpm']))
        item['bpm'] = int(new_bpm)
        if write:
            item.try_write()
        item.store()
