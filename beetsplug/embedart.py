# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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
import logging
import imghdr

from beets.plugins import BeetsPlugin
from beets import mediafile
from beets import ui
from beets.ui import decargs
from beets.util import syspath, normpath
from beets.util.artresizer import ArtResizer
from beets import config

log = logging.getLogger('beets')

def _embed(path, items, maxwidth=0):
    """Embed an image file, located at `path`, into each item.
    """
    if maxwidth:
        path = ArtResizer.shared.resize(maxwidth, syspath(path))

    data = open(syspath(path), 'rb').read()
    kindstr = imghdr.what(None, data)
    if kindstr not in ('jpeg', 'png'):
        log.error('A file of type %s is not allowed as coverart.' % kindstr)
        return

    # Add art to each file.
    log.debug('Embedding album art.')

    for item in items:
        try:
            f = mediafile.MediaFile(syspath(item.path))
        except mediafile.UnreadableFileError as exc:
            log.warn('Could not embed art in {0}: {1}'.format(
                repr(item.path), exc
            ))
            continue
        f.art = data
        f.save()

class EmbedCoverArtPlugin(BeetsPlugin):
    """Allows albumart to be embedded into the actual files.
    """
    def __init__(self):
        super(EmbedCoverArtPlugin, self).__init__()
        self.config.add({
            'maxwidth': 0,
            'auto': True,
        })
        if self.config['maxwidth'].get(int) and \
                not ArtResizer.shared.local:
            self.config['maxwidth'] = 0
            log.warn("embedart: ImageMagick or PIL not found; "
                     "'maxwidth' option ignored")

    def commands(self):
        # Embed command.
        embed_cmd = ui.Subcommand('embedart',
            help='embed image files into file metadata')
        embed_cmd.parser.add_option('-f', '--file', metavar='PATH',
            help='the image file to embed')
        def embed_func(lib, opts, args):
            if opts.file:
                imagepath = normpath(opts.file)
                embed(lib, imagepath, decargs(args))
            else:
                embed_current(lib, decargs(args))
        embed_cmd.func = embed_func

        # Extract command.
        extract_cmd = ui.Subcommand('extractart',
                                    help='extract an image from file metadata')
        extract_cmd.parser.add_option('-o', dest='outpath',
                                      help='image output file')
        def extract_func(lib, opts, args):
            outpath = normpath(opts.outpath or 'cover')
            extract(lib, outpath, decargs(args))
        extract_cmd.func = extract_func

        # Clear command.
        clear_cmd = ui.Subcommand('clearart',
                                  help='remove images from file metadata')
        def clear_func(lib, opts, args):
            clear(lib, decargs(args))
        clear_cmd.func = clear_func

        return [embed_cmd, extract_cmd, clear_cmd]

# "embedart" command with --file argument.
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
    _embed(imagepath, album.items(),
           config['embedart']['maxwidth'].get(int))

# "embedart" command without explicit file.
def embed_current(lib, query):
    albums = lib.albums(query)
    for album in albums:
        if not album.artpath:
            log.info(u'No album art present: {0} - {1}'.
                     format(album.albumartist, album.album))
            continue

        log.info(u'Embedding album art into {0} - {1}'.
                 format(album.albumartist, album.album))
        _embed(album.artpath, album.items(),
               config['embedart']['maxwidth'].get(int))

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
    try:
        mf = mediafile.MediaFile(syspath(item.path))
    except mediafile.UnreadableFileError as exc:
        log.error('Could not extract art from {0}: {1}'.format(
            repr(item.path), exc
        ))
        return

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
        try:
            mf = mediafile.MediaFile(syspath(item.path))
        except mediafile.UnreadableFileError as exc:
            log.error('Could not clear art from {0}: {1}'.format(
                repr(item.path), exc
            ))
            continue
        mf.art = None
        mf.save()

# Automatically embed art into imported albums.
@EmbedCoverArtPlugin.listen('album_imported')
def album_imported(lib, album):
    if album.artpath and config['embedart']['auto']:
        _embed(album.artpath, album.items(),
               config['embedart']['maxwidth'].get(int))
