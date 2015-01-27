# This file is part of beets.
# Copyright 2015, Matt Lichtenberg.
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

"""Creates freedesktop.org-compliant .directory files on an album level.
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.ui import decargs

import os


def create_file(albumpath, artfile):
    file_contents = "[Desktop Entry]\nIcon=./" + artfile
    outfilename = os.path.join(albumpath, ".directory")

    if not os.path.exists(outfilename):
        file = open(outfilename, 'w')
        file.write(file_contents)
        file.close()


class FreedesktopPlugin(BeetsPlugin):
    def __init__(self):
        super(FreedesktopPlugin, self).__init__()
        self.config.add({
            'auto': False
        })
        self.register_listener('album_imported', self.imported)

    def commands(self):
        freedesktop_command = Subcommand("freedesktop",
                                         help="Create .directory files")
        freedesktop_command.func = self.process_query
        return [freedesktop_command]

    def imported(self, lib, album):
        automatic = self.config['auto'].get(bool)
        if not automatic:
            return
        self.process_album(album)

    def process_query(self, lib, opts, args):
        for album in lib.albums(decargs(args)):
            self.process_album(album)

    def process_album(self, album):
        albumpath = album.item_dir()
        if album.artpath:
            fullartpath = album.artpath
            artfile = os.path.split(fullartpath)[1]
            create_file(albumpath, artfile)
        else:
            self._log.debug(u'album has no art')
