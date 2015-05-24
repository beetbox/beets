# This file is part of beets.
# Copyright 2015, Adrian Sampson.
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

"""Allows beets to embed album art into file metadata."""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import os.path

from beets.plugins import BeetsPlugin
from beets import ui
from beets.ui import decargs
from beets.util import syspath, normpath, displayable_path, bytestring_path
from beets.util.artresizer import ArtResizer
from beets import config
from beets import art


class EmbedCoverArtPlugin(BeetsPlugin):
    """Allows albumart to be embedded into the actual files.
    """
    def __init__(self):
        super(EmbedCoverArtPlugin, self).__init__()
        self.config.add({
            'maxwidth': 0,
            'auto': True,
            'compare_threshold': 0,
            'ifempty': False,
        })

        if self.config['maxwidth'].get(int) and not ArtResizer.shared.local:
            self.config['maxwidth'] = 0
            self._log.warning(u"ImageMagick or PIL not found; "
                              u"'maxwidth' option ignored")
        if self.config['compare_threshold'].get(int) and not \
                ArtResizer.shared.can_compare:
            self.config['compare_threshold'] = 0
            self._log.warning(u"ImageMagick 6.8.7 or higher not installed; "
                              u"'compare_threshold' option ignored")

        self.register_listener('art_set', self.process_album)

    def commands(self):
        # Embed command.
        embed_cmd = ui.Subcommand(
            'embedart', help='embed image files into file metadata'
        )
        embed_cmd.parser.add_option(
            '-f', '--file', metavar='PATH', help='the image file to embed'
        )
        maxwidth = self.config['maxwidth'].get(int)
        compare_threshold = self.config['compare_threshold'].get(int)
        ifempty = self.config['ifempty'].get(bool)

        def embed_func(lib, opts, args):
            if opts.file:
                imagepath = normpath(opts.file)
                if not os.path.isfile(syspath(imagepath)):
                    raise ui.UserError(u'image file {0} not found'.format(
                        displayable_path(imagepath)
                    ))
                for item in lib.items(decargs(args)):
                    art.embed_item(self._log, item, imagepath, maxwidth, None,
                                   compare_threshold, ifempty)
            else:
                for album in lib.albums(decargs(args)):
                    art.embed_album(self._log, album, maxwidth, False,
                                    compare_threshold, ifempty)

        embed_cmd.func = embed_func

        # Extract command.
        extract_cmd = ui.Subcommand('extractart',
                                    help='extract an image from file metadata')
        extract_cmd.parser.add_option('-o', dest='outpath',
                                      help='image output file')
        extract_cmd.parser.add_option('-n', dest='filename',
                                      help='image filename to create for all '
                                           'matched albums')
        extract_cmd.parser.add_option('-a', dest='associate',
                                      action='store_true',
                                      help='associate the extracted images '
                                           'with the album')

        def extract_func(lib, opts, args):
            if opts.outpath:
                art.extract_first(self._log, normpath(opts.outpath),
                                  lib.items(decargs(args)))
            else:
                filename = bytestring_path(opts.filename or
                                           config['art_filename'].get())
                if os.path.dirname(filename) != '':
                    self._log.error(u"Only specify a name rather than a path "
                                    u"for -n")
                    return
                for album in lib.albums(decargs(args)):
                    artpath = normpath(os.path.join(album.path, filename))
                    artpath = art.extract_first(self._log, artpath,
                                                album.items())
                    if artpath and opts.associate:
                        album.set_art(artpath)
                        album.store()
        extract_cmd.func = extract_func

        # Clear command.
        clear_cmd = ui.Subcommand('clearart',
                                  help='remove images from file metadata')

        def clear_func(lib, opts, args):
            art.clear(self._log, lib, decargs(args))
        clear_cmd.func = clear_func

        return [embed_cmd, extract_cmd, clear_cmd]

    def process_album(self, album):
        """Automatically embed art after art has been set
        """
        if self.config['auto'] and config['import']['write']:
            max_width = self.config['maxwidth'].get(int)
            art.embed_album(self._log, album, max_width, True,
                            self.config['compare_threshold'].get(int),
                            self.config['ifempty'].get(bool))
