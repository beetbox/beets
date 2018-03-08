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
from beets.mediafile import image_mime_type
from beets.util.artresizer import ArtResizer
from beets.util import confit
from beets.util import syspath, bytestring_path, py3_path
import six

try:
    import itunes
    HAVE_ITUNES = True
except ImportError:
    HAVE_ITUNES = False

CONTENT_TYPES = {
    'image/jpeg': [b'jpg', b'jpeg'],
    'image/png': [b'png']
}
IMAGE_EXTENSIONS = [ext for exts in CONTENT_TYPES.values() for ext in exts]


class Candidate(object):
    """Holds information about a matching artwork, deals with validation of
    dimension restrictions and resizing.
    """
    CANDIDATE_BAD = 0
    CANDIDATE_EXACT = 1
    CANDIDATE_DOWNSCALE = 2

    MATCH_EXACT = 0
    MATCH_FALLBACK = 1

    def __init__(self, log, path=None, url=None, source=u'',
                 match=None, size=None):
        self._log = log
        self.path = path
        self.url = url
        self.source = source
        self.check = None
        self.match = match
        self.size = size

    def _validate(self, plugin):
        """Determine whether the candidate artwork is valid based on
        its dimensions (width and ratio).

        Return `CANDIDATE_BAD` if the file is unusable.
        Return `CANDIDATE_EXACT` if the file is usable as-is.
        Return `CANDIDATE_DOWNSCALE` if the file must be resized.
        """
        if not self.path:
            return self.CANDIDATE_BAD

        if not (plugin.enforce_ratio or plugin.minwidth or plugin.maxwidth):
            return self.CANDIDATE_EXACT

        # get_size returns None if no local imaging backend is available
        if not self.size:
            self.size = ArtResizer.shared.get_size(self.path)
        self._log.debug(u'image size: {}', self.size)

        if not self.size:
            self._log.warning(u'Could not get size of image (please see '
                              u'documentation for dependencies). '
                              u'The configuration options `minwidth` and '
                              u'`enforce_ratio` may be violated.')
            return self.CANDIDATE_EXACT

        short_edge = min(self.size)
        long_edge = max(self.size)

        # Check minimum size.
        if plugin.minwidth and self.size[0] < plugin.minwidth:
            self._log.debug(u'image too small ({} < {})',
                            self.size[0], plugin.minwidth)
            return self.CANDIDATE_BAD

        # Check aspect ratio.
        edge_diff = long_edge - short_edge
        if plugin.enforce_ratio:
            if plugin.margin_px:
                if edge_diff > plugin.margin_px:
                    self._log.debug(u'image is not close enough to being '
                                    u'square, ({} - {} > {})',
                                    long_edge, short_edge, plugin.margin_px)
                    return self.CANDIDATE_BAD
            elif plugin.margin_percent:
                margin_px = plugin.margin_percent * long_edge
                if edge_diff > margin_px:
                    self._log.debug(u'image is not close enough to being '
                                    u'square, ({} - {} > {})',
                                    long_edge, short_edge, margin_px)
                    return self.CANDIDATE_BAD
            elif edge_diff:
                # also reached for margin_px == 0 and margin_percent == 0.0
                self._log.debug(u'image is not square ({} != {})',
                                self.size[0], self.size[1])
                return self.CANDIDATE_BAD

        # Check maximum size.
        if plugin.maxwidth and self.size[0] > plugin.maxwidth:
            self._log.debug(u'image needs resizing ({} > {})',
                            self.size[0], plugin.maxwidth)
            return self.CANDIDATE_DOWNSCALE

        return self.CANDIDATE_EXACT

    def validate(self, plugin):
        self.check = self._validate(plugin)
        return self.check

    def resize(self, plugin):
        if plugin.maxwidth and self.check == self.CANDIDATE_DOWNSCALE:
            self.path = ArtResizer.shared.resize(plugin.maxwidth, self.path)


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

    req = requests.Request('GET', *args, **req_kwargs)
    with requests.Session() as s:
        s.headers = {'User-Agent': 'beets'}
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
    VALID_MATCHING_CRITERIA = ['default']

    def __init__(self, log, config, match_by=None):
        self._log = log
        self._config = config
        self.match_by = match_by or self.VALID_MATCHING_CRITERIA

    def get(self, album, plugin, paths):
        raise NotImplementedError()

    def _candidate(self, **kwargs):
        return Candidate(source=self, log=self._log, **kwargs)

    def fetch_image(self, candidate, plugin):
        raise NotImplementedError()


