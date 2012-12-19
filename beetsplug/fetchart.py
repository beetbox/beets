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

"""Fetches album art.
"""
import urllib
import re
import logging
import os
import tempfile

from beets.plugins import BeetsPlugin
from beets.util.artresizer import ArtResizer
from beets import importer
from beets import ui
from beets import util
from beets import config

IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg']
COVER_NAMES = ['cover', 'front', 'art', 'album', 'folder']
CONTENT_TYPES = ('image/jpeg',)
DOWNLOAD_EXTENSION = '.jpg'

log = logging.getLogger('beets')


def _fetch_image(url):
    """Downloads an image from a URL and checks whether it seems to
    actually be an image. If so, returns a path to the downloaded image.
    Otherwise, returns None.
    """
    # Generate a temporary filename with the correct extension.
    fd, fn = tempfile.mkstemp(suffix=DOWNLOAD_EXTENSION)
    os.close(fd)

    log.debug(u'fetchart: downloading art: {0}'.format(url))
    try:
        _, headers = urllib.urlretrieve(url, filename=fn)
    except IOError:
        log.debug(u'error fetching art')
        return

    # Make sure it's actually an image.
    if headers.gettype() in CONTENT_TYPES:
        log.debug(u'fetchart: downloaded art to: {0}'.format(
            util.displayable_path(fn)
        ))
        return fn
    else:
        log.debug(u'fetchart: not an image')


# ART SOURCES ################################################################

# Cover Art Archive.

CAA_URL = 'http://coverartarchive.org/release/{mbid}/front-500.jpg'

def caa_art(release_id):
    """Return the Cover Art Archive URL given a MusicBrainz release ID.
    """
    return CAA_URL.format(mbid=release_id)


# Art from Amazon.

AMAZON_URL = 'http://images.amazon.com/images/P/%s.%02i.LZZZZZZZ.jpg'
AMAZON_INDICES = (1, 2)

def art_for_asin(asin):
    """Generate URLs for an Amazon ID (ASIN) string."""
    for index in AMAZON_INDICES:
        yield AMAZON_URL % (asin, index)


# AlbumArt.org scraper.

AAO_URL = 'http://www.albumart.org/index_detail.php'
AAO_PAT = r'href\s*=\s*"([^>"]*)"[^>]*title\s*=\s*"View larger image"'

def aao_art(asin):
    """Return art URL from AlbumArt.org given an ASIN."""
    # Get the page from albumart.org.
    url = '%s?%s' % (AAO_URL, urllib.urlencode({'asin': asin}))
    try:
        log.debug(u'fetchart: scraping art URL: {0}'.format(url))
        page = urllib.urlopen(url).read()
    except IOError:
        log.debug(u'fetchart: error scraping art page')
        return

    # Search the page for the image URL.
    m = re.search(AAO_PAT, page)
    if m:
        image_url = m.group(1)
        return image_url
    else:
        log.debug(u'fetchart: no image found on page')


# Art from the filesystem.

def art_in_path(path):
    """Look for album art files in a specified directory."""
    if not os.path.isdir(path):
        return

    # Find all files that look like images in the directory.
    images = []
    for fn in os.listdir(path):
        for ext in IMAGE_EXTENSIONS:
            if fn.lower().endswith('.' + ext):
                images.append(fn)

    # Look for "preferred" filenames.
    for fn in images:
        for name in COVER_NAMES:
            if fn.lower().startswith(name):
                log.debug(u'fetchart: using well-named art file {0}'.format(
                    util.displayable_path(fn)
                ))
                return os.path.join(path, fn)

    # Fall back to any image in the folder.
    if images:
        log.debug(u'fetchart: using fallback art file {0}'.format(
            util.displayable_path(images[0])
        ))
        return os.path.join(path, images[0])


# Try each source in turn.

def _source_urls(album):
    """Generate possible source URLs for an album's art. The URLs are
    not guaranteed to work so they each need to be attempted in turn.
    This allows the main `art_for_album` function to abort iteration
    through this sequence early to avoid the cost of scraping when not
    necessary.
    """
    if album.mb_albumid:
        yield caa_art(album.mb_albumid)

    # Amazon and AlbumArt.org.
    if album.asin:
        for url in art_for_asin(album.asin):
            yield url
        yield aao_art(album.asin)

def art_for_album(album, path, maxwidth=None, local_only=False):
    """Given an Album object, returns a path to downloaded art for the
    album (or None if no art is found). If `maxwidth`, then images are
    resized to this maximum pixel size. If `local_only`, then only local
    image files from the filesystem are returned; no network requests
    are made.
    """
    out = None

    # Local art.
    if isinstance(path, basestring):
        out = art_in_path(path)

    # Web art sources.
    if not local_only and not out:
        for url in _source_urls(album):
            if maxwidth:
                url = ArtResizer.shared.proxy_url(maxwidth, url)
            out = _fetch_image(url)
            if out:
                break

    if maxwidth and out:
        out = ArtResizer.shared.resize(maxwidth, out)
    return out


# PLUGIN LOGIC ###############################################################

def batch_fetch_art(lib, albums, force, maxwidth=None):
    """Fetch album art for each of the albums. This implements the manual
    fetchart CLI command.
    """
    for album in albums:
        if album.artpath and not force:
            message = 'has album art'
        else:
            path = art_for_album(album, None, maxwidth)

            if path:
                album.set_art(path, False)
                message = 'found album art'
            else:
                message = 'no art found'
        log.info(u'{0} - {1}: {2}'.format(album.albumartist, album.album,
                                          message))

class FetchArtPlugin(BeetsPlugin):
    def __init__(self):
        super(FetchArtPlugin, self).__init__()

        self.config.add({
            'auto': True,
            'maxwidth': 0,
        })

        # Holds paths to downloaded images between fetching them and
        # placing them in the filesystem.
        self.art_paths = {}

        self.maxwidth = self.config['maxwidth'].get(int)
        if self.config['auto']:
            # Enable two import hooks when fetching is enabled.
            self.import_stages = [self.fetch_art]
            self.register_listener('import_task_files', self.assign_art)

    # Asynchronous; after music is added to the library.
    def fetch_art(self, session, task):
        """Find art for the album being imported."""
        if task.is_album:  # Only fetch art for full albums.
            if task.choice_flag == importer.action.ASIS:
                # For as-is imports, don't search Web sources for art.
                local = True
            elif task.choice_flag == importer.action.APPLY:
                # Search everywhere for art.
                local = False
            else:
                # For any other choices (e.g., TRACKS), do nothing.
                return

            album = session.lib.get_album(task.album_id)
            path = art_for_album(album, task.path, self.maxwidth, local)

            if path:
                self.art_paths[task] = path

    # Synchronous; after music files are put in place.
    def assign_art(self, session, task):
        """Place the discovered art in the filesystem."""
        if task in self.art_paths:
            path = self.art_paths.pop(task)

            album = session.lib.get_album(task.album_id)
            src_removed = config['import']['delete'].get(bool) or \
                          config['import']['move'].get(bool)
            album.set_art(path, not src_removed)
            if src_removed:
                task.prune(path)

    # Manual album art fetching.
    def commands(self):
        cmd = ui.Subcommand('fetchart', help='download album art')
        cmd.parser.add_option('-f', '--force', dest='force',
                              action='store_true', default=False,
                              help='re-download art when already present')
        def func(lib, opts, args):
            batch_fetch_art(lib, lib.albums(ui.decargs(args)), opts.force,
                            self.maxwidth)
        cmd.func = func
        return [cmd]
