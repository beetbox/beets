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

"""Fetches, embeds, and displays lyrics.
"""

from __future__ import absolute_import, division, print_function

import difflib
import errno
import itertools
import json
import struct
import os.path
import re
import requests
import unicodedata
from unidecode import unidecode
import warnings
import six
from six.moves import urllib

try:
    from bs4 import SoupStrainer, BeautifulSoup
    HAS_BEAUTIFUL_SOUP = True
except ImportError:
    HAS_BEAUTIFUL_SOUP = False

try:
    import langdetect
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

try:
    # PY3: HTMLParseError was removed in 3.5 as strict mode
    # was deprecated in 3.3.
    # https://docs.python.org/3.3/library/html.parser.html
    from six.moves.html_parser import HTMLParseError
except ImportError:
    class HTMLParseError(Exception):
        pass

from beets import plugins
from beets import ui
from beets import util
import beets

DIV_RE = re.compile(r'<(/?)div>?', re.I)
COMMENT_RE = re.compile(r'<!--.*-->', re.S)
TAG_RE = re.compile(r'<[^>]*>')
BREAK_RE = re.compile(r'\n?\s*<br([\s|/][^>]*)*>\s*\n?', re.I)
URL_CHARACTERS = {
    u'\u2018': u"'",
    u'\u2019': u"'",
    u'\u201c': u'"',
    u'\u201d': u'"',
    u'\u2010': u'-',
    u'\u2011': u'-',
    u'\u2012': u'-',
    u'\u2013': u'-',
    u'\u2014': u'-',
    u'\u2015': u'-',
    u'\u2016': u'-',
    u'\u2026': u'...',
}
USER_AGENT = 'beets/{}'.format(beets.__version__)

# The content for the base index.rst generated in ReST mode.
REST_INDEX_TEMPLATE = u'''Lyrics
======

* :ref:`Song index <genindex>`
* :ref:`search`

Artist index:

.. toctree::
   :maxdepth: 1
   :glob:

   artists/*
'''

# The content for the base conf.py generated.
REST_CONF_TEMPLATE = u'''# -*- coding: utf-8 -*-
master_doc = 'index'
project = u'Lyrics'
copyright = u'none'
author = u'Various Authors'
latex_documents = [
    (master_doc, 'Lyrics.tex', project,
     author, 'manual'),
]
epub_title = project
epub_author = author
epub_publisher = author
epub_copyright = copyright
epub_exclude_files = ['search.html']
epub_tocdepth = 1
epub_tocdup = False
'''


# Utilities.

def unichar(i):
    try:
        return six.unichr(i)
    except ValueError:
        return struct.pack('i', i).decode('utf-32')


def unescape(text):
    """Resolve &#xxx; HTML entities (and some others)."""
    if isinstance(text, bytes):
        text = text.decode('utf-8', 'ignore')
    out = text.replace(u'&nbsp;', u' ')

    def replchar(m):
        num = m.group(1)
        return unichar(int(num))
    out = re.sub(u"&#(\\d+);", replchar, out)
    return out


def extract_text_between(html, start_marker, end_marker):
    try:
        _, html = html.split(start_marker, 1)
        html, _ = html.split(end_marker, 1)
    except ValueError:
        return u''
    return html


def extract_text_in(html, starttag):
    """Extract the text from a <DIV> tag in the HTML starting with
    ``starttag``. Returns None if parsing fails.
    """
    # Strip off the leading text before opening tag.
    try:
        _, html = html.split(starttag, 1)
    except ValueError:
        return

    # Walk through balanced DIV tags.
    level = 0
    parts = []
    pos = 0
    for match in DIV_RE.finditer(html):
        if match.group(1):  # Closing tag.
            level -= 1
            if level == 0:
                pos = match.end()
        else:  # Opening tag.
            if level == 0:
                parts.append(html[pos:match.start()])
            level += 1

        if level == -1:
            parts.append(html[pos:match.start()])
            break
    else:
        print(u'no closing tag found!')
        return
    return u''.join(parts)


