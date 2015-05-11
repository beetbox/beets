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
import shutil


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
                for album in lib.albums(ui.decargs(args)):
                    self.ipfs_add(album)
                    album.store()

            if opts.get:
                self.ipfs_get(lib, ui.decargs(args))

        cmd.func = func
        return [cmd]

    def ipfs_add(self, lib):
        try:
            album_dir = lib.item_dir()
        except AttributeError:
            return
        self._log.info('Adding {0} to ipfs', album_dir)

        _proc = subprocess.Popen(["ipfs", "add", "-q", "-p", "-r", album_dir],
                                 stdout=subprocess.PIPE)
        count = 0
        while True:
            line = _proc.stdout.readline().strip()

            if line != '':
                if count < len(lib.items()):
                    item = lib.items()[count]
                    self._log.info("item: {0}", line)
                    item.ipfs = line
                    item.store()
                    count += 1
                else:
                    self._log.info("album: {0}", line)
                    lib.ipfs = line
            else:
                break
        return True

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
        shutil.rmtree(_hash[0])
