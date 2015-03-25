# This file is part of beets.
# Copyright 2015, David Hamp-Gonsalves
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
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets import config
from beets import ui
from beets import util
from os.path import relpath
from tempfile import NamedTemporaryFile


class PlayPlugin(BeetsPlugin):

    def __init__(self):
        super(PlayPlugin, self).__init__()

        config['play'].add({
            'command': None,
            'use_folders': False,
            'relative_to': None,
        })

    def commands(self):
        play_command = Subcommand(
            'play',
            help='send music to a player as a playlist'
        )
        play_command.parser.add_album_option()
        play_command.func = self.play_music
        return [play_command]

    def play_music(self, lib, opts, args):
        """Execute query, create temporary playlist and execute player
        command passing that playlist.
        """
        command_str = config['play']['command'].get()
        use_folders = config['play']['use_folders'].get(bool)
        relative_to = config['play']['relative_to'].get()
        if relative_to:
            relative_to = util.normpath(relative_to)

        # Perform search by album and add folders rather than tracks to
        # playlist.
        if opts.album:
            selection = lib.albums(ui.decargs(args))
            paths = []

            sort = lib.get_default_album_sort()
            for album in selection:
                if use_folders:
                    paths.append(album.item_dir())
                else:
                    paths.extend(item.path
                                 for item in sort.sort(album.items()))
            item_type = 'album'

        # Perform item query and add tracks to playlist.
        else:
            selection = lib.items(ui.decargs(args))
            paths = [item.path for item in selection]
            item_type = 'track'

        item_type += 's' if len(selection) > 1 else ''

        if not selection:
            ui.print_(ui.colorize('text_warning',
                                  'No {0} to play.'.format(item_type)))
            return

        # Warn user before playing any huge playlists.
        if len(selection) > 100:
            ui.print_(ui.colorize(
                'text_warning',
                'You are about to queue {0} {1}.'.format(len(selection),
                                                         item_type)
            ))

            if ui.input_options(('Continue', 'Abort')) == 'a':
                return

        # Create temporary m3u file to hold our playlist.
        m3u = NamedTemporaryFile('w', suffix='.m3u', delete=False)
        for item in paths:
            if relative_to:
                m3u.write(relpath(item, relative_to) + b'\n')
            else:
                m3u.write(item + b'\n')
        m3u.close()

        ui.print_(u'Playing {0} {1}.'.format(len(selection), item_type))

        try:
            util.interactive_open(m3u.name, command_str)
        except OSError as exc:
            raise ui.UserError("Could not play the music playlist: "
                               "{0}".format(exc))
        finally:
            util.remove(m3u.name)
