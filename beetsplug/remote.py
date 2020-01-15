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
import requests

from beets import config, ui
from beets.ui import Subcommand
from beetsplug.play import PlayPlugin, play


class RemotePlugin(PlayPlugin):
    def __init__(self):
        super(RemotePlugin, self).__init__()

        config['play'].add({
            'servers': {
                'local': 'http://127.0.0.1:8337'
            }
        })

    def commands(self):
        play_commands = super().commands()
        remote_command = Subcommand(
            'remote',
            help=u'play from remote server'
        )
        remote_command.parser.add_album_option()
        remote_command.parser.add_option(
            u'-A', u'--args',
            action='store',
            help=u'add additional arguments to the command',
        )
        remote_command.parser.add_option(
            u'-y', u'--yes',
            action="store_true",
            help=u'skip the warning threshold',
        )
        remote_command.parser.add_option(
            u'-s', u'--server',
            action='store',
            help=u'remote server label',
        )
        remote_command.func = self._remote_command
        return play_commands + [remote_command]

    def _remote_command(self, lib, opts, args):
        server_url = config['play']['servers'][opts.server].get(str)
        query = ' '.join(ui.decargs(args))

        if opts.album:
            item_type = 'remote album'
            url = server_url + '/album/query/' + query
            album_response = requests.get(url).json()

            if not album_response['results']:
                ui.print_(ui.colorize('text_warning',
                                      u'No {0} to play.'.format(item_type)))
                return

            album_id = str(album_response['results'][0]['id'])
            url = server_url + '/item/query/' + 'album_id:' + album_id
            item_response = requests.get(url).json()
        else:
            item_type = 'remote track'
            if args:
                url = server_url + '/item/query/' + query
            else:
                url = server_url + '/item/' + query
            item_response = requests.get(url).json()

        selection = [
            server_url + '/item/' + str(result['id']) + '/file'
            for result in
            item_response.get('results') or item_response.get('items') or []
        ]

        if not selection:
            ui.print_(ui.colorize('text_warning',
                                  u'No {0} to play.'.format(item_type)))
            return

        open_args = self._playlist_or_paths([link.encode() for link in selection])
        command_str = self._command_str(opts.args)

        play(command_str, selection, None, open_args, self._log, item_type)
