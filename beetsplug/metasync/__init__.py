# This file is part of beets.
# Copyright 2015, Heinz Wiesinger.
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

"""Synchronize information from music player libraries
"""

from beets import ui, logging
from beets.plugins import BeetsPlugin
from beets.dbcore import types
from beets.library import DateType
from sys import modules
import inspect

# Loggers.
log = logging.getLogger('beets.metasync')


class MetaSyncPlugin(BeetsPlugin):

    item_types = {
        'amarok_rating':      types.INTEGER,
        'amarok_score':       types.FLOAT,
        'amarok_uid':         types.STRING,
        'amarok_playcount':   types.INTEGER,
        'amarok_firstplayed': DateType(),
        'amarok_lastplayed':  DateType()
    }

    def __init__(self):
        super(MetaSyncPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('metasync',
                            help='update metadata from music player libraries')
        cmd.parser.add_option('-p', '--pretend', action='store_true',
                              help='show all changes but do nothing')
        cmd.parser.add_option('-s', '--source', action='store_false',
                              default=self.config['source'].as_str_seq(),
                              help="select specific sources to import from")
        cmd.parser.add_format_option()
        cmd.func = self.func
        return [cmd]

    def func(self, lib, opts, args):
        """Command handler for the metasync function.
        """
        pretend = opts.pretend
        source = opts.source
        query = ui.decargs(args)

        sources = {}

        for player in source:
            __import__('beetsplug.metasync', fromlist=[str(player)])

            module = 'beetsplug.metasync.' + player

            if module not in modules.keys():
                log.error(u'Unknown metadata source \'' + player + '\'')
                continue

            classes = inspect.getmembers(modules[module], inspect.isclass)

            for entry in classes:
                if entry[0].lower() == player:
                    sources[player] = entry[1]()
                else:
                    continue

        for item in lib.items(query):
            for player in sources.values():
                player.get_data(item)

            changed = ui.show_model_changes(item)

            if changed and not pretend:
                item.store()
