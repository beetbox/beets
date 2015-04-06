# This file is part of beets.
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

from beets import ui
from beets.plugins import BeetsPlugin

from subprocess import call

class IPFSPlugin(BeetsPlugin):
    def __init__(self):
        super(IPFSPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('ipfs',
                            help='interact with ipfs')
        cmd.parser.add_option('-a', '--add', dest='add',
                                    action='store_true',
                                    help='Add to ipfs')

        def func(lib, opts, args):
            if opts.add:
                ipfs(lib.albums(ui.decargs(args)), action='add')

        cmd.func = func
        return [cmd]

def ipfs(lib, action):
    try:
        album_dir = lib.get().item_dir()
    except AttributeError:
        return
    if action == 'add':
        ui.print_('Adding %s to ipfs' % album_dir)
        call(["ipfs", "add", "-r", album_dir])