class LocalArtSource(ArtSource):
    IS_LOCAL = True
    LOC_STR = u'local'

    def fetch_image(self, candidate, plugin):
        pass


class RemoteArtSource(ArtSource):
    IS_LOCAL = False
    LOC_STR = u'remote'

    def fetch_image(self, candidate, plugin):
        """Downloads an image from a URL and checks whether it seems to
        actually be an image. If so, returns a path to the downloaded image.
        Otherwise, returns None.
        """
        if plugin.maxwidth:
            candidate.url = ArtResizer.shared.proxy_url(plugin.maxwidth,
                                                        candidate.url)
        try:
            with closing(self.request(candidate.url, stream=True,
                                      message=u'downloading image')) as resp:
                ct = resp.headers.get('Content-Type', None)

                # Download the image to a temporary file. As some servers
                # (notably fanart.tv) have proven to return wrong Content-Types
                # when images were uploaded with a bad file extension, do not
                # rely on it. Instead validate the type using the file magic
                # and only then determine the extension.
                data = resp.iter_content(chunk_size=1024)
                header = b''
                for chunk in data:
                    header += chunk
                    if len(header) >= 32:
                        # The imghdr module will only read 32 bytes, and our
                        # own additions in mediafile even less.
                        break
                else:
                    # server didn't return enough data, i.e. corrupt image
                    return

                real_ct = image_mime_type(header)
                if real_ct is None:
                    # detection by file magic failed, fall back to the
                    # server-supplied Content-Type
                    # Is our type detection failsafe enough to drop this?
                    real_ct = ct

                if real_ct not in CONTENT_TYPES:
                    self._log.debug(u'not a supported image: {}',
                                    real_ct or u'unknown content type')
                    return

                ext = b'.' + CONTENT_TYPES[real_ct][0]

                if real_ct != ct:
                    self._log.warning(u'Server specified {}, but returned a '
                                      u'{} image. Correcting the extension '
                                      u'to {}',
                                      ct, real_ct, ext)

                suffix = py3_path(ext)
                with NamedTemporaryFile(suffix=suffix, delete=False) as fh:
                    # write the first already loaded part of the image
                    fh.write(header)
                    # download the remaining part of the image
                    for chunk in data:
                        fh.write(chunk)
                self._log.debug(u'downloaded art to: {0}',
                                util.displayable_path(fh.name))
                candidate.path = util.bytestring_path(fh.name)
                return

        except (IOError, requests.RequestException, TypeError) as exc:
            # Handling TypeError works around a urllib3 bug:
            # https://github.com/shazow/urllib3/issues/556
            self._log.debug(u'error fetching art: {}', exc)
            return


class CoverArtArchive(RemoteArtSource):
    NAME = u"Cover Art Archive"
    VALID_MATCHING_CRITERIA = ['release', 'releasegroup']

    if util.SNI_SUPPORTED:
        URL = 'https://coverartarchive.org/release/{mbid}/front'
        GROUP_URL = 'https://coverartarchive.org/release-group/{mbid}/front'
    else:
        URL = 'http://coverartarchive.org/release/{mbid}/front'
        GROUP_URL = 'http://coverartarchive.org/release-group/{mbid}/front'

    def get(self, album, plugin, paths):
        """Return the Cover Art Archive and Cover Art Archive release group URLs
        using album MusicBrainz release ID and release group ID.
        """
        if 'release' in self.match_by and album.mb_albumid:
            yield self._candidate(url=self.URL.format(mbid=album.mb_albumid),
                                  match=Candidate.MATCH_EXACT)
        if 'releasegroup' in self.match_by and album.mb_releasegroupid:
            yield self._candidate(
                url=self.GROUP_URL.format(mbid=album.mb_releasegroupid),
                match=Candidate.MATCH_FALLBACK)


class Amazon(RemoteArtSource):
    NAME = u"Amazon"
    URL = 'http://images.amazon.com/images/P/%s.%02i.LZZZZZZZ.jpg'
    INDICES = (1, 2)

    def get(self, album, plugin, paths):
        """Generate URLs using Amazon ID (ASIN) string.
        """
        if album.asin:
            for index in self.INDICES:
                yield self._candidate(url=self.URL % (album.asin, index),
                                      match=Candidate.MATCH_EXACT)


