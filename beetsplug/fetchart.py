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

from beets.plugins import BeetsPlugin
from beets import importer
from beets import ui

IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg']
COVER_NAMES = ['cover', 'front', 'art', 'album', 'folder']
CONTENT_TYPES = ('image/jpeg',)

log = logging.getLogger('beets')


# ART SOURCES ################################################################

def _fetch_image(url):
    """Downloads an image from a URL and checks whether it seems to
    actually be an image. If so, returns a path to the downloaded image.
    Otherwise, returns None.
    """
    log.debug('Downloading art: %s' % url)
    try:
        fn, headers = urllib.urlretrieve(url)
    except IOError:
        log.debug('error fetching art')
        return

    # Make sure it's actually an image.
    if headers.gettype() in CONTENT_TYPES:
        log.debug('Downloaded art to: %s' % fn)
        return fn
    else:
        log.debug('Not an image.')


# Cover Art Archive.

CAA_URL = 'http://coverartarchive.org/release/{mbid}/front-500.jpg'

def caa_art(release_id):
    """Fetch album art from the Cover Art Archive given a MusicBrainz
    release ID.
    """
    url = CAA_URL.format(mbid=release_id)
    return _fetch_image(url)


# Art from Amazon.

AMAZON_URL = 'http://images.amazon.com/images/P/%s.%02i.LZZZZZZZ.jpg'
AMAZON_INDICES = (1, 2)

def art_for_asin(asin):
    """Fetch art for an Amazon ID (ASIN) string."""
    for index in AMAZON_INDICES:
        # Fetch the image.
        url = AMAZON_URL % (asin, index)
        fn = _fetch_image(url)
        if fn:
            return fn


# AlbumArt.org scraper.

AAO_URL = 'http://www.albumart.org/index_detail.php'
AAO_PAT = r'href\s*=\s*"([^>"]*)"[^>]*title\s*=\s*"View larger image"'

def aao_art(asin):
    """Fetch art from AlbumArt.org."""
    # Get the page from albumart.org.
    url = '%s?%s' % (AAO_URL, urllib.urlencode({'asin': asin}))
    try:
        log.debug('Scraping art URL: %s' % url)
        page = urllib.urlopen(url).read()
    except IOError:
        log.debug('Error scraping art page')
        return

    # Search the page for the image URL.
    m = re.search(AAO_PAT, page)
    if m:
        image_url = m.group(1)
        return _fetch_image(image_url)
    else:
        log.debug('No image found on page')


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
                log.debug('Using well-named art file %s' % fn)
                return os.path.join(path, fn)

    # Fall back to any image in the folder.
    if images:
        log.debug('Using fallback art file %s' % images[0])
        return os.path.join(path, images[0])


# Try each source in turn.

def art_for_album(album, path, local_only=False):
    """Given an Album object, returns a path to downloaded art for the
    album (or None if no art is found). If `local_only`, then only local
    image files from the filesystem are returned; no network requests
    are made.
    """
    # Local art.
    if isinstance(path, basestring):
        out = art_in_path(path)
        if out:
            return out
    if local_only:
        # Abort without trying Web sources.
        return

    # CoverArtArchive.org.
    if album.mb_albumid:
        log.debug('Fetching album art for MBID {0}.'.format(album.mb_albumid))
        out = caa_art(album.mb_albumid)
        if out:
            return out

    # Amazon and AlbumArt.org.
    if album.asin:
        log.debug('Fetching album art for ASIN %s.' % album.asin)
        out = art_for_asin(album.asin)
        if out:
            return out
        return aao_art(album.asin)

    # All sources failed.
    log.debug('No ASIN available: no art found.')
    return None


# PLUGIN LOGIC ###############################################################

def batch_fetch_art(lib, albums, force):
    """Fetch album art for each of the albums. This implements the manual
    fetchart CLI command.
    """
    for album in albums:
        if album.artpath and not force:
            message = 'has album art'
        else:
            path = art_for_album(album, None)
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

        self.autofetch = True

        # Holds paths to downloaded images between fetching them and
        # placing them in the filesystem.
        self.art_paths = {}

    def configure(self, config):
        self.autofetch = ui.config_val(config, 'fetchart',
                                       'autofetch', True, bool)
        if self.autofetch:
            # Enable two import hooks when fetching is enabled.
            self.import_stages = [self.fetch_art]
            self.register_listener('import_task_files', self.assign_art)

    # Asynchronous; after music is added to the library.
    def fetch_art(self, config, task):
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

            album = config.lib.get_album(task.album_id)
            path = art_for_album(album, task.path, local_only=local)
            if path:
                self.art_paths[task] = path

    # Synchronous; after music files are put in place.
    def assign_art(self, config, task):
        """Place the discovered art in the filesystem."""
        if task in self.art_paths:
            path = self.art_paths.pop(task)

            album = config.lib.get_album(task.album_id)
            album.set_art(path, not (config.delete or config.move))

            if config.delete or config.move:
                task.prune(path)

    # Manual album art fetching.
    def commands(self):
        cmd = ui.Subcommand('fetchart', help='download album art')
        cmd.parser.add_option('-f', '--force', dest='force',
                              action='store_true', default=False,
                              help='re-download art when already present')
        def func(lib, config, opts, args):
            batch_fetch_art(lib, lib.albums(ui.decargs(args)), opts.force)
        cmd.func = func
        return [cmd]