def search_pairs(item):
    """Yield a pairs of artists and titles to search for.

    The first item in the pair is the name of the artist, the second
    item is a list of song names.

    In addition to the artist and title obtained from the `item` the
    method tries to strip extra information like paranthesized suffixes
    and featured artists from the strings and add them as candidates.
    The artist sort name is added as a fallback candidate to help in
    cases where artist name includes special characters or is in a
    non-latin script.
    The method also tries to split multiple titles separated with `/`.
    """
    def generate_alternatives(string, patterns):
        """Generate string alternatives by extracting first matching group for
           each given pattern.
        """
        alternatives = [string]
        for pattern in patterns:
            match = re.search(pattern, string, re.IGNORECASE)
            if match:
                alternatives.append(match.group(1))
        return alternatives

    title, artist, artist_sort = item.title, item.artist, item.artist_sort

    patterns = [
        # Remove any featuring artists from the artists name
        r"(.*?) {0}".format(plugins.feat_tokens())]
    artists = generate_alternatives(artist, patterns)
    # Use the artist_sort as fallback only if it differs from artist to avoid
    # repeated remote requests with the same search terms
    if artist != artist_sort:
        artists.append(artist_sort)

    patterns = [
        # Remove a parenthesized suffix from a title string. Common
        # examples include (live), (remix), and (acoustic).
        r"(.+?)\s+[(].*[)]$",
        # Remove any featuring artists from the title
        r"(.*?) {0}".format(plugins.feat_tokens(for_artist=False)),
        # Remove part of title after colon ':' for songs with subtitles
        r"(.+?)\s*:.*"]
    titles = generate_alternatives(title, patterns)

    # Check for a dual song (e.g. Pink Floyd - Speak to Me / Breathe)
    # and each of them.
    multi_titles = []
    for title in titles:
        multi_titles.append([title])
        if '/' in title:
            multi_titles.append([x.strip() for x in title.split('/')])

    return itertools.product(artists, multi_titles)


def slug(text):
    """Make a URL-safe, human-readable version of the given text

    This will do the following:

    1. decode unicode characters into ASCII
    2. shift everything to lowercase
    3. strip whitespace
    4. replace other non-word characters with dashes
    5. strip extra dashes

    This somewhat duplicates the :func:`Google.slugify` function but
    slugify is not as generic as this one, which can be reused
    elsewhere.
    """
    return re.sub(r'\W+', '-', unidecode(text).lower().strip()).strip('-')


class Backend(object):
    def __init__(self, config, log):
        self._log = log

    @staticmethod
    def _encode(s):
        """Encode the string for inclusion in a URL"""
        if isinstance(s, six.text_type):
            for char, repl in URL_CHARACTERS.items():
                s = s.replace(char, repl)
            s = s.encode('utf-8', 'ignore')
        return urllib.parse.quote(s)

    def build_url(self, artist, title):
        return self.URL_PATTERN % (self._encode(artist.title()),
                                   self._encode(title.title()))

    def fetch_url(self, url):
        """Retrieve the content at a given URL, or return None if the source
        is unreachable.
        """
        try:
            # Disable the InsecureRequestWarning that comes from using
            # `verify=false`.
            # https://github.com/kennethreitz/requests/issues/2214
            # We're not overly worried about the NSA MITMing our lyrics scraper
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                r = requests.get(url, verify=False, headers={
                    'User-Agent': USER_AGENT,
                })
        except requests.RequestException as exc:
            self._log.debug(u'lyrics request failed: {0}', exc)
            return
        if r.status_code == requests.codes.ok:
            return r.text
        else:
            self._log.debug(u'failed to fetch: {0} ({1})', url, r.status_code)

    def fetch(self, artist, title):
        raise NotImplementedError()


class SymbolsReplaced(Backend):
    REPLACEMENTS = {
        r'\s+': '_',
        '<': 'Less_Than',
        '>': 'Greater_Than',
        '#': 'Number_',
        r'[\[\{]': '(',
        r'[\]\}]': ')',
    }

    @classmethod
    def _encode(cls, s):
        for old, new in cls.REPLACEMENTS.items():
            s = re.sub(old, new, s)

        return super(SymbolsReplaced, cls)._encode(s)


