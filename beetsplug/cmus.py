# This file is part of beets.
# Copyright 2011, coolkehon
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

"""Beets command line interface to cmus-remote
an instance of cmus must already be running"""

from beets.plugins import BeetsPlugin
from beets import mediafile
from beets import ui
from beets.ui import Subcommand
from beets.util import syspath, normpath
import subprocess 

cmus_cmd = Subcommand('cmus', help='Interface to a remote cmus instance.')
cmus_cmd.parser.add_option('--socket', action='store_true', dest='socket', help='Connect using socket SOCKET instead of ~/.cmus/socket.')
cmus_cmd.parser.add_option('-p', '--play', action='store_true', help='Start playing.')
cmus_cmd.parser.add_option('-u', '--pause', action='store_true', help='Toggle pause.')
cmus_cmd.parser.add_option('-s', '--stop', action='store_true', help='Stop playing.')
cmus_cmd.parser.add_option('-n', '--next', action='store_true', help='Skip forward in playlist.')
cmus_cmd.parser.add_option('-r', '--prev', action='store_true', help='Skip backward in playlist.')
cmus_cmd.parser.add_option('-R', '--repeat', action='store_true', help='Toggle repeat.')
cmus_cmd.parser.add_option('-S', '--shuffle', action='store_true', help='Toggle shuffle.')
cmus_cmd.parser.add_option('-Q', '--status', action='store_true', help='Get player status information.')
cmus_cmd.parser.add_option('-l', '--library', action='store_true', help='Modify library instead of playlist.')
cmus_cmd.parser.add_option('-P', '--playlist', action='store_true', help='Modify playlist (default).')
cmus_cmd.parser.add_option('-q', '--queue', action='store_true', help='Modify play queue instead of playlist.')
cmus_cmd.parser.add_option('-c', '--clear', action='store_true', help='clear playlist, library (-l) or play queue (-q) before adding songs.')
cmus_cmd.parser.add_option('-a', '--add', action='store_true', help='Add songs to cmus. Similar to beet ls (see beet help ls).')

def cmus_remote(lib, config, opts, args):
    """Execute cmus commands"""

    cmd = ['cmus-remote']
    cmd_args = []

    if opts.socket is not None:
        cmd.append(opts.socket)

    if opts.playlist:
        cmd_args += ['--playlist']
    elif opts.queue:
        cmd_args += ['--queue']
    elif opts.library:
        cmd_args += ['--library']

    if opts.clear:
        subprocess.call(cmd + ['--clear'] + cmd_args)
    
    if opts.add:
        for item in lib.items( ui.make_query(args)):
            subprocess.call(cmd + cmd_args + [item.path])

    if opts.stop:
        subprocess.call(cmd + ['--stop'])
    elif opts.play:
        subprocess.call(cmd + ['--play'])
    elif opts.pause:
        subprocess.call(cmd + ['--pause'])

    if opts.next:
        subprocess.call(cmd + ['--next'])
    elif opts.prev:
        subprocess.call(cmd + ['--prev'])

    if opts.repeat:
        subprocess.call(cmd + ['--repeat'])

    if opts.shuffle:
        subprocess.call(cmd + ['--shuffle'])

    if opts.status:
        subprocess.call(cmd + ['--status'])

cmus_cmd.func = cmus_remote

class CmusRemote(BeetsPlugin):
    def commands(self):
        return [cmus_cmd]