class AlbumArtOrg(RemoteArtSource):
    NAME = u"AlbumArt.org scraper"
    URL = 'http://www.albumart.org/index_detail.php'
    PAT = r'href\s*=\s*"([^>"]*)"[^>]*title\s*=\s*"View larger image"'

    def get(self, album, plugin, paths):
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
            yield self._candidate(url=image_url, match=Candidate.MATCH_EXACT)
        else:
            self._log.debug(u'no image found on page')


class GoogleImages(RemoteArtSource):
    NAME = u"Google Images"
    URL = u'https://www.googleapis.com/customsearch/v1'

    def __init__(self, *args, **kwargs):
        super(GoogleImages, self).__init__(*args, **kwargs)
        self.key = self._config['google_key'].get(),
        self.cx = self._config['google_engine'].get(),

    def get(self, album, plugin, paths):
        """Return art URL from google custom search engine
        given an album title and interpreter.
        """
        if not (album.albumartist and album.album):
            return
        search_string = (album.albumartist + ',' + album.album).encode('utf-8')
        response = self.request(self.URL, params={
            'key': self.key,
            'cx': self.cx,
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
                yield self._candidate(url=item['link'],
                                      match=Candidate.MATCH_EXACT)


class FanartTV(RemoteArtSource):
    """Art from fanart.tv requested using their API"""
    NAME = u"fanart.tv"
    API_URL = 'https://webservice.fanart.tv/v3/'
    API_ALBUMS = API_URL + 'music/albums/'
    PROJECT_KEY = '61a7d0ab4e67162b7a0c7c35915cd48e'

    def __init__(self, *args, **kwargs):
        super(FanartTV, self).__init__(*args, **kwargs)
        self.client_key = self._config['fanarttv_key'].get()

    def get(self, album, plugin, paths):
        if not album.mb_releasegroupid:
            return

        response = self.request(
            self.API_ALBUMS + album.mb_releasegroupid,
            headers={'api-key': self.PROJECT_KEY,
                     'client-key': self.client_key})

        try:
            data = response.json()
        except ValueError:
            self._log.debug(u'fanart.tv: error loading response: {}',
                            response.text)
            return

        if u'status' in data and data[u'status'] == u'error':
            if u'not found' in data[u'error message'].lower():
                self._log.debug(u'fanart.tv: no image found')
            elif u'api key' in data[u'error message'].lower():
                self._log.warning(u'fanart.tv: Invalid API key given, please '
                                  u'enter a valid one in your config file.')
            else:
                self._log.debug(u'fanart.tv: error on request: {}',
                                data[u'error message'])
            return

        matches = []
        # can there be more than one releasegroupid per response?
        for mbid, art in data.get(u'albums', dict()).items():
            # there might be more art referenced, e.g. cdart, and an albumcover
            # might not be present, even if the request was succesful
            if album.mb_releasegroupid == mbid and u'albumcover' in art:
                matches.extend(art[u'albumcover'])
            # can this actually occur?
            else:
                self._log.debug(u'fanart.tv: unexpected mb_releasegroupid in '
                                u'response!')

        matches.sort(key=lambda x: x[u'likes'], reverse=True)
        for item in matches:
            # fanart.tv has a strict size requirement for album art to be
            # uploaded
            yield self._candidate(url=item[u'url'],
                                  match=Candidate.MATCH_EXACT,
                                  size=(1000, 1000))


class ITunesStore(RemoteArtSource):
    NAME = u"iTunes Store"

    def get(self, album, plugin, paths):
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
                yield self._candidate(url=big_url, match=Candidate.MATCH_EXACT)
            else:
                self._log.debug(u'album has no artwork in iTunes Store')
        except IndexError:
            self._log.debug(u'album not found in iTunes Store')


class Wikipedia(RemoteArtSource):
    NAME = u"Wikipedia (queried through DBpedia)"
    DBPEDIA_URL = 'https://dbpedia.org/sparql'
    WIKIPEDIA_URL = 'https://en.wikipedia.org/w/api.php'
    SPARQL_QUERY = u'''PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
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

    def get(self, album, plugin, paths):
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
            for _, result in results.items():
                image_url = result['imageinfo'][0]['url']
                yield self._candidate(url=image_url,
                                      match=Candidate.MATCH_EXACT)
        except (ValueError, KeyError, IndexError):
            self._log.debug(u'wikipedia: error scraping imageinfo')
            return


class FileSystem(LocalArtSource):
    NAME = u"Filesystem"

    @staticmethod
    def filename_priority(filename, cover_names):
        """Sort order for image names.

        Return indexes of cover names found in the image filename. This
        means that images with lower-numbered and more keywords will have
        higher priority.
        """
        return [idx for (idx, x) in enumerate(cover_names) if x in filename]

    def get(self, album, plugin, paths):
        """Look for album art files in the specified directories.
        """
        if not paths:
            return
        cover_names = list(map(util.bytestring_path, plugin.cover_names))
        cover_names_str = b'|'.join(cover_names)
        cover_pat = br''.join([br"(\b|_)(", cover_names_str, br")(\b|_)"])

        for path in paths:
            if not os.path.isdir(syspath(path)):
                continue

            # Find all files that look like images in the directory.
            images = []
            for fn in os.listdir(syspath(path)):
                fn = bytestring_path(fn)
                for ext in IMAGE_EXTENSIONS:
                    if fn.lower().endswith(b'.' + ext) and \
                       os.path.isfile(syspath(os.path.join(path, fn))):
                        images.append(fn)

            # Look for "preferred" filenames.
            images = sorted(images,
                            key=lambda x:
                                self.filename_priority(x, cover_names))
            remaining = []
            for fn in images:
                if re.search(cover_pat, os.path.splitext(fn)[0], re.I):
                    self._log.debug(u'using well-named art file {0}',
                                    util.displayable_path(fn))
                    yield self._candidate(path=os.path.join(path, fn),
                                          match=Candidate.MATCH_EXACT)
                else:
                    remaining.append(fn)

            # Fall back to any image in the folder.
            if remaining and not plugin.cautious:
                self._log.debug(u'using fallback art file {0}',
                                util.displayable_path(remaining[0]))
                yield self._candidate(path=os.path.join(path, remaining[0]),
                                      match=Candidate.MATCH_FALLBACK)


# Try each source in turn.

SOURCES_ALL = [u'filesystem',
               u'coverart', u'itunes', u'amazon', u'albumart',
               u'wikipedia', u'google', u'fanarttv']

ART_SOURCES = {
    u'filesystem': FileSystem,
    u'coverart': CoverArtArchive,
    u'itunes': ITunesStore,
    u'albumart': AlbumArtOrg,
    u'amazon': Amazon,
    u'wikipedia': Wikipedia,
    u'google': GoogleImages,
    u'fanarttv': FanartTV,
}
SOURCE_NAMES = {v: k for k, v in ART_SOURCES.items()}

# PLUGIN LOGIC ###############################################################


class FetchArtPlugin(plugins.BeetsPlugin, RequestMixin):
    PAT_PX = r"(0|[1-9][0-9]*)px"
    PAT_PERCENT = r"(100(\.00?)?|[1-9]?[0-9](\.[0-9]{1,2})?)%"

    def __init__(self):
        super(FetchArtPlugin, self).__init__()

        # Holds candidates corresponding to downloaded images between
        # fetching them and placing them in the filesystem.
        self.art_candidates = {}

        self.config.add({
            'auto': True,
            'minwidth': 0,
            'maxwidth': 0,
            'enforce_ratio': False,
            'cautious': False,
            'cover_names': ['cover', 'front', 'art', 'album', 'folder'],
            'sources': ['filesystem',
                        'coverart', 'itunes', 'amazon', 'albumart'],
            'google_key': None,
            'google_engine': u'001442825323518660753:hrh5ch1gjzm',
            'fanarttv_key': None,
            'store_source': False,
        })
        self.config['google_key'].redact = True
        self.config['fanarttv_key'].redact = True

        self.minwidth = self.config['minwidth'].get(int)
        self.maxwidth = self.config['maxwidth'].get(int)

        # allow both pixel and percentage-based margin specifications
        self.enforce_ratio = self.config['enforce_ratio'].get(
            confit.OneOf([bool,
                          confit.String(pattern=self.PAT_PX),
                          confit.String(pattern=self.PAT_PERCENT)]))
        self.margin_px = None
        self.margin_percent = None
        if type(self.enforce_ratio) is six.text_type:
            if self.enforce_ratio[-1] == u'%':
                self.margin_percent = float(self.enforce_ratio[:-1]) / 100
            elif self.enforce_ratio[-2:] == u'px':
                self.margin_px = int(self.enforce_ratio[:-2])
            else:
                # shouldn't happen
                raise confit.ConfigValueError()
            self.enforce_ratio = True

        cover_names = self.config['cover_names'].as_str_seq()
        self.cover_names = list(map(util.bytestring_path, cover_names))
        self.cautious = self.config['cautious'].get(bool)
        self.store_source = self.config['store_source'].get(bool)

        self.src_removed = (config['import']['delete'].get(bool) or
                            config['import']['move'].get(bool))

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
        available_sources = [(s, c)
                             for s in available_sources
                             for c in ART_SOURCES[s].VALID_MATCHING_CRITERIA]
        sources = plugins.sanitize_pairs(
            self.config['sources'].as_pairs(default_value='*'),
            available_sources)

        if 'remote_priority' in self.config:
            self._log.warning(
                u'The `fetch_art.remote_priority` configuration option has '
                u'been deprecated. Instead, place `filesystem` at the end of '
                u'your `sources` list.')
            if self.config['remote_priority'].get(bool):
                fs = []
                others = []
                for s, c in sources:
                    if s == 'filesystem':
                        fs.append((s, c))
                    else:
                        others.append((s, c))
                sources = others + fs

        self.sources = [ART_SOURCES[s](self._log, self.config, match_by=[c])
                        for s, c in sources]

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
            elif task.choice_flag in (importer.action.APPLY,
                                      importer.action.RETAG):
                # Search everywhere for art.
                local = False
            else:
                # For any other choices (e.g., TRACKS), do nothing.
                return

            candidate = self.art_for_album(task.album, task.paths, local)

            if candidate:
                self.art_candidates[task] = candidate

    def _set_art(self, album, candidate, delete=False):
        album.set_art(candidate.path, delete)
        if self.store_source:
            # store the source of the chosen artwork in a flexible field
            self._log.debug(
                u"Storing art_source for {0.albumartist} - {0.album}",
                album)
            album.art_source = SOURCE_NAMES[type(candidate.source)]
        album.store()

    # Synchronous; after music files are put in place.
    def assign_art(self, session, task):
        """Place the discovered art in the filesystem."""
        if task in self.art_candidates:
            candidate = self.art_candidates.pop(task)

            self._set_art(task.album, candidate, not self.src_removed)

            if self.src_removed:
                task.prune(candidate.path)

    # Manual album art fetching.
    def commands(self):
        cmd = ui.Subcommand('fetchart', help='download album art')
        cmd.parser.add_option(
            u'-f', u'--force', dest='force',
            action='store_true', default=False,
            help=u're-download art when already present'
        )
        cmd.parser.add_option(
            u'-q', u'--quiet', dest='quiet',
            action='store_true', default=False,
            help=u'shows only quiet art'
        )

        def func(lib, opts, args):
            self.batch_fetch_art(lib, lib.albums(ui.decargs(args)), opts.force,
                                 opts.quiet)
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

        for source in self.sources:
            if source.IS_LOCAL or not local_only:
                self._log.debug(
                    u'trying source {0} for album {1.albumartist} - {1.album}',
                    SOURCE_NAMES[type(source)],
                    album,
                )
                # URLs might be invalid at this point, or the image may not
                # fulfill the requirements
                for candidate in source.get(album, self, paths):
                    source.fetch_image(candidate, self)
                    if candidate.validate(self):
                        out = candidate
                        self._log.debug(
                            u'using {0.LOC_STR} image {1}'.format(
                                source, util.displayable_path(out.path)))
                        break
                if out:
                    break

        if out:
            out.resize(self)

        return out

    def batch_fetch_art(self, lib, albums, force, quiet):
        """Fetch album art for each of the albums. This implements the manual
        fetchart CLI command.
        """
        for album in albums:
            if album.artpath and not force and os.path.isfile(album.artpath):
                if not quiet:
                    message = ui.colorize('text_highlight_minor',
                                          u'has album art')
                    self._log.info(u'{0}: {1}', album, message)
            else:
                # In ordinary invocations, look for images on the
                # filesystem. When forcing, however, always go to the Web
                # sources.
                local_paths = None if force else [album.path]

                candidate = self.art_for_album(album, local_paths)
                if candidate:
                    self._set_art(album, candidate)
                    message = ui.colorize('text_success', u'found album art')
                else:
                    message = ui.colorize('text_error', u'no art found')
                self._log.info(u'{0}: {1}', album, message)