class MusiXmatch(SymbolsReplaced):
    REPLACEMENTS = dict(SymbolsReplaced.REPLACEMENTS, **{
        r'\s+': '-'
    })

    URL_PATTERN = 'https://www.musixmatch.com/lyrics/%s/%s'

    def fetch(self, artist, title):
        url = self.build_url(artist, title)

        html = self.fetch_url(url)
        if not html:
            return
        if "We detected that your IP is blocked" in html:
            self._log.warning(u'we are blocked at MusixMatch: url %s failed'
                              % url)
            return
        html_part = html.split('<p class="mxm-lyrics__content')[-1]
        lyrics = extract_text_between(html_part, '>', '</p>')
        lyrics = lyrics.strip(',"').replace('\\n', '\n')
        # another odd case: sometimes only that string remains, for
        # missing songs. this seems to happen after being blocked
        # above, when filling in the CAPTCHA.
        if "Instant lyrics for all your music." in lyrics:
            return
        return lyrics


class Genius(Backend):
    """Fetch lyrics from Genius via genius-api.

    Simply adapted from
    bigishdata.com/2016/09/27/getting-song-lyrics-from-geniuss-api-scraping/
    """

    base_url = "https://api.genius.com"

    def __init__(self, config, log):
        super(Genius, self).__init__(config, log)
        self.api_key = config['genius_api_key'].as_str()
        self.headers = {
            'Authorization': "Bearer %s" % self.api_key,
            'User-Agent': USER_AGENT,
        }

    def lyrics_from_song_api_path(self, song_api_path):
        song_url = self.base_url + song_api_path
        response = requests.get(song_url, headers=self.headers)
        json = response.json()
        path = json["response"]["song"]["path"]

        # Gotta go regular html scraping... come on Genius.
        page_url = "https://genius.com" + path
        try:
            page = requests.get(page_url)
        except requests.RequestException as exc:
            self._log.debug(u'Genius page request for {0} failed: {1}',
                            page_url, exc)
            return None
        html = BeautifulSoup(page.text, "html.parser")

        # Remove script tags that they put in the middle of the lyrics.
        [h.extract() for h in html('script')]

        # At least Genius is nice and has a tag called 'lyrics'!
        # Updated css where the lyrics are based in HTML.
        lyrics_div = html.find("div", class_="lyrics")
        if lyrics_div is None:
            self._log.debug(u'Genius lyrics for {0} not found',
                            page_url)
            return None

        return lyrics_div.get_text()

    def fetch(self, artist, title):
        search_url = self.base_url + "/search"
        data = {'q': title}
        try:
            response = requests.get(search_url, data=data,
                                    headers=self.headers)
        except requests.RequestException as exc:
            self._log.debug(u'Genius API request failed: {0}', exc)
            return None

        try:
            json = response.json()
        except ValueError:
            self._log.debug(u'Genius API request returned invalid JSON')
            return None

        song_info = None
        for hit in json["response"]["hits"]:
            # Genius uses zero-width characters to denote lowercase
            # artist names.
            hit_artist = hit["result"]["primary_artist"]["name"]. \
                strip(u'\u200b').lower()

            if hit_artist == artist.lower():
                song_info = hit
                break

        if song_info:
            self._log.debug(u'fetched: {0}', song_info["result"]["url"])
            song_api_path = song_info["result"]["api_path"]
            return self.lyrics_from_song_api_path(song_api_path)
        else:
            self._log.debug(u'genius: no matching artist')


class LyricsWiki(SymbolsReplaced):
    """Fetch lyrics from LyricsWiki."""

    if util.SNI_SUPPORTED:
        URL_PATTERN = 'https://lyrics.wikia.com/%s:%s'
    else:
        URL_PATTERN = 'http://lyrics.wikia.com/%s:%s'

    def fetch(self, artist, title):
        url = self.build_url(artist, title)
        html = self.fetch_url(url)
        if not html:
            return

        # Get the HTML fragment inside the appropriate HTML element and then
        # extract the text from it.
        html_frag = extract_text_in(html, u"<div class='lyricbox'>")
        if html_frag:
            lyrics = _scrape_strip_cruft(html_frag, True)

            if lyrics and 'Unfortunately, we are not licensed' not in lyrics:
                return lyrics


