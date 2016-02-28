# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, David Hamp-Gonsalves
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
from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets import config
from beets import ui
from beets import util
from os.path import relpath
from tempfile import NamedTemporaryFile

# Indicate where arguments should be inserted into the command string.
# If this is missing, they're placed at the end.
ARGS_MARKER = '$args'


class PlayPlugin(BeetsPlugin):

    def __init__(self):
        super(PlayPlugin, self).__init__()

        config['play'].add({
            'command': None,
            'use_folders': False,
            'relative_to': None,
            'raw': False,
            # Backwards compatibility. See #1803 and line 74
            'warning_threshold': -2,
            'warning_treshold': 100,
        })

    def commands(self):
        play_command = Subcommand(
            'play',
            help=u'send music to a player as a playlist'
        )
        play_command.parser.add_album_option()
        play_command.parser.add_option(
            u'-A', u'--args',
            action='store',
            help=u'add additional arguments to the command',
        )
        play_command.func = self.play_music
        return [play_command]

    def play_music(self, lib, opts, args):
        """Execute query, create temporary playlist and execute player
        command passing that playlist, at request insert optional arguments.
        """
        command_str = config['play']['command'].get()
        if not command_str:
            command_str = util.open_anything()
        use_folders = config['play']['use_folders'].get(bool)
        relative_to = config['play']['relative_to'].get()
        raw = config['play']['raw'].get(bool)
        warning_threshold = config['play']['warning_threshold'].get(int)
        # We use -2 as a default value for warning_threshold to detect if it is
        # set or not. We can't use a falsey value because it would have an
        # actual meaning in the configuration of this plugin, and we do not use
        # -1 because some people might use it as a value to obtain no warning,
        # which wouldn't be that bad of a practice.
        if warning_threshold == -2:
            # if warning_threshold has not been set by user, look for
            # warning_treshold, to preserve backwards compatibility. See #1803.
            # warning_treshold has the correct default value of 100.
            warning_threshold = config['play']['warning_treshold'].get(int)

        if relative_to:
            relative_to = util.normpath(relative_to)

        # Add optional arguments to the player command.
        if opts.args:
            if ARGS_MARKER in command_str:
                command_str = command_str.replace(ARGS_MARKER, opts.args)
            else:
                command_str = u"{} {}".format(command_str, opts.args)

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
            if relative_to:
                paths = [relpath(path, relative_to) for path in paths]
            item_type = 'track'

        item_type += 's' if len(selection) > 1 else ''

        if not selection:
            ui.print_(ui.colorize('text_warning',
                                  u'No {0} to play.'.format(item_type)))
            return

        # Warn user before playing any huge playlists.
        if warning_threshold and len(selection) > warning_threshold:
            ui.print_(ui.colorize(
                'text_warning',
                u'You are about to queue {0} {1}.'.format(
                    len(selection), item_type)))

            if ui.input_options(('Continue', 'Abort')) == 'a':
                return

        ui.print_(u'Playing {0} {1}.'.format(len(selection), item_type))
        if raw:
            open_args = paths
        else:
            open_args = [self._create_tmp_playlist(paths)]

        self._log.debug(u'executing command: {} {}', command_str,
                        b' '.join(open_args))
        try:
            util.interactive_open(open_args, command_str)
        except OSError as exc:
            raise ui.UserError(
                "Could not play the query: {0}".format(exc))

    def _create_tmp_playlist(self, paths_list):
        """Create a temporary .m3u file. Return the filename.
        """
        m3u = NamedTemporaryFile('w', suffix='.m3u', delete=False)
        for item in paths_list:
            m3u.write(item + b'\n')
        m3u.close()
        return m3u.name
