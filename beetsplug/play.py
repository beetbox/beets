# This file is part of beets.
# Copyright 2014, David Hamp-Gonsalves
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

"""Send the results of a query to the configured music player as a playlist.
"""
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets import config
from beets import ui
from beets import util
import platform
import logging
from tempfile import NamedTemporaryFile

log = logging.getLogger('beets')


def play_music(lib, opts, args):
    """Execute query, create temporary playlist and execute player
    command passing that playlist.
    """

    command = config['play']['command'].get()

    # If a command isn't set then let the OS decide how to open the playlist.
    if not command:
        sys_name = platform.system()
        if sys_name == 'Darwin':
            command = 'open'
        elif sys_name == 'Windows':
            command = 'start'
        else:
            # If not Mac or Win then assume Linux(or posix based).
            command = 'xdg-open'

    # Preform search by album and add folders rather then tracks to playlist.
    if opts.album:
        albums = lib.albums(ui.decargs(args))
        paths = []

        for album in albums:
            paths.append(album.item_dir())
        item_type = 'album'

    # Preform item query and add tracks to playlist.
    else:
        paths = [item.path for item in lib.items(ui.decargs(args))]
        item_type = 'track'

    item_type += 's' if len(paths) > 1 else ''

    if not paths:
        ui.print_(ui.colorize('yellow', 'No {0} to play.'.format(item_type)))
        return

    # Warn user before playing any huge playlists.
    if len(paths) > 100:
        ui.print_(ui.colorize(
            'yellow',
            'You are about to queue {0} {1}.'.format(len(paths), item_type)))

        if ui.input_options(('Continue', 'Abort')) == 'a':
            return

    # Create temporary m3u file to hold our playlist.
    m3u = NamedTemporaryFile('w', suffix='.m3u', delete=False)
    for item in paths:
        m3u.write(item + '\n')
    m3u.close()

    # Invoke the command and log the output.
    output = util.command_output([command, m3u.name])
    if output:
        log.debug(u'Output of {0}: {1}'.format(command, output))

    ui.print_(u'Playing {0} {1}.'.format(len(paths), item_type))


class PlayPlugin(BeetsPlugin):

    def __init__(self):
        super(PlayPlugin, self).__init__()

        config['play'].add({
            'command': None,
        })

    def commands(self):
        play_command = Subcommand(
            'play',
            help='send music to a player as a playlist'
        )
        play_command.parser.add_option(
            '-a', '--album',
            action='store_true', default=False,
            help='query and load albums (as folders) rather than tracks'
        )
        play_command.func = play_music
        return [play_command]