def remove_credits(text):
    """Remove first/last line of text if it contains the word 'lyrics'
    eg 'Lyrics by songsdatabase.com'
    """
    textlines = text.split('\n')
    credits = None
    for i in (0, -1):
        if textlines and 'lyrics' in textlines[i].lower():
            credits = textlines.pop(i)
    if credits:
        text = '\n'.join(textlines)
    return text


def _scrape_strip_cruft(html, plain_text_out=False):
    """Clean up HTML
    """
    html = unescape(html)

    html = html.replace('\r', '\n')  # Normalize EOL.
    html = re.sub(r' +', ' ', html)  # Whitespaces collapse.
    html = BREAK_RE.sub('\n', html)  # <br> eats up surrounding '\n'.
    html = re.sub(r'(?s)<(script).*?</\1>', '', html)  # Strip script tags.

    if plain_text_out:  # Strip remaining HTML tags
        html = COMMENT_RE.sub('', html)
        html = TAG_RE.sub('', html)

    html = '\n'.join([x.strip() for x in html.strip().split('\n')])
    html = re.sub(r'\n{3,}', r'\n\n', html)
    return html


def _scrape_merge_paragraphs(html):
    html = re.sub(r'</p>\s*<p(\s*[^>]*)>', '\n', html)
    return re.sub(r'<div .*>\s*</div>', '\n', html)


def scrape_lyrics_from_html(html):
    """Scrape lyrics from a URL. If no lyrics can be found, return None
    instead.
    """
    if not HAS_BEAUTIFUL_SOUP:
        return None

    if not html:
        return None

    def is_text_notcode(text):
        length = len(text)
        return (length > 20 and
                text.count(' ') > length / 25 and
                (text.find('{') == -1 or text.find(';') == -1))
    html = _scrape_strip_cruft(html)
    html = _scrape_merge_paragraphs(html)

    # extract all long text blocks that are not code
    try:
        soup = BeautifulSoup(html, "html.parser",
                             parse_only=SoupStrainer(text=is_text_notcode))
    except HTMLParseError:
        return None

    # Get the longest text element (if any).
    strings = sorted(soup.stripped_strings, key=len, reverse=True)
    if strings:
        return strings[0]
    else:
        return None


