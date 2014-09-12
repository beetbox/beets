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

"""Fetches album art.
"""
from contextlib import closing
import logging
import os
import re
from tempfile import NamedTemporaryFile

import requests

from beets.plugins import BeetsPlugin
from beets.util.artresizer import ArtResizer
from beets import importer
from beets import ui
from beets import util
from beets import config

IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg']
CONTENT_TYPES = ('image/jpeg',)
DOWNLOAD_EXTENSION = '.jpg'

log = logging.getLogger('beets')

requests_session = requests.Session()
requests_session.headers = {'User-Agent': 'beets'}


def _fetch_image(url):
    """Downloads an image from a URL and checks whether it seems to
    actually be an image. If so, returns a path to the downloaded image.
    Otherwise, returns None.
    """
    log.debug(u'fetchart: downloading art: {0}'.format(url))
    try:
        with closing(requests_session.get(url, stream=True)) as resp:
            if 'Content-Type' not in resp.headers \
                    or resp.headers['Content-Type'] not in CONTENT_TYPES:
                log.debug(u'fetchart: not an image')
                return

            # Generate a temporary file with the correct extension.
            with NamedTemporaryFile(suffix=DOWNLOAD_EXTENSION, delete=False) \
                    as fh:
                for chunk in resp.iter_content():
                    fh.write(chunk)
            log.debug(u'fetchart: downloaded art to: {0}'.format(
                util.displayable_path(fh.name)
            ))
            return fh.name
    except (IOError, requests.RequestException):
        log.debug(u'fetchart: error fetching art')


# ART SOURCES ################################################################

# Cover Art Archive.

CAA_URL = 'http://coverartarchive.org/release/{mbid}/front-500.jpg'
CAA_GROUP_URL = 'http://coverartarchive.org/release-group/{mbid}/front-500.jpg'


def caa_art(release_id):
    """Return the Cover Art Archive URL given a MusicBrainz release ID.
    """
    return CAA_URL.format(mbid=release_id)


def caa_group_art(release_group_id):
    """Return the Cover Art Archive release group URL given a MusicBrainz
    release group ID.
    """
    return CAA_GROUP_URL.format(mbid=release_group_id)


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
    try:
        resp = requests_session.get(AAO_URL, params={'asin': asin})
        log.debug(u'fetchart: scraped art URL: {0}'.format(resp.url))
    except requests.RequestException:
        log.debug(u'fetchart: error scraping art page')
        return

    # Search the page for the image URL.
    m = re.search(AAO_PAT, resp.text)
    if m:
        image_url = m.group(1)
        return image_url
    else:
        log.debug(u'fetchart: no image found on page')


# Google Images scraper.

GOOGLE_URL = 'https://ajax.googleapis.com/ajax/services/search/images'


def google_art(album):
    """Return art URL from google.org given an album title and
    interpreter.
    """
    search_string = (album.albumartist + ',' + album.album).encode('utf-8')
    response = requests_session.get(GOOGLE_URL, params={
        'v': '1.0',
        'q': search_string,
        'start': '0',
    })

    # Get results using JSON.
    try:
        results = response.json()
        data = results['responseData']
        dataInfo = data['results']
        for myUrl in dataInfo:
            return myUrl['unescapedUrl']
    except:
        log.debug(u'fetchart: error scraping art page')
        return


# Art from the filesystem.

def filename_priority(filename, cover_names):
    """Sort order for image names.

    Return indexes of cover names found in the image filename. This
    means that images with lower-numbered and more keywords will have higher
    priority.
    """
    return [idx for (idx, x) in enumerate(cover_names) if x in filename]


def art_in_path(path, cover_names, cautious):
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
    images = sorted(images, key=lambda x: filename_priority(x, cover_names))
    cover_pat = r"(\b|_)({0})(\b|_)".format('|'.join(cover_names))
    for fn in images:
        if re.search(cover_pat, os.path.splitext(fn)[0], re.I):
            log.debug(u'fetchart: using well-named art file {0}'.format(
                util.displayable_path(fn)
            ))
            return os.path.join(path, fn)

    # Fall back to any image in the folder.
    if images and not cautious:
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
    # Cover Art Archive.
    if album.mb_albumid:
        yield caa_art(album.mb_albumid)
    if album.mb_releasegroupid:
        yield caa_group_art(album.mb_releasegroupid)

    # Amazon and AlbumArt.org.
    if album.asin:
        for url in art_for_asin(album.asin):
            yield url
        url = aao_art(album.asin)
        if url:
            yield url

    if config['fetchart']['google_search']:
        url = google_art(album)
        if url:
            yield url


def art_for_album(album, paths, maxwidth=None, local_only=False):
    """Given an Album object, returns a path to downloaded art for the
    album (or None if no art is found). If `maxwidth`, then images are
    resized to this maximum pixel size. If `local_only`, then only local
    image files from the filesystem are returned; no network requests
    are made.
    """
    out = None

    # Local art.
    cover_names = config['fetchart']['cover_names'].as_str_seq()
    cover_names = map(util.bytestring_path, cover_names)
    cautious = config['fetchart']['cautious'].get(bool)
    if paths:
        for path in paths:
            out = art_in_path(path, cover_names, cautious)
            if out:
                break

    # Web art sources.
    remote_priority = config['fetchart']['remote_priority'].get(bool)
    if not local_only and (remote_priority or not out):
        for url in _source_urls(album):
            if maxwidth:
                url = ArtResizer.shared.proxy_url(maxwidth, url)
            candidate = _fetch_image(url)
            if candidate:
                out = candidate
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
            # In ordinary invocations, look for images on the
            # filesystem. When forcing, however, always go to the Web
            # sources.
            local_paths = None if force else [album.path]

            path = art_for_album(album, local_paths, maxwidth)
            if path:
                album.set_art(path, False)
                album.store()
                message = ui.colorize('green', 'found album art')
            else:
                message = ui.colorize('red', 'no art found')

        log.info(u'{0} - {1}: {2}'.format(album.albumartist, album.album,
                                          message))


class FetchArtPlugin(BeetsPlugin):
    def __init__(self):
        super(FetchArtPlugin, self).__init__()

        self.config.add({
            'auto': True,
            'maxwidth': 0,
            'remote_priority': False,
            'cautious': False,
            'google_search': False,
            'cover_names': ['cover', 'front', 'art', 'album', 'folder'],
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

            path = art_for_album(task.album, task.paths, self.maxwidth, local)

            if path:
                self.art_paths[task] = path

    # Synchronous; after music files are put in place.
    def assign_art(self, session, task):
        """Place the discovered art in the filesystem."""
        if task in self.art_paths:
            path = self.art_paths.pop(task)

            album = task.album
            src_removed = (config['import']['delete'].get(bool) or
                           config['import']['move'].get(bool))
            album.set_art(path, not src_removed)
            album.store()
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
