# This file is a plugin on beets.
# Copyright (c) <2013> David Hamp-Gonsalves
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

"""sends the results of a query to the configured music player as a playlist"""

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets import config
from beets import ui

import subprocess
import os
from tempfile import NamedTemporaryFile


def check_config():

    if not config['play']['command'].get():
        ui.print_(ui.colorize('red', 'no player command is set. Verify configuration.'))
        return

def play_music(lib, opts, args):
    """execute query, create temporary playlist and execute player command passing that playlist"""
    check_config()

    #get the music player command to launch and pass playlist to
    command = config['play']['command'].get()
    isDebug = config['play']['debug'].get()

    if opts.album: #search by album
    	#get all the albums to be added to playlist
        albums = lib.albums(ui.decargs(args))
        paths = []

        for album in albums:
            paths.append(album.item_dir())
        itemType = 'album'

    else: #search by item name
        paths = [item.path for item in lib.items(ui.decargs(args))]
        itemType = 'track'

    if len(paths) > 1:
        itemType += 's'

    if not paths:
    	ui.print_(ui.colorize('yellow', 'no {0} to play.'.format(itemType)))
    	return

    #warn user before playing any huge playlists
    if len(paths) > 100:
    	ui.print_(ui.colorize('yellow', 'do you really want to play {0} {1}?'.format(len(paths), itemType)))
    	opts = ('Continue', 'Abort')
    	if ui.input_options(opts) == 'a':
    		return

    m3u = NamedTemporaryFile('w', suffix='.m3u', delete=False)
    for item in paths:
        m3u.write(item + '\n')
    m3u.close()

    #prevent output from player poluting our console(unless debug is on)
    if not isDebug:
        FNULL = open(os.devnull, 'w')
        subprocess.Popen([command, m3u.name], stdout=FNULL, stderr=subprocess.STDOUT)
        FNULL.close()
    else:
        subprocess.Popen([command, m3u.name])

    ui.print_('playing {0} {1}.'.format(len(paths), itemType))
    
        
class PlayPlugin(BeetsPlugin):
    
    def __init__(self):
        super(PlayPlugin, self).__init__()

        config['play'].add({
            'command': None,
            'debug': False
        })

    def commands(self):
    	play_command = Subcommand('play', help='send query results to music player as playlist.')
    	play_command.parser.add_option('-a', '--album',
                                            action='store_true', default=False,
                                            help='query and load albums(folders) rather then tracks.')
    	play_command.func = play_music
    	return [play_command]