class Google(Backend):
    """Fetch lyrics from Google search results."""

    def __init__(self, config, log):
        super(Google, self).__init__(config, log)
        self.api_key = config['google_API_key'].as_str()
        self.engine_id = config['google_engine_ID'].as_str()

    def is_lyrics(self, text, artist=None):
        """Determine whether the text seems to be valid lyrics.
        """
        if not text:
            return False
        bad_triggers_occ = []
        nb_lines = text.count('\n')
        if nb_lines <= 1:
            self._log.debug(u"Ignoring too short lyrics '{0}'", text)
            return False
        elif nb_lines < 5:
            bad_triggers_occ.append('too_short')
        else:
            # Lyrics look legit, remove credits to avoid being penalized
            # further down
            text = remove_credits(text)

        bad_triggers = ['lyrics', 'copyright', 'property', 'links']
        if artist:
            bad_triggers_occ += [artist]

        for item in bad_triggers:
            bad_triggers_occ += [item] * len(re.findall(r'\W%s\W' % item,
                                                        text, re.I))

        if bad_triggers_occ:
            self._log.debug(u'Bad triggers detected: {0}', bad_triggers_occ)
        return len(bad_triggers_occ) < 2

    def slugify(self, text):
        """Normalize a string and remove non-alphanumeric characters.
        """
        text = re.sub(r"[-'_\s]", '_', text)
        text = re.sub(r"_+", '_', text).strip('_')
        pat = r"([^,\(]*)\((.*?)\)"  # Remove content within parentheses
        text = re.sub(pat, r'\g<1>', text).strip()
        try:
            text = unicodedata.normalize('NFKD', text).encode('ascii',
                                                              'ignore')
            text = six.text_type(re.sub(r'[-\s]+', ' ', text.decode('utf-8')))
        except UnicodeDecodeError:
            self._log.exception(u"Failing to normalize '{0}'", text)
        return text

    BY_TRANS = ['by', 'par', 'de', 'von']
    LYRICS_TRANS = ['lyrics', 'paroles', 'letras', 'liedtexte']

    def is_page_candidate(self, url_link, url_title, title, artist):
        """Return True if the URL title makes it a good candidate to be a
        page that contains lyrics of title by artist.
        """
        title = self.slugify(title.lower())
        artist = self.slugify(artist.lower())
        sitename = re.search(u"//([^/]+)/.*",
                             self.slugify(url_link.lower())).group(1)
        url_title = self.slugify(url_title.lower())

        # Check if URL title contains song title (exact match)
        if url_title.find(title) != -1:
            return True

        # or try extracting song title from URL title and check if
        # they are close enough
        tokens = [by + '_' + artist for by in self.BY_TRANS] + \
                 [artist, sitename, sitename.replace('www.', '')] + \
            self.LYRICS_TRANS
        tokens = [re.escape(t) for t in tokens]
        song_title = re.sub(u'(%s)' % u'|'.join(tokens), u'', url_title)

        song_title = song_title.strip('_|')
        typo_ratio = .9
        ratio = difflib.SequenceMatcher(None, song_title, title).ratio()
        return ratio >= typo_ratio

    def fetch(self, artist, title):
        query = u"%s %s" % (artist, title)
        url = u'https://www.googleapis.com/customsearch/v1?key=%s&cx=%s&q=%s' \
              % (self.api_key, self.engine_id,
                 urllib.parse.quote(query.encode('utf-8')))

        data = self.fetch_url(url)
        if not data:
            self._log.debug(u'google backend returned no data')
            return None
        try:
            data = json.loads(data)
        except ValueError as exc:
            self._log.debug(u'google backend returned malformed JSON: {}', exc)
        if 'error' in data:
            reason = data['error']['errors'][0]['reason']
            self._log.debug(u'google backend error: {0}', reason)
            return None

        if 'items' in data.keys():
            for item in data['items']:
                url_link = item['link']
                url_title = item.get('title', u'')
                if not self.is_page_candidate(url_link, url_title,
                                              title, artist):
                    continue
                html = self.fetch_url(url_link)
                lyrics = scrape_lyrics_from_html(html)
                if not lyrics:
                    continue

                if self.is_lyrics(lyrics, artist):
                    self._log.debug(u'got lyrics from {0}',
                                    item['displayLink'])
                    return lyrics


