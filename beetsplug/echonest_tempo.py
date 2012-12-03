# This file is part of beets.
# Copyright 2012, David Brenner <david.a.brenner gmail>
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

"""Gets tempo (bpm) for imported music from the EchoNest API. Requires
the pyechonest library (https://github.com/echonest/pyechonest).
"""
import logging
from beets.plugins import BeetsPlugin
from beets import ui
from beets.ui import commands
import pyechonest.config
import pyechonest.song

# Global logger.
log = logging.getLogger('beets')

# The official Echo Nest API key for beets. This can be overridden by
# the user.
ECHONEST_APIKEY = 'NY2KTZHQ0QDSHBAP6'

def fetch_item_tempo(lib, loglevel, item, write):
    """Fetch and store tempo for a single item. If ``write``, then the
    tempo will also be written to the file itself in the bpm field. The 
    ``loglevel`` parameter controls the visibility of the function's 
    status log messages.
    """
    # Skip if the item already has the tempo field.
    if item.bpm:
        log.log(loglevel, u'bpm already present: %s - %s' %
                          (item.artist, item.title))
        return

    # Fetch tempo.
    tempo = get_tempo(item.artist, item.title)
    if not tempo:
        log.log(loglevel, u'tempo not found: %s - %s' %
                          (item.artist, item.title))
        return

    log.log(loglevel, u'fetched tempo: %s - %s' %
                      (item.artist, item.title))
    item.bpm = tempo
    if write:
        item.write()
    lib.store(item)

def get_tempo(artist, title):
    """Get the tempo for a song."""
    # Unfortunately, all we can do is search by artist and title. EchoNest
    # supports foreign ids from MusicBrainz, but currently only for artists,
    # not individual tracks/recordings.
    results = pyechonest.song.search(
        artist=artist, title=title, results=1, buckets=['audio_summary']
    )
    if len(results) > 0:
        return results[0].audio_summary['tempo']
    else:
        return None

AUTOFETCH = True
class EchoNestTempoPlugin(BeetsPlugin):
    def __init__(self):
        super(EchoNestTempoPlugin, self).__init__()
        self.import_stages = [self.imported]

    def commands(self):
        cmd = ui.Subcommand('tempo', help='fetch song tempo (bpm)')
        cmd.parser.add_option('-p', '--print', dest='printbpm',
                              action='store_true', default=False,
                              help='print tempo (bpm) to console')
        def func(lib, config, opts, args):
            # The "write to files" option corresponds to the
            # import_write config value.
            write = ui.config_val(config, 'beets', 'import_write',
                                  commands.DEFAULT_IMPORT_WRITE, bool)

            for item in lib.items(ui.decargs(args)):
                fetch_item_tempo(lib, logging.INFO, item, write)
                if opts.printbpm and item.bpm:
                    ui.print_('{0} BPM'.format(item.bpm))
        cmd.func = func
        return [cmd]

    def configure(self, config):
        global AUTOFETCH
        AUTOFETCH = ui.config_val(config, 'echonest_tempo', 'autofetch', True,
                                  bool)
        apikey = ui.config_val(config, 'echonest_tempo', 'apikey',
                               ECHONEST_APIKEY)
        pyechonest.config.ECHO_NEST_API_KEY = apikey

    # Auto-fetch tempo on import.
    def imported(self, config, task):
        if AUTOFETCH:
            for item in task.imported_items():
                fetch_item_tempo(config.lib, logging.DEBUG, item, False)
