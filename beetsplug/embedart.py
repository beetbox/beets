# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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
from __future__ import with_statement

import logging
import imghdr

from beets.plugins import BeetsPlugin
from beets import mediafile
from beets import ui
from beets.ui import decargs
from beets.util import syspath, normpath

log = logging.getLogger('beets')

def _embed(path, items):
    """Embed an image file, located at `path`, into each item.
    """
    data = open(syspath(path), 'rb').read()
    kindstr = imghdr.what(None, data)
    if kindstr not in ('jpeg', 'png'):
        log.error('A file of type %s is not allowed as coverart.' % kindstr)
        return

    # Add art to each file.
    log.debug('Embedding album art.')
    for item in items:
        f = mediafile.MediaFile(syspath(item.path))
        f.art = data
        f.save()

options = {
    'autoembed': True,
}
class EmbedCoverArtPlugin(BeetsPlugin):
    """Allows albumart to be embedded into the actual files."""
    def configure(self, config):
        options['autoembed'] = \
            ui.config_val(config, 'embedart', 'autoembed', True, bool)

    def commands(self):
        # Embed command.
        embed_cmd = ui.Subcommand('embedart',
                                  help='embed an image file into file metadata')
        def embed_func(lib, config, opts, args):
            if not args:
                raise ui.UserError('specify an image file')
            imagepath = normpath(args.pop(0))
            embed(lib, imagepath, decargs(args))
        embed_cmd.func = embed_func

        # Extract command.
        extract_cmd = ui.Subcommand('extractart',
                                    help='extract an image from file metadata')
        extract_cmd.parser.add_option('-o', dest='outpath',
                                      help='image output file')
        def extract_func(lib, config, opts, args):
            outpath = normpath(opts.outpath or 'cover')
            extract(lib, outpath, decargs(args))
        extract_cmd.func = extract_func

        # Clear command.
        clear_cmd = ui.Subcommand('clearart',
                                  help='remove images from file metadata')
        def clear_func(lib, config, opts, args):
            clear(lib, decargs(args))
        clear_cmd.func = clear_func

        return [embed_cmd, extract_cmd, clear_cmd]

# "embedart" command.
def embed(lib, imagepath, query):
    albums = lib.albums(query)
    for i_album in albums:
        album = i_album
        break
    else:
        log.error('No album matches query.')
        return

    log.info('Embedding album art into %s - %s.' % \
             (album.albumartist, album.album))
    _embed(imagepath, album.items())

# "extractart" command.
def extract(lib, outpath, query):
    items = lib.items(query)
    for i_item in items:
        item = i_item
        break
    else:
        log.error('No item matches query.')
        return

    # Extract the art.
    mf = mediafile.MediaFile(syspath(item.path))
    art = mf.art
    if not art:
        log.error('No album art present in %s - %s.' %
                  (item.artist, item.title))
        return

    # Add an extension to the filename.
    ext = imghdr.what(None, h=art)
    if not ext:
        log.error('Unknown image type.')
        return
    outpath += '.' + ext

    log.info('Extracting album art from: %s - %s\n'
             'To: %s' % \
             (item.artist, item.title, outpath))
    with open(syspath(outpath), 'wb') as f:
        f.write(art)

# "clearart" command.
def clear(lib, query):
    log.info('Clearing album art from items:')
    for item in lib.items(query):
        log.info(u'%s - %s' % (item.artist, item.title))
        mf = mediafile.MediaFile(syspath(item.path))
        mf.art = None
        mf.save()

# Automatically embed art into imported albums.
@EmbedCoverArtPlugin.listen('album_imported')
def album_imported(lib, album, config):
    if album.artpath and options['autoembed']:
        _embed(album.artpath, album.items())
