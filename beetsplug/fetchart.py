# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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
CONTENT_TYPES = ('image/jpeg', 'image/png')
DOWNLOAD_EXTENSION = '.jpg'

CANDIDATE_BAD = 0
CANDIDATE_EXACT = 1
CANDIDATE_DOWNSCALE = 2

MATCH_EXACT = 0
MATCH_FALLBACK = 1

class Candidate():
    """ 

    """
    def __init__(self, path=None, url=None, source=u'', match=None):
        self.path = path
        self.source = source
        self.check = None
        self.match = match
        self.size = None

    def _validate(self, extra):
        """Determine whether the candidate artwork is valid based on
        its dimensions (width and ratio).

        Return `CANDIDATE_BAD` if the file is unusable.
        Return `CANDIDATE_EXACT` if the file is usable as-is.
        Return `CANDIDATE_DOWNSCALE` if the file must be resized.
        """
        if not self.path:
            return CANDIDATE_BAD

        if not (extra['enforce_ratio'] or 
                extra['minwidth'] or 
                extra['maxwidth']):
            return CANDIDATE_EXACT

        # get_size returns None if no local imaging backend is available
        self.size = ArtResizer.shared.get_size(self.path)
        self._log.debug(u'image size: {}', self.size)

        if not self.size:
            self._log.warning(u'Could not get size of image (please see '
                              u'documentation for dependencies). '
                              u'The configuration options `minwidth` and '
                              u'`enforce_ratio` may be violated.')
            return CANDIDATE_EXACT

        # Check minimum size.
        if extra['minwidth'] and self.size[0] < extra['minwidth']:
            self._log.debug(u'image too small ({} < {})',
                            self.size[0], extra['minwidth'])
            return CANDIDATE_BAD

        # Check aspect ratio.
        if extra['enforce_ratio'] and self.size[0] != self.size[1]:
            self._log.debug(u'image is not square ({} != {})',
                            self.size[0], self.size[1])
            return CANDIDATE_BAD

        # Check maximum size.
        if extra['maxwidth'] and self.size[0] > extra['maxwidth']:
            self._log.debug(u'image needs resizing ({} > {})',
                            self.size[0], extra['maxwidth'])
            return CANDIDATE_DOWNSCALE

        return CANDIDATE_EXACT

    def validate(self, extra):
        self.check = self._validate(extra)
        return self.check

    def resize(self, extra):
        if extra['maxwidth'] and self.check == CANDIDATE_DOWNSCALE:
            self.path = ArtResizer.shared.resize(extra['maxwidth'], self.path)


def _logged_get(log, *args, **kwargs):
    """Like `requests.get`, but logs the effective URL to the specified
    `log` at the `DEBUG` level.

    Use the optional `message` parameter to specify what to log before
    the URL. By default, the string is "getting URL".

    Also sets the User-Agent header to indicate beets.
    """
    # Use some arguments with the `send` call but most with the
    # `Request` construction. This is a cheap, magic-filled way to
    # emulate `requests.get` or, more pertinently,
    # `requests.Session.request`.
    req_kwargs = kwargs
    send_kwargs = {}
    for arg in ('stream', 'verify', 'proxies', 'cert', 'timeout'):
        if arg in kwargs:
            send_kwargs[arg] = req_kwargs.pop(arg)

    # Our special logging message parameter.
    if 'message' in kwargs:
        message = kwargs.pop('message')
    else:
        message = 'getting URL'

    req = requests.Request(b'GET', *args, **req_kwargs)
    with requests.Session() as s:
        s.headers = {b'User-Agent': b'beets'}
        prepped = s.prepare_request(req)
        log.debug('{}: {}', message, prepped.url)
        return s.send(prepped, **send_kwargs)


class RequestMixin(object):
    """Adds a Requests wrapper to the class that uses the logger, which
    must be named `self._log`.
    """

    def request(self, *args, **kwargs):
        """Like `requests.get`, but uses the logger `self._log`.

        See also `_logged_get`.
        """
        return _logged_get(self._log, *args, **kwargs)


# ART SOURCES ################################################################

class ArtSource(RequestMixin):
    def __init__(self, log, config):
        self._log = log
        self._config = config

    def get(self, album, extra):
        raise NotImplementedError()

    def fetch_image(self, candidate, extra):
        raise NotImplementedError()

