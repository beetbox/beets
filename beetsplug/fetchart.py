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

CAA_URL = 'http://coverartarchive.org/release/{mbid}/front-500'

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

def art_for_album(album, path):
    """Given an AlbumInfo object, returns a path to downloaded art for
    the album (or None if no art is found).
    """
    if isinstance(path, basestring):
        out = art_in_path(path)
        if out:
            return out

    if album.album_id:
        log.debug('Fetching album art for MBID {0}.'.format(album.album_id))
        out = caa_art(album.album_id)
        if out:
            return out

    if album.asin:
        log.debug('Fetching album art for ASIN %s.' % album.asin)
        out = art_for_asin(album.asin)
        if out:
            return out
        return aao_art(album.asin)
    else:
        log.debug('No ASIN available: no art found.')
        return None


# PLUGIN LOGIC ###############################################################

class FetchArtPlugin(BeetsPlugin):
    def __init__(self):
        super(FetchArtPlugin, self).__init__()
        self.import_stages = [self.fetch_art]
        self.register_listener('import_task_files', self.assign_art)

        # Holds paths to downloaded images between fetching them and
        # placing them in the filesystem.
        self.art_paths = {}

    # Asynchronous; after music is added to the library.
    def fetch_art(self, config, task):
        """Find art for the album being imported."""
        if task.should_write_tags() and task.is_album:
            path = art_for_album(task.info, task.path)
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