class LyricsPlugin(plugins.BeetsPlugin):
    SOURCES = ['google', 'lyricwiki', 'musixmatch', 'genius']
    SOURCE_BACKENDS = {
        'google': Google,
        'lyricwiki': LyricsWiki,
        'musixmatch': MusiXmatch,
        'genius': Genius,
    }

    def __init__(self):
        super(LyricsPlugin, self).__init__()
        self.import_stages = [self.imported]
        self.config.add({
            'auto': True,
            'bing_client_secret': None,
            'bing_lang_from': [],
            'bing_lang_to': None,
            'google_API_key': None,
            'google_engine_ID': u'009217259823014548361:lndtuqkycfu',
            'genius_api_key':
                "Ryq93pUGm8bM6eUWwD_M3NOFFDAtp2yEE7W"
                "76V-uFL5jks5dNvcGCdarqFjDhP9c",
            'fallback': None,
            'force': False,
            'local': False,
            'sources': self.SOURCES,
        })
        self.config['bing_client_secret'].redact = True
        self.config['google_API_key'].redact = True
        self.config['google_engine_ID'].redact = True
        self.config['genius_api_key'].redact = True

        # State information for the ReST writer.
        # First, the current artist we're writing.
        self.artist = u'Unknown artist'
        # The current album: False means no album yet.
        self.album = False
        # The current rest file content. None means the file is not
        # open yet.
        self.rest = None

        available_sources = list(self.SOURCES)
        sources = plugins.sanitize_choices(
            self.config['sources'].as_str_seq(), available_sources)

        if 'google' in sources:
            if not self.config['google_API_key'].get():
                # We log a *debug* message here because the default
                # configuration includes `google`. This way, the source
                # is silent by default but can be enabled just by
                # setting an API key.
                self._log.debug(u'Disabling google source: '
                                u'no API key configured.')
                sources.remove('google')
            elif not HAS_BEAUTIFUL_SOUP:
                self._log.warning(u'To use the google lyrics source, you must '
                                  u'install the beautifulsoup4 module. See '
                                  u'the documentation for further details.')
                sources.remove('google')

        if 'genius' in sources and not HAS_BEAUTIFUL_SOUP:
            self._log.debug(
                u'The Genius backend requires BeautifulSoup, which is not '
                u'installed, so the source is disabled.'
            )
            sources.remove('genius')

        self.config['bing_lang_from'] = [
            x.lower() for x in self.config['bing_lang_from'].as_str_seq()]
        self.bing_auth_token = None

        if not HAS_LANGDETECT and self.config['bing_client_secret'].get():
            self._log.warning(u'To use bing translations, you need to '
                              u'install the langdetect module. See the '
                              u'documentation for further details.')

        self.backends = [self.SOURCE_BACKENDS[source](self.config, self._log)
                         for source in sources]

    def get_bing_access_token(self):
        params = {
            'client_id': 'beets',
            'client_secret': self.config['bing_client_secret'],
            'scope': "https://api.microsofttranslator.com",
            'grant_type': 'client_credentials',
        }

        oauth_url = 'https://datamarket.accesscontrol.windows.net/v2/OAuth2-13'
        oauth_token = json.loads(requests.post(
            oauth_url,
            data=urllib.parse.urlencode(params)).content)
        if 'access_token' in oauth_token:
            return "Bearer " + oauth_token['access_token']
        else:
            self._log.warning(u'Could not get Bing Translate API access token.'
                              u' Check your "bing_client_secret" password')

    def commands(self):
        cmd = ui.Subcommand('lyrics', help='fetch song lyrics')
        cmd.parser.add_option(
            u'-p', u'--print', dest='printlyr',
            action='store_true', default=False,
            help=u'print lyrics to console',
        )
        cmd.parser.add_option(
            u'-r', u'--write-rest', dest='writerest',
            action='store', default=None, metavar='dir',
            help=u'write lyrics to given directory as ReST files',
        )
        cmd.parser.add_option(
            u'-f', u'--force', dest='force_refetch',
            action='store_true', default=False,
            help=u'always re-download lyrics',
        )
        cmd.parser.add_option(
            u'-l', u'--local', dest='local_only',
            action='store_true', default=False,
            help=u'do not fetch missing lyrics',
        )

        def func(lib, opts, args):
            # The "write to files" option corresponds to the
            # import_write config value.
            write = ui.should_write()
            if opts.writerest:
                self.writerest_indexes(opts.writerest)
            for item in lib.items(ui.decargs(args)):
                if not opts.local_only and not self.config['local']:
                    self.fetch_item_lyrics(
                        lib, item, write,
                        opts.force_refetch or self.config['force'],
                    )
                if item.lyrics:
                    if opts.printlyr:
                        ui.print_(item.lyrics)
                    if opts.writerest:
                        self.writerest(opts.writerest, item)
            if opts.writerest:
                # flush last artist
                self.writerest(opts.writerest, None)
                ui.print_(u'ReST files generated. to build, use one of:')
                ui.print_(u'  sphinx-build -b html %s _build/html'
                          % opts.writerest)
                ui.print_(u'  sphinx-build -b epub %s _build/epub'
                          % opts.writerest)
                ui.print_((u'  sphinx-build -b latex %s _build/latex '
                           u'&& make -C _build/latex all-pdf')
                          % opts.writerest)
        cmd.func = func
        return [cmd]

    def writerest(self, directory, item):
        """Write the item to an ReST file

        This will keep state (in the `rest` variable) in order to avoid
        writing continuously to the same files.
        """

        if item is None or slug(self.artist) != slug(item.albumartist):
            if self.rest is not None:
                path = os.path.join(directory, 'artists',
                                    slug(self.artist) + u'.rst')
                with open(path, 'wb') as output:
                    output.write(self.rest.encode('utf-8'))
                self.rest = None
                if item is None:
                    return
            self.artist = item.albumartist.strip()
            self.rest = u"%s\n%s\n\n.. contents::\n   :local:\n\n" \
                        % (self.artist,
                           u'=' * len(self.artist))
        if self.album != item.album:
            tmpalbum = self.album = item.album.strip()
            if self.album == '':
                tmpalbum = u'Unknown album'
            self.rest += u"%s\n%s\n\n" % (tmpalbum, u'-' * len(tmpalbum))
        title_str = u":index:`%s`" % item.title.strip()
        block = u'| ' + item.lyrics.replace(u'\n', u'\n| ')
        self.rest += u"%s\n%s\n\n%s\n\n" % (title_str,
                                            u'~' * len(title_str),
                                            block)

    def writerest_indexes(self, directory):
        """Write conf.py and index.rst files necessary for Sphinx

        We write minimal configurations that are necessary for Sphinx
        to operate. We do not overwrite existing files so that
        customizations are respected."""
        try:
            os.makedirs(os.path.join(directory, 'artists'))
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
            else:
                raise
        indexfile = os.path.join(directory, 'index.rst')
        if not os.path.exists(indexfile):
            with open(indexfile, 'w') as output:
                output.write(REST_INDEX_TEMPLATE)
        conffile = os.path.join(directory, 'conf.py')
        if not os.path.exists(conffile):
            with open(conffile, 'w') as output:
                output.write(REST_CONF_TEMPLATE)

    def imported(self, session, task):
        """Import hook for fetching lyrics automatically.
        """
        if self.config['auto']:
            for item in task.imported_items():
                self.fetch_item_lyrics(session.lib, item,
                                       False, self.config['force'])

    def fetch_item_lyrics(self, lib, item, write, force):
        """Fetch and store lyrics for a single item. If ``write``, then the
           lyrics will also be written to the file itself.
        """
        # Skip if the item already has lyrics.
        if not force and item.lyrics:
            self._log.info(u'lyrics already present: {0}', item)
            return

        lyrics = None
        for artist, titles in search_pairs(item):
            lyrics = [self.get_lyrics(artist, title) for title in titles]
            if any(lyrics):
                break

        lyrics = u"\n\n---\n\n".join([l for l in lyrics if l])

        if lyrics:
            self._log.info(u'fetched lyrics: {0}', item)
            if HAS_LANGDETECT and self.config['bing_client_secret'].get():
                lang_from = langdetect.detect(lyrics)
                if self.config['bing_lang_to'].get() != lang_from and (
                    not self.config['bing_lang_from'] or (
                        lang_from in self.config[
                        'bing_lang_from'].as_str_seq())):
                    lyrics = self.append_translation(
                        lyrics, self.config['bing_lang_to'])
        else:
            self._log.info(u'lyrics not found: {0}', item)
            fallback = self.config['fallback'].get()
            if fallback:
                lyrics = fallback
            else:
                return
        item.lyrics = lyrics
        if write:
            item.try_write()
        item.store()

    def get_lyrics(self, artist, title):
        """Fetch lyrics, trying each source in turn. Return a string or
        None if no lyrics were found.
        """
        for backend in self.backends:
            lyrics = backend.fetch(artist, title)
            if lyrics:
                self._log.debug(u'got lyrics from backend: {0}',
                                backend.__class__.__name__)
                return _scrape_strip_cruft(lyrics, True)

    def append_translation(self, text, to_lang):
        import xml.etree.ElementTree as ET

        if not self.bing_auth_token:
            self.bing_auth_token = self.get_bing_access_token()
        if self.bing_auth_token:
            # Extract unique lines to limit API request size per song
            text_lines = set(text.split('\n'))
            url = ('https://api.microsofttranslator.com/v2/Http.svc/'
                   'Translate?text=%s&to=%s' % ('|'.join(text_lines), to_lang))
            r = requests.get(url,
                             headers={"Authorization ": self.bing_auth_token})
            if r.status_code != 200:
                self._log.debug('translation API error {}: {}', r.status_code,
                                r.text)
                if 'token has expired' in r.text:
                    self.bing_auth_token = None
                    return self.append_translation(text, to_lang)
                return text
            lines_translated = ET.fromstring(r.text.encode('utf-8')).text
            # Use a translation mapping dict to build resulting lyrics
            translations = dict(zip(text_lines, lines_translated.split('|')))
            result = ''
            for line in text.split('\n'):
                result += '%s / %s\n' % (line, translations[line])
            return result