class LocalArtSource(ArtSource):
    IS_LOCAL = True
    LOC_STR = u'local'

    def fetch_image(self, candidate, extra):
        return candidate

class RemoteArtSource(ArtSource):
    IS_LOCAL = False
    LOC_STR = u'remote'

    def fetch_image(self, candidate, extra):
        """Downloads an image from a URL and checks whether it seems to
        actually be an image. If so, returns a path to the downloaded image.
        Otherwise, returns None.
        """
        if extra['maxwidth']:
            candidate.url = ArtResizer.shared.proxy_url(extra['maxwidth'], 
                                                        candidate.url)
        try:
            with closing(self.request(candidate.url, stream=True,
                                      message=u'downloading image')) as resp:
                if 'Content-Type' not in resp.headers \
                        or resp.headers['Content-Type'] not in CONTENT_TYPES:
                    self._log.debug(
                        u'not a supported image: {}',
                        resp.headers.get('Content-Type') or u'no content type',
                    )
                    candidate.path = None
                    return 

                # Generate a temporary file with the correct extension.
                with NamedTemporaryFile(suffix=DOWNLOAD_EXTENSION,
                                        delete=False) as fh:
                    for chunk in resp.iter_content(chunk_size=1024):
                        fh.write(chunk)
                self._log.debug(u'downloaded art to: {0}',
                                util.displayable_path(fh.name))
                candidate.path = fh.name
                return

        except (IOError, requests.RequestException, TypeError) as exc:
            # Handling TypeError works around a urllib3 bug:
            # https://github.com/shazow/urllib3/issues/556
            self._log.debug(u'error fetching art: {}', exc)
            candidate.path = None
            return 


class CoverArtArchive(RemoteArtSource):
    """Cover Art Archive"""
    URL = 'http://coverartarchive.org/release/{mbid}/front'
    GROUP_URL = 'http://coverartarchive.org/release-group/{mbid}/front'

    def get(self, album, extra):
        """Return the Cover Art Archive and Cover Art Archive release group URLs
        using album MusicBrainz release ID and release group ID.
        """
        if album.mb_albumid:
            yield Candidate(url=self.URL.format(mbid=album.mb_albumid),
                            source=u'coverartarchive.org',
                            match=MATCH_EXACT)
        if album.mb_releasegroupid:
            yield Candidate(url=self.GROUP_URL.format(mbid=album.mb_releasegroupid),
                            source=u'coverartarchive.org',
                            match=MATCH_FALLBACK)


class Amazon(RemoteArtSource):
    URL = 'http://images.amazon.com/images/P/%s.%02i.LZZZZZZZ.jpg'
    INDICES = (1, 2)

    def get(self, album, extra):
        """Generate URLs using Amazon ID (ASIN) string.
        """
        if album.asin:
            for index in self.INDICES:
                yield Candidate(url=self.URL % (album.asin, index),
                                source=u'Amazon',
                                match=MATCH_EXACT)


class AlbumArtOrg(RemoteArtSource):
    """AlbumArt.org scraper"""
    URL = 'http://www.albumart.org/index_detail.php'
    PAT = r'href\s*=\s*"([^>"]*)"[^>]*title\s*=\s*"View larger image"'

    def get(self, album, extra):
        """Return art URL from AlbumArt.org using album ASIN.
        """
        if not album.asin:
            return
        # Get the page from albumart.org.
        try:
            resp = self.request(self.URL, params={'asin': album.asin})
            self._log.debug(u'scraped art URL: {0}', resp.url)
        except requests.RequestException:
            self._log.debug(u'error scraping art page')
            return

        # Search the page for the image URL.
        m = re.search(self.PAT, resp.text)
        if m:
            image_url = m.group(1)
            yield Candidate(url=image_url,
                            source=u'AlbumArt.org',
                            match=MATCH_EXACT)
        else:
            self._log.debug(u'no image found on page')


class GoogleImages(RemoteArtSource):
    URL = u'https://www.googleapis.com/customsearch/v1'

    def get(self, album, extra):
        """Return art URL from google custom search engine
        given an album title and interpreter.
        """
        if not (album.albumartist and album.album):
            return
        search_string = (album.albumartist + ',' + album.album).encode('utf-8')
        response = self.request(self.URL, params={
            'key': self._config['google_key'].get(),
            'cx': self._config['google_engine'].get(),
            'q': search_string,
            'searchType': 'image'
        })

        # Get results using JSON.
        try:
            data = response.json()
        except ValueError:
            self._log.debug(u'google: error loading response: {}'
                            .format(response.text))
            return

        if 'error' in data:
            reason = data['error']['errors'][0]['reason']
            self._log.debug(u'google fetchart error: {0}', reason)
            return

        if 'items' in data.keys():
            for item in data['items']:
                yield Candidate(url=item['link'],
                                source=u'Google images',
                                match=MATCH_EXACT)


