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

"""Adds support for ipfs. Requires go-ipfs and a running ipfs daemon
"""
from beets import ui
from beets.plugins import BeetsPlugin

import subprocess
from os import rmdir


class IPFSPlugin(BeetsPlugin):

    def __init__(self):
        super(IPFSPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('ipfs',
                            help='interact with ipfs')
        cmd.parser.add_option('-a', '--add', dest='add',
                                    action='store_true',
                                    help='Add to ipfs')
        cmd.parser.add_option('-g', '--get', dest='get',
                                    action='store_true',
                                    help='Get from ipfs')

        def func(lib, opts, args):
            if opts.add:
                self.ipfs_add(lib.albums(ui.decargs(args)))
            if opts.get:
                self.ipfs_get(lib, ui.decargs(args))

        cmd.func = func
        return [cmd]

    def ipfs_add(self, lib):
        try:
            album_dir = lib.get().item_dir()
        except AttributeError:
            return
        self._log.info('Adding {0} to ipfs', album_dir)
        subprocess.call(["ipfs", "add", "-r", album_dir])

    def ipfs_get(self, lib, _hash):
        try:
            subprocess.check_output(["ipfs", "get", _hash[0]],
                                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            self._log.error('Failed to get {0} from ipfs.\n{1}',
                            _hash[0], err.output)
            return False

        self._log.info('Getting {0} from ipfs', _hash[0])
        imp = ui.commands.TerminalImportSession(lib, loghandler=None,
                                                query=None, paths=_hash)
        imp.run()
        rmdir(_hash[0])
