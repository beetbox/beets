# This file is part of beets.
# Copyright 2014, Adrian Sampson.
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
import os.path
import logging
import imghdr
import subprocess
import platform
from tempfile import NamedTemporaryFile

from beets.plugins import BeetsPlugin
from beets import mediafile
from beets import ui
from beets.ui import decargs
from beets.util import syspath, normpath, displayable_path
from beets.util.artresizer import ArtResizer
from beets import config


log = logging.getLogger('beets')


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
            log.warn(u"embedart: ImageMagick or PIL not found; "
                     u"'maxwidth' option ignored")
        if self.config['compare_threshold'].get(int) and not \
                ArtResizer.shared.can_compare:
            self.config['compare_threshold'] = 0
            log.warn(u"embedart: ImageMagick 6.8.7 or higher not installed; "
                     u"'compare_threshold' option ignored")

    def commands(self):
        # Embed command.
        embed_cmd = ui.Subcommand(
            'embedart', help='embed image files into file metadata'
        )
        embed_cmd.parser.add_option(
            '-f', '--file', metavar='PATH', help='the image file to embed'
        )
        maxwidth = config['embedart']['maxwidth'].get(int)
        compare_threshold = config['embedart']['compare_threshold'].get(int)
        ifempty = config['embedart']['ifempty'].get(bool)

        def embed_func(lib, opts, args):
            if opts.file:
                imagepath = normpath(opts.file)
                for item in lib.items(decargs(args)):
                    embed_item(item, imagepath, maxwidth, None,
                               compare_threshold, ifempty)
            else:
                for album in lib.albums(decargs(args)):
                    embed_album(album, maxwidth)

        embed_cmd.func = embed_func

        # Extract command.
        extract_cmd = ui.Subcommand('extractart',
                                    help='extract an image from file metadata')
        extract_cmd.parser.add_option('-o', dest='outpath',
                                      help='image output file')

        def extract_func(lib, opts, args):
            outpath = normpath(opts.outpath or 'cover')
            item = lib.items(decargs(args)).get()
            extract(outpath, item)
        extract_cmd.func = extract_func

        # Clear command.
        clear_cmd = ui.Subcommand('clearart',
                                  help='remove images from file metadata')

        def clear_func(lib, opts, args):
            clear(lib, decargs(args))
        clear_cmd.func = clear_func

        return [embed_cmd, extract_cmd, clear_cmd]


@EmbedCoverArtPlugin.listen('album_imported')
def album_imported(lib, album):
    """Automatically embed art into imported albums.
    """
    if album.artpath and config['embedart']['auto']:
        embed_album(album, config['embedart']['maxwidth'].get(int), True)


def embed_item(item, imagepath, maxwidth=None, itempath=None,
               compare_threshold=0, ifempty=False, as_album=False):
    """Embed an image into the item's media file.
    """
    if compare_threshold:
        if not check_art_similarity(item, imagepath, compare_threshold):
            log.warn(u'Image not similar; skipping.')
            return
    if ifempty:
        art = get_art(item)
        if not art:
            pass
        else:
            log.debug(u'embedart: media file contained art already {0}'.format(
                displayable_path(imagepath)
            ))
            return
    if maxwidth and not as_album:
        imagepath = resize_image(imagepath, maxwidth)

    try:
        log.debug(u'embedart: embedding {0}'.format(
            displayable_path(imagepath)
        ))
        item['images'] = [_mediafile_image(imagepath, maxwidth)]
    except IOError as exc:
        log.error(u'embedart: could not read image file: {0}'.format(exc))
    else:
        # We don't want to store the image in the database.
        item.try_write(itempath)
        del item['images']


def embed_album(album, maxwidth=None, quiet=False):
    """Embed album art into all of the album's items.
    """
    imagepath = album.artpath
    if not imagepath:
        log.info(u'No album art present: {0} - {1}'.
                 format(album.albumartist, album.album))
        return
    if not os.path.isfile(syspath(imagepath)):
        log.error(u'Album art not found at {0}'
                  .format(displayable_path(imagepath)))
        return
    if maxwidth:
        imagepath = resize_image(imagepath, maxwidth)

    log.log(
        logging.DEBUG if quiet else logging.INFO,
        u'Embedding album art into {0.albumartist} - {0.album}.'.format(album),
    )

    for item in album.items():
        embed_item(item, imagepath, maxwidth, None,
                   config['embedart']['compare_threshold'].get(int),
                   config['embedart']['ifempty'].get(bool), as_album=True)


def resize_image(imagepath, maxwidth):
    """Returns path to an image resized to maxwidth.
    """
    log.info(u'Resizing album art to {0} pixels wide'
             .format(maxwidth))
    imagepath = ArtResizer.shared.resize(maxwidth, syspath(imagepath))
    return imagepath


def check_art_similarity(item, imagepath, compare_threshold):
    """A boolean indicating if an image is similar to embedded item art.
    """
    with NamedTemporaryFile(delete=True) as f:
        art = extract(f.name, item)

        if art:
            # Converting images to grayscale tends to minimize the weight
            # of colors in the diff score
            cmd = 'convert {0} {1} -colorspace gray MIFF:- | ' \
                  'compare -metric PHASH - null:'.format(syspath(imagepath),
                                                         syspath(art))

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    close_fds=platform.system() != 'Windows',
                                    shell=True)
            stdout, stderr = proc.communicate()
            if proc.returncode:
                if proc.returncode != 1:
                    log.warn(u'embedart: IM phashes compare failed for {0}, \
                   {1}'.format(displayable_path(imagepath),
                               displayable_path(art)))
                    return
                phashDiff = float(stderr)
            else:
                phashDiff = float(stdout)

            log.info(u'embedart: compare PHASH score is {0}'.format(phashDiff))
            if phashDiff > compare_threshold:
                return False

    return True


def _mediafile_image(image_path, maxwidth=None):
    """Return a `mediafile.Image` object for the path.
    """

    with open(syspath(image_path), 'rb') as f:
        data = f.read()
    return mediafile.Image(data, type=mediafile.ImageType.front)


def get_art(item):
    # Extract the art.
    try:
        mf = mediafile.MediaFile(syspath(item.path))
    except mediafile.UnreadableFileError as exc:
        log.error(u'Could not extract art from {0}: {1}'.format(
            displayable_path(item.path), exc
        ))
        return

    return mf.art

# 'extractart' command.


def extract(outpath, item):
    if not item:
        log.error(u'No item matches query.')
        return

    art = get_art(item)

    if not art:
        log.error(u'No album art present in {0} - {1}.'
                  .format(item.artist, item.title))
        return

    # Add an extension to the filename.
    ext = imghdr.what(None, h=art)
    if not ext:
        log.error(u'Unknown image type.')
        return
    outpath += '.' + ext

    log.info(u'Extracting album art from: {0.artist} - {0.title} '
             u'to: {1}'.format(item, displayable_path(outpath)))
    with open(syspath(outpath), 'wb') as f:
        f.write(art)
    return outpath


# 'clearart' command.

def clear(lib, query):
    log.info(u'Clearing album art from items:')
    for item in lib.items(query):
        log.info(u'{0} - {1}'.format(item.artist, item.title))
        try:
            mf = mediafile.MediaFile(syspath(item.path),
                                     config['id3v23'].get(bool))
        except mediafile.UnreadableFileError as exc:
            log.error(u'Could not clear art from {0}: {1}'.format(
                displayable_path(item.path), exc
            ))
            continue
        del mf.art
        mf.save()