class ITunesStore(RemoteArtSource):
    # Art from the iTunes Store.
    def get(self, album, extra):
        """Return art URL from iTunes Store given an album title.
        """
        if not (album.albumartist and album.album):
            return
        search_string = (album.albumartist + ' ' + album.album).encode('utf-8')
        try:
            # Isolate bugs in the iTunes library while searching.
            try:
                results = itunes.search_album(search_string)
            except Exception as exc:
                self._log.debug(u'iTunes search failed: {0}', exc)
                return

            # Get the first match.
            if results:
                itunes_album = results[0]
            else:
                self._log.debug(u'iTunes search for {:r} got no results',
                                search_string)
                return

            if itunes_album.get_artwork()['100']:
                small_url = itunes_album.get_artwork()['100']
                big_url = small_url.replace('100x100', '1200x1200')
                yield Candidate(url=big_url,
                                source=u'iTunes Store',
                                match=MATCH_EXACT)
            else:
                self._log.debug(u'album has no artwork in iTunes Store')
        except IndexError:
            self._log.debug(u'album not found in iTunes Store')


class Wikipedia(RemoteArtSource):
    # Art from Wikipedia (queried through DBpedia)
    DBPEDIA_URL = 'http://dbpedia.org/sparql'
    WIKIPEDIA_URL = 'http://en.wikipedia.org/w/api.php'
    SPARQL_QUERY = '''PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                 PREFIX dbpprop: <http://dbpedia.org/property/>
                 PREFIX owl: <http://dbpedia.org/ontology/>
                 PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                 PREFIX foaf: <http://xmlns.com/foaf/0.1/>

                 SELECT DISTINCT ?pageId ?coverFilename WHERE {{
                   ?subject owl:wikiPageID ?pageId .
                   ?subject dbpprop:name ?name .
                   ?subject rdfs:label ?label .
                   {{ ?subject dbpprop:artist ?artist }}
                     UNION
                   {{ ?subject owl:artist ?artist }}
                   {{ ?artist foaf:name "{artist}"@en }}
                     UNION
                   {{ ?artist dbpprop:name "{artist}"@en }}
                   ?subject rdf:type <http://dbpedia.org/ontology/Album> .
                   ?subject dbpprop:cover ?coverFilename .
                   FILTER ( regex(?name, "{album}", "i") )
                  }}
                 Limit 1'''

    def get(self, album, extra):
        if not (album.albumartist and album.album):
            return

        # Find the name of the cover art filename on DBpedia
        cover_filename, page_id = None, None
        dbpedia_response = self.request(
            self.DBPEDIA_URL,
            params={
                'format': 'application/sparql-results+json',
                'timeout': 2500,
                'query': self.SPARQL_QUERY.format(
                    artist=album.albumartist.title(), album=album.album)
            },
            headers={'content-type': 'application/json'},
        )
        try:
            data = dbpedia_response.json()
            results = data['results']['bindings']
            if results:
                cover_filename = 'File:' + results[0]['coverFilename']['value']
                page_id = results[0]['pageId']['value']
            else:
                self._log.debug(u'wikipedia: album not found on dbpedia')
        except (ValueError, KeyError, IndexError):
            self._log.debug(u'wikipedia: error scraping dbpedia response: {}',
                            dbpedia_response.text)

        # Ensure we have a filename before attempting to query wikipedia
        if not (cover_filename and page_id):
            return

        # DBPedia sometimes provides an incomplete cover_filename, indicated
        # by the filename having a space before the extension, e.g., 'foo .bar'
        # An additional Wikipedia call can help to find the real filename.
        # This may be removed once the DBPedia issue is resolved, see:
        # https://github.com/dbpedia/extraction-framework/issues/396
        if ' .' in cover_filename and \
           '.' not in cover_filename.split(' .')[-1]:
            self._log.debug(
                u'wikipedia: dbpedia provided incomplete cover_filename'
            )
            lpart, rpart = cover_filename.rsplit(' .', 1)

            # Query all the images in the page
            wikipedia_response = self.request(
                self.WIKIPEDIA_URL,
                params={
                    'format': 'json',
                    'action': 'query',
                    'continue': '',
                    'prop': 'images',
                    'pageids': page_id,
                },
                headers={'content-type': 'application/json'},
            )

            # Try to see if one of the images on the pages matches our
            # imcomplete cover_filename
            try:
                data = wikipedia_response.json()
                results = data['query']['pages'][page_id]['images']
                for result in results:
                    if re.match(re.escape(lpart) + r'.*?\.' + re.escape(rpart),
                                result['title']):
                        cover_filename = result['title']
                        break
            except (ValueError, KeyError):
                self._log.debug(
                    u'wikipedia: failed to retrieve a cover_filename'
                )
                return

        # Find the absolute url of the cover art on Wikipedia
        wikipedia_response = self.request(
            self.WIKIPEDIA_URL,
            params={
                'format': 'json',
                'action': 'query',
                'continue': '',
                'prop': 'imageinfo',
                'iiprop': 'url',
                'titles': cover_filename.encode('utf-8'),
            },
            headers={'content-type': 'application/json'},
        )

        try:
            data = wikipedia_response.json()
            results = data['query']['pages']
            for _, result in results.iteritems():
                image_url = result['imageinfo'][0]['url']
                yield Candidate(url=image_url,
                                source=u'Wikipedia',
                                match=MATCH_EXACT)
        except (ValueError, KeyError, IndexError):
            self._log.debug(u'wikipedia: error scraping imageinfo')
            return


