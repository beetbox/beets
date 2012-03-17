# This file is part of beets.
# Copyright 2012, Adrian Sampson.
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

"""Write paths of imported files in a m3u file to ease later import in a music
player.
"""

from __future__ import with_statement 
import os

from beets import ui
from beets.plugins import BeetsPlugin
from beets.util import normpath

class m3uPlugin(BeetsPlugin):
    def configure(self, config):
        global M3U_FILENAME
        M3U_FILENAME = ui.config_val(config, 'm3uupdate', 'm3u', None)

        if not M3U_FILENAME:
            M3U_FILENAME = os.path.join(
                           ui.config_val(config, 'beets', 'directory', '.'),
                           'imported.m3u')
        M3U_FILENAME = normpath(M3U_FILENAME)
        m3u_dir = os.path.dirname(M3U_FILENAME)
        if not os.path.exists(m3u_dir):
            os.makedirs(m3u_dir)

@m3uPlugin.listen('album_imported')
def album_imported(lib, album, config): 
    with open(M3U_FILENAME, 'a') as f:
        for item in album.items():  
            f.write(os.path.relpath(item.path, 
                                    os.path.dirname(M3U_FILENAME)) + '\n')

@m3uPlugin.listen('item_imported')
def item_imported(lib, item, config):
    with open(M3U_FILENAME, 'a') as f:
            f.write(os.path.relpath(item.path, 
                                    os.path.dirname(M3U_FILENAME)) + '\n')

