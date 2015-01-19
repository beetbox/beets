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

"""Fetches album art.
"""
from __future__ import division, absolute_import, print_function

from contextlib import closing
import os
import re
from tempfile import NamedTemporaryFile

import requests

from beets import plugins
from beets import importer
from beets import ui
from beets import util
from beets import config
from beets.util.artresizer import ArtResizer

try:
    import itunes
    HAVE_ITUNES = True
except ImportError:
    HAVE_ITUNES = False

IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg']
CONTENT_TYPES = ('image/jpeg',)
DOWNLOAD_EXTENSION = '.jpg'

requests_session = requests.Session()
requests_session.headers = {'User-Agent': 'beets'}


# ART SOURCES ################################################################

class ArtSource(object):
    def __init__(self, log):
        self._log = log

    def get(self, album):
        raise NotImplementedError()


class CoverArtArchive(ArtSource):
    """Cover Art Archive"""
    URL = 'http://coverartarchive.org/release/{mbid}/front-500.jpg'
    GROUP_URL = 'http://coverartarchive.org/release-group/{mbid}/front-500.jpg'

    def get(self, album):
        """Return the Cover Art Archive and Cover Art Archive release group URLs
        using album MusicBrainz release ID and release group ID.
        """
        if album.mb_albumid:
            yield self.URL.format(mbid=album.mb_albumid)
        if album.mb_releasegroupid:
            yield self.GROUP_URL.format(mbid=album.mb_releasegroupid)


class Amazon(ArtSource):
    URL = 'http://images.amazon.com/images/P/%s.%02i.LZZZZZZZ.jpg'
    INDICES = (1, 2)

    def get(self, album):
        """Generate URLs using Amazon ID (ASIN) string.
        """
        if album.asin:
            for index in self.INDICES:
                yield self.URL % (album.asin, index)


class AlbumArtOrg(ArtSource):
    """AlbumArt.org scraper"""
    URL = 'http://www.albumart.org/index_detail.php'
    PAT = r'href\s*=\s*"([^>"]*)"[^>]*title\s*=\s*"View larger image"'

    def get(self, album):
        """Return art URL from AlbumArt.org using album ASIN.
        """
        if not album.asin:
            return
        # Get the page from albumart.org.
        try:
            resp = requests_session.get(self.URL, params={'asin': album.asin})
            self._log.debug(u'scraped art URL: {0}', resp.url)
        except requests.RequestException:
            self._log.debug(u'error scraping art page')
            return

        # Search the page for the image URL.
        m = re.search(self.PAT, resp.text)
        if m:
            image_url = m.group(1)
            yield image_url
        else:
            self._log.debug(u'no image found on page')