class FileSystem(LocalArtSource):
    """Art from the filesystem"""
    @staticmethod
    def filename_priority(filename, cover_names):
        """Sort order for image names.

        Return indexes of cover names found in the image filename. This
        means that images with lower-numbered and more keywords will have
        higher priority.
        """
        return [idx for (idx, x) in enumerate(cover_names) if x in filename]

    def get(self, album, extra):
        """Look for album art files in the specified directories.
        """
        paths = extra['paths']
        cover_names = extra['cover_names']
        cover_pat = br"(\b|_)({0})(\b|_)".format(b'|'.join(cover_names))
        cautious = extra['cautious']
        
        for path in paths:
            if not os.path.isdir(path):
                continue

            # Find all files that look like images in the directory.
            images = []
            for fn in os.listdir(path):
                for ext in IMAGE_EXTENSIONS:
                    if fn.lower().endswith(b'.' + ext.encode('utf8')) and \
                       os.path.isfile(os.path.join(path, fn)):
                        images.append(fn)

            # Look for "preferred" filenames.
            images = sorted(images, 
                            lambda x: self.filename_priority(x, cover_names))
            for fn in images:
                if re.search(cover_pat, os.path.splitext(fn)[0], re.I):
                    self._log.debug(u'using well-named art file {0}',
                                    util.displayable_path(fn))
                    yield Candidate(path=os.path.join(path, fn),
                                    source=u'Filesystem',
                                    match=MATCH_EXACT)

            # Fall back to any image in the folder.
            if images and not cautious:
                self._log.debug(u'using fallback art file {0}',
                                util.displayable_path(images[0]))
                yield Candidate(path=os.path.join(path, images[0]),
                                source=u'Filesystem',
                                match=MATCH_FALLBACK)


# Try each source in turn.

SOURCES_ALL = [u'filesysytem', 
               u'coverart', u'itunes', u'amazon', u'albumart',
               u'wikipedia', u'google']

ART_SOURCES = {
    u'filesystem': FileSystem,
    u'coverart': CoverArtArchive,
    u'itunes': ITunesStore,
    u'albumart': AlbumArtOrg,
    u'amazon': Amazon,
    u'wikipedia': Wikipedia,
    u'google': GoogleImages,
}
SOURCE_NAMES = {v: k for k, v in ART_SOURCES.items()}

# PLUGIN LOGIC ###############################################################


