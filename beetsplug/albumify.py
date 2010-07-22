# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

"""Provides the albumify command, which "upgrades" databases created
with beets <1.0b3. It walks through the database and groups all items
not yet associated with albums into albums based on metadata.
"""

from collections import defaultdict

from beets.plugins import BeetsPlugin
import beets.ui

# Main functionality.
def albumify(lib):
    # Associate every (albumless) item with a unique artist/album
    # pair.
    albums = defaultdict(list)
    for item in lib.get():
        if item.album_id is None:
            albums[(item.artist, item.album)].append(item)
    
    # Create an album for each group.
    for (artist, album), items in albums.items():
        beets.ui.print_('%s - %s (%i tracks)' % (artist, album, len(items)))
        lib.add_album(items)

# Plugin hook.
class AlbumifyPlugin(BeetsPlugin):
    def commands(self):
        cmd = beets.ui.Subcommand('albumify', help='group items into albums')
        def func(lib, config, opts, args):
            if args:
                raise beets.ui.UserError('albumify takes no arguments')
            albumify(lib)
            lib.save()
        cmd.func = func
        return [cmd]