class GoogleImages(ArtSource):
    URL = 'https://ajax.googleapis.com/ajax/services/search/images'

    def get(self, album):
        """Return art URL from google.org given an album title and
        interpreter.
        """
        if not (album.albumartist and album.album):
            return
        search_string = (album.albumartist + ',' + album.album).encode('utf-8')
        response = requests_session.get(self.URL, params={
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
                yield myUrl['unescapedUrl']
        except:
            self._log.debug(u'error scraping art page')
            return


class ITunesStore(ArtSource):
    # Art from the iTunes Store.
    def get(self, album):
        """Return art URL from iTunes Store given an album title.
        """
        search_string = (album.albumartist + ' ' + album.album).encode('utf-8')
        try:
            # Isolate bugs in the iTunes library while searching.
            try:
                itunes_album = itunes.search_album(search_string)[0]
            except Exception as exc:
                self._log.debug('iTunes search failed: {0}', exc)
                return

            if itunes_album.get_artwork()['100']:
                small_url = itunes_album.get_artwork()['100']
                big_url = small_url.replace('100x100', '1200x1200')
                yield big_url
            else:
                self._log.debug(u'album has no artwork in iTunes Store')
        except IndexError:
            self._log.debug(u'album not found in iTunes Store')


class FileSystem(ArtSource):
    """Art from the filesystem"""
    @staticmethod
    def filename_priority(filename, cover_names):
        """Sort order for image names.

        Return indexes of cover names found in the image filename. This
        means that images with lower-numbered and more keywords will have
        higher priority.
        """
        return [idx for (idx, x) in enumerate(cover_names) if x in filename]

    def get(self, path, cover_names, cautious):
        """Look for album art files in a specified directory.
        """
        if not os.path.isdir(path):
            return

        # Find all files that look like images in the directory.
        images = []
        for fn in os.listdir(path):
            for ext in IMAGE_EXTENSIONS:
                if fn.lower().endswith('.' + ext) and \
                   os.path.isfile(os.path.join(path, fn)):
                    images.append(fn)

        # Look for "preferred" filenames.
        images = sorted(images,
                        key=lambda x: self.filename_priority(x, cover_names))
        cover_pat = r"(\b|_)({0})(\b|_)".format('|'.join(cover_names))
        for fn in images:
            if re.search(cover_pat, os.path.splitext(fn)[0], re.I):
                self._log.debug(u'using well-named art file {0}',
                                util.displayable_path(fn))
                return os.path.join(path, fn)

        # Fall back to any image in the folder.
        if images and not cautious:
            self._log.debug(u'using fallback art file {0}',
                            util.displayable_path(images[0]))
            return os.path.join(path, images[0])


# Try each source in turn.

SOURCES_ALL = [u'coverart', u'itunes', u'amazon', u'albumart', u'google']

ART_FUNCS = {
    u'coverart': CoverArtArchive,
    u'itunes': ITunesStore,
    u'albumart': AlbumArtOrg,
    u'amazon': Amazon,
    u'google': GoogleImages,
}

# PLUGIN LOGIC ###############################################################


class FetchArtPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(FetchArtPlugin, self).__init__()

        self.config.add({
            'auto': True,
            'maxwidth': 0,
            'remote_priority': False,
            'cautious': False,
            'google_search': False,
            'cover_names': ['cover', 'front', 'art', 'album', 'folder'],
            'sources': SOURCES_ALL,
        })

        # Holds paths to downloaded images between fetching them and
        # placing them in the filesystem.
        self.art_paths = {}

        self.maxwidth = self.config['maxwidth'].get(int)
        if self.config['auto']:
            # Enable two import hooks when fetching is enabled.
            self.import_stages = [self.fetch_art]
            self.register_listener('import_task_files', self.assign_art)

        available_sources = list(SOURCES_ALL)
        if not HAVE_ITUNES and u'itunes' in available_sources:
            available_sources.remove(u'itunes')
        sources_name = plugins.sanitize_choices(
            self.config['sources'].as_str_seq(), available_sources)
        self.sources = [ART_FUNCS[s](self._log) for s in sources_name]
        self.fs_source = FileSystem(self._log)

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

            path = self.art_for_album(task.album, task.paths, local)

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
            self.batch_fetch_art(lib, lib.albums(ui.decargs(args)), opts.force)
        cmd.func = func
        return [cmd]

    # Utilities converted from functions to methods on logging overhaul

    def _fetch_image(self, url):
        """Downloads an image from a URL and checks whether it seems to
        actually be an image. If so, returns a path to the downloaded image.
        Otherwise, returns None.
        """
        self._log.debug(u'downloading art: {0}', url)
        try:
            with closing(requests_session.get(url, stream=True)) as resp:
                if 'Content-Type' not in resp.headers \
                        or resp.headers['Content-Type'] not in CONTENT_TYPES:
                    self._log.debug(u'not an image')
                    return

                # Generate a temporary file with the correct extension.
                with NamedTemporaryFile(suffix=DOWNLOAD_EXTENSION,
                                        delete=False) as fh:
                    for chunk in resp.iter_content():
                        fh.write(chunk)
                self._log.debug(u'downloaded art to: {0}',
                                util.displayable_path(fh.name))
                return fh.name
        except (IOError, requests.RequestException):
            self._log.debug(u'error fetching art')

    def art_for_album(self, album, paths, local_only=False):
        """Given an Album object, returns a path to downloaded art for the
        album (or None if no art is found). If `maxwidth`, then images are
        resized to this maximum pixel size. If `local_only`, then only local
        image files from the filesystem are returned; no network requests
        are made.
        """
        out = None

        # Local art.
        cover_names = self.config['cover_names'].as_str_seq()
        cover_names = map(util.bytestring_path, cover_names)
        cautious = self.config['cautious'].get(bool)
        if paths:
            for path in paths:
                # FIXME
                out = self.fs_source.get(path, cover_names, cautious)
                if out:
                    break

        # Web art sources.
        remote_priority = self.config['remote_priority'].get(bool)
        if not local_only and (remote_priority or not out):
            for url in self._source_urls(album):
                if self.maxwidth:
                    url = ArtResizer.shared.proxy_url(self.maxwidth, url)
                candidate = self._fetch_image(url)
                if candidate:
                    out = candidate
                    break

        if self.maxwidth and out:
            out = ArtResizer.shared.resize(self.maxwidth, out)
        return out

    def batch_fetch_art(self, lib, albums, force):
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

                path = self.art_for_album(album, local_paths)
                if path:
                    album.set_art(path, False)
                    album.store()
                    message = ui.colorize('green', 'found album art')
                else:
                    message = ui.colorize('red', 'no art found')

            self._log.info(u'{0.albumartist} - {0.album}: {1}', album, message)

    def _source_urls(self, album):
        """Generate possible source URLs for an album's art. The URLs are
        not guaranteed to work so they each need to be attempted in turn.
        This allows the main `art_for_album` function to abort iteration
        through this sequence early to avoid the cost of scraping when not
        necessary.
        """
        for source in self.sources:
            urls = source.get(album)
            for url in urls:
                yield url