class FetchArtPlugin(plugins.BeetsPlugin, RequestMixin):
    def __init__(self):
        super(FetchArtPlugin, self).__init__()

        self.config.add({
            'auto': True,
            'minwidth': 0,
            'maxwidth': 0,
            'enforce_ratio': False,
            'remote_priority': False,
            'cautious': False,
            'cover_names': ['cover', 'front', 'art', 'album', 'folder'],
            'sources': ['filesystem', 
                        'coverart', 'itunes', 'amazon', 'albumart'],
            'google_key': None,
            'google_engine': u'001442825323518660753:hrh5ch1gjzm',
        })
        self.config['google_key'].redact = True

        # Holds paths to downloaded images between fetching them and
        # placing them in the filesystem.
        self.art_paths = {}

        self.minwidth = self.config['minwidth'].get(int)
        self.maxwidth = self.config['maxwidth'].get(int)
        self.enforce_ratio = self.config['enforce_ratio'].get(bool)

        if self.config['auto']:
            # Enable two import hooks when fetching is enabled.
            self.import_stages = [self.fetch_art]
            self.register_listener('import_task_files', self.assign_art)

        available_sources = list(SOURCES_ALL)
        if not HAVE_ITUNES and u'itunes' in available_sources:
            available_sources.remove(u'itunes')
        if not self.config['google_key'].get() and \
                u'google' in available_sources:
            available_sources.remove(u'google')
        sources_name = plugins.sanitize_choices(
            self.config['sources'].as_str_seq(), available_sources)
        if 'remote_priority' in self.config:
            self._log.warning(
                u'The `fetch_art.remote_priority` configuration option has '
                u'been deprecated, see the documentation.')
            if self.config['remote_priority'].get(bool):
                try:
                    self.sources_name.remove[u'filesystem']
                    sources_name.append[u'filesystem']
                except ValueError:
                    pass
        self.sources = [ART_SOURCES[s](self._log, self.config)
                        for s in sources_name]

    # Asynchronous; after music is added to the library.
    def fetch_art(self, session, task):
        """Find art for the album being imported."""
        if task.is_album:  # Only fetch art for full albums.
            if task.album.artpath and os.path.isfile(task.album.artpath):
                # Album already has art (probably a re-import); skip it.
                return
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
        cmd.parser.add_option(
            u'-f', u'--force', dest='force',
            action='store_true', default=False,
            help=u're-download art when already present'
        )

        def func(lib, opts, args):
            self.batch_fetch_art(lib, lib.albums(ui.decargs(args)), opts.force)
        cmd.func = func
        return [cmd]

    # Utilities converted from functions to methods on logging overhaul

    def art_for_album(self, album, paths, local_only=False):
        """Given an Album object, returns a path to downloaded art for the
        album (or None if no art is found). If `maxwidth`, then images are
        resized to this maximum pixel size. If `local_only`, then only local
        image files from the filesystem are returned; no network requests
        are made.
        """
        out = None
        check = None

        # all the information any of the sources might need
        cover_names = self.config['cover_names'].as_str_seq()
        cover_names = map(util.bytestring_path, cover_names)
        cautious = self.config['cautious'].get(bool)
        extra = {'paths': paths, 
                 'cover_names': cover_names, 
                 'cautious': cautious,
                 'enforce_ratio': self.enforce_ratio,
                 'minwidth': self.minwidth,
                 'maxwidth': self.maxwidth}

        for source in self.sources:
            if source.is_local or not local_only:
                self._log.debug(
                    u'trying source {0} for album {1.albumartist} - {1.album}',
                    SOURCE_NAMES[type(source)],
                    album,
                )
                # URLs might be invalid at this point, or the image may not
                # fulfill the requirements
                for candidate in source.get(album, extra):
                    source.fetch_image(candidate)
                    if candidate.validate(extra):
                        out = candidate
                        self._log.debug(u'using {0.LOC_STR()} image {1}'
                                        .format(source, out.path))
                        break
                if out:
                    break

        if out:
            out.resize(extra)

        return out

    def batch_fetch_art(self, lib, albums, force):
        """Fetch album art for each of the albums. This implements the manual
        fetchart CLI command.
        """
        for album in albums:
            if album.artpath and not force and os.path.isfile(album.artpath):
                message = ui.colorize('text_highlight_minor', u'has album art')
            else:
                # In ordinary invocations, look for images on the
                # filesystem. When forcing, however, always go to the Web
                # sources.
                local_paths = None if force else [album.path]

                path = self.art_for_album(album, local_paths)
                if path:
                    album.set_art(path, False)
                    album.store()
                    message = ui.colorize('text_success', u'found album art')
                else:
                    message = ui.colorize('text_error', u'no art found')

            self._log.info(u'{0}: {1}', album, message)

