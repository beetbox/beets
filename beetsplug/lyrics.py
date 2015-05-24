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

"""Fetches, embeds, and displays lyrics.
"""

from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import re
import requests
import json
import unicodedata
import urllib
import difflib
import itertools
import warnings
from HTMLParser import HTMLParseError

from beets import plugins
from beets import config, ui


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


# Utilities.


def unescape(text):
    """Resolves &#xxx; HTML entities (and some others)."""
    if isinstance(text, bytes):
        text = text.decode('utf8', 'ignore')
    out = text.replace(u'&nbsp;', u' ')

    def replchar(m):
        num = m.group(1)
        return unichr(int(num))
    out = re.sub(u"&#(\d+);", replchar, out)
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
        print('no closing tag found!')
        return
    return u''.join(parts)


def search_pairs(item):
    """Yield a pairs of artists and titles to search for.

    The first item in the pair is the name of the artist, the second
    item is a list of song names.

    In addition to the artist and title obtained from the `item` the
    method tries to strip extra information like paranthesized suffixes
    and featured artists from the strings and add them as candidates.
    The method also tries to split multiple titles separated with `/`.
    """

    title, artist = item.title, item.artist
    titles = [title]
    artists = [artist]

    # Remove any featuring artists from the artists name
    pattern = r"(.*?) {0}".format(plugins.feat_tokens())
    match = re.search(pattern, artist, re.IGNORECASE)
    if match:
        artists.append(match.group(1))

    # Remove a parenthesized suffix from a title string. Common
    # examples include (live), (remix), and (acoustic).
    pattern = r"(.+?)\s+[(].*[)]$"
    match = re.search(pattern, title, re.IGNORECASE)
    if match:
        titles.append(match.group(1))

    # Remove any featuring artists from the title
    pattern = r"(.*?) {0}".format(plugins.feat_tokens(for_artist=False))
    for title in titles[:]:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            titles.append(match.group(1))

    # Check for a dual song (e.g. Pink Floyd - Speak to Me / Breathe)
    # and each of them.
    multi_titles = []
    for title in titles:
        multi_titles.append([title])
        if '/' in title:
            multi_titles.append([x.strip() for x in title.split('/')])

    return itertools.product(artists, multi_titles)


class Backend(object):
    def __init__(self, config, log):
        self._log = log

    @staticmethod
    def _encode(s):
        """Encode the string for inclusion in a URL"""
        if isinstance(s, unicode):
            for char, repl in URL_CHARACTERS.items():
                s = s.replace(char, repl)
            s = s.encode('utf8', 'ignore')
        return urllib.quote(s)

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
                r = requests.get(url, verify=False)
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
    @classmethod
    def _encode(cls, s):
        s = re.sub(r'\s+', '_', s)
        s = s.replace("<", "Less_Than")
        s = s.replace(">", "Greater_Than")
        s = s.replace("#", "Number_")
        s = re.sub(r'[\[\{]', '(', s)
        s = re.sub(r'[\]\}]', ')', s)
        return super(SymbolsReplaced, cls)._encode(s)


class MusiXmatch(SymbolsReplaced):
    URL_PATTERN = 'https://www.musixmatch.com/lyrics/%s/%s'

    def fetch(self, artist, title):
        url = self.build_url(artist, title)
        html = self.fetch_url(url)
        if not html:
            return
        lyrics = extract_text_between(html,
                                      '"lyrics_body":', '"lyrics_language":')
        return lyrics.strip(',"').replace('\\n', '\n')


class LyricsWiki(SymbolsReplaced):
    """Fetch lyrics from LyricsWiki."""
    URL_PATTERN = 'http://lyrics.wikia.com/%s:%s'

    def fetch(self, artist, title):
        url = self.build_url(artist, title)
        html = self.fetch_url(url)
        if not html:
            return
        lyrics = extract_text_in(html, u"<div class='lyricbox'>")
        if lyrics and 'Unfortunately, we are not licensed' not in lyrics:
            return lyrics


class LyricsCom(Backend):
    """Fetch lyrics from Lyrics.com."""
    URL_PATTERN = 'http://www.lyrics.com/%s-lyrics-%s.html'
    NOT_FOUND = (
        'Sorry, we do not have the lyric',
        'Submit Lyrics',
    )

    @classmethod
    def _encode(cls, s):
        s = re.sub(r'[^\w\s-]', '', s)
        s = re.sub(r'\s+', '-', s)
        return super(LyricsCom, cls)._encode(s).lower()

    def fetch(self, artist, title):
        url = self.build_url(artist, title)
        html = self.fetch_url(url)
        if not html:
            return
        lyrics = extract_text_between(html, '<div id="lyrics" class="SCREENO'
                                      'NLY" itemprop="description">', '</div>')
        if not lyrics:
            return
        for not_found_str in self.NOT_FOUND:
            if not_found_str in lyrics:
                return

        parts = lyrics.split('\n---\nLyrics powered by', 1)
        if parts:
            return parts[0]


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
    html = re.sub(r'<(script).*?</\1>(?s)', '', html)  # Strip script tags.

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
    from bs4 import SoupStrainer, BeautifulSoup

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
    soup = sorted(soup.stripped_strings, key=len)[-1]
    return soup


class Google(Backend):
    """Fetch lyrics from Google search results."""
    def __init__(self, config, log):
        super(Google, self).__init__(config, log)
        self.api_key = config['google_API_key'].get(unicode)
        self.engine_id = config['google_engine_ID'].get(unicode)

    def is_lyrics(self, text, artist=None):
        """Determine whether the text seems to be valid lyrics.
        """
        if not text:
            return False
        badTriggersOcc = []
        nbLines = text.count('\n')
        if nbLines <= 1:
            self._log.debug(u"Ignoring too short lyrics '{0}'", text)
            return False
        elif nbLines < 5:
            badTriggersOcc.append('too_short')
        else:
            # Lyrics look legit, remove credits to avoid being penalized
            # further down
            text = remove_credits(text)

        badTriggers = ['lyrics', 'copyright', 'property', 'links']
        if artist:
            badTriggersOcc += [artist]

        for item in badTriggers:
            badTriggersOcc += [item] * len(re.findall(r'\W%s\W' % item,
                                                      text, re.I))

        if badTriggersOcc:
            self._log.debug(u'Bad triggers detected: {0}', badTriggersOcc)
        return len(badTriggersOcc) < 2

    def slugify(self, text):
        """Normalize a string and remove non-alphanumeric characters.
        """
        text = re.sub(r"[-'_\s]", '_', text)
        text = re.sub(r"_+", '_', text).strip('_')
        pat = "([^,\(]*)\((.*?)\)"  # Remove content within parentheses
        text = re.sub(pat, '\g<1>', text).strip()
        try:
            text = unicodedata.normalize('NFKD', text).encode('ascii',
                                                              'ignore')
            text = unicode(re.sub('[-\s]+', ' ', text))
        except UnicodeDecodeError:
            self._log.exception(u"Failing to normalize '{0}'", text)
        return text

    BY_TRANS = ['by', 'par', 'de', 'von']
    LYRICS_TRANS = ['lyrics', 'paroles', 'letras', 'liedtexte']

    def is_page_candidate(self, urlLink, urlTitle, title, artist):
        """Return True if the URL title makes it a good candidate to be a
        page that contains lyrics of title by artist.
        """
        title = self.slugify(title.lower())
        artist = self.slugify(artist.lower())
        sitename = re.search(u"//([^/]+)/.*",
                             self.slugify(urlLink.lower())).group(1)
        urlTitle = self.slugify(urlTitle.lower())
        # Check if URL title contains song title (exact match)
        if urlTitle.find(title) != -1:
            return True
        # or try extracting song title from URL title and check if
        # they are close enough
        tokens = [by + '_' + artist for by in self.BY_TRANS] + \
                 [artist, sitename, sitename.replace('www.', '')] + \
            self.LYRICS_TRANS
        songTitle = re.sub(u'(%s)' % u'|'.join(tokens), u'', urlTitle)
        songTitle = songTitle.strip('_|')
        typoRatio = .9
        ratio = difflib.SequenceMatcher(None, songTitle, title).ratio()
        return ratio >= typoRatio

    def fetch(self, artist, title):
        query = u"%s %s" % (artist, title)
        url = u'https://www.googleapis.com/customsearch/v1?key=%s&cx=%s&q=%s' \
              % (self.api_key, self.engine_id,
                 urllib.quote(query.encode('utf8')))

        data = urllib.urlopen(url)
        data = json.load(data)
        if 'error' in data:
            reason = data['error']['errors'][0]['reason']
            self._log.debug(u'google lyrics backend error: {0}', reason)
            return

        if 'items' in data.keys():
            for item in data['items']:
                urlLink = item['link']
                urlTitle = item.get('title', u'')
                if not self.is_page_candidate(urlLink, urlTitle,
                                              title, artist):
                    continue
                html = self.fetch_url(urlLink)
                lyrics = scrape_lyrics_from_html(html)
                if not lyrics:
                    continue

                if self.is_lyrics(lyrics, artist):
                    self._log.debug(u'got lyrics from {0}',
                                    item['displayLink'])
                    return lyrics


class LyricsPlugin(plugins.BeetsPlugin):
    SOURCES = ['google', 'lyricwiki', 'lyrics.com', 'musixmatch']
    SOURCE_BACKENDS = {
        'google': Google,
        'lyricwiki': LyricsWiki,
        'lyrics.com': LyricsCom,
        'musixmatch': MusiXmatch,
    }

    def __init__(self):
        super(LyricsPlugin, self).__init__()
        self.import_stages = [self.imported]
        self.config.add({
            'auto': True,
            'google_API_key': None,
            'google_engine_ID': u'009217259823014548361:lndtuqkycfu',
            'fallback': None,
            'force': False,
            'sources': self.SOURCES,
        })
        self.config['google_API_key'].redact = True
        self.config['google_engine_ID'].redact = True

        available_sources = list(self.SOURCES)
        if not self.config['google_API_key'].get() and \
                'google' in self.SOURCES:
            available_sources.remove('google')
        self.config['sources'] = plugins.sanitize_choices(
            self.config['sources'].as_str_seq(), available_sources)

        self.backends = [self.SOURCE_BACKENDS[key](self.config, self._log)
                         for key in self.config['sources'].as_str_seq()]

    def commands(self):
        cmd = ui.Subcommand('lyrics', help='fetch song lyrics')
        cmd.parser.add_option('-p', '--print', dest='printlyr',
                              action='store_true', default=False,
                              help='print lyrics to console')
        cmd.parser.add_option('-f', '--force', dest='force_refetch',
                              action='store_true', default=False,
                              help='always re-download lyrics')

        def func(lib, opts, args):
            # The "write to files" option corresponds to the
            # import_write config value.
            write = config['import']['write'].get(bool)
            for item in lib.items(ui.decargs(args)):
                self.fetch_item_lyrics(
                    lib, item, write,
                    opts.force_refetch or self.config['force'],
                )
                if opts.printlyr and item.lyrics:
                    ui.print_(item.lyrics)

        cmd.func = func
        return [cmd]

    def imported(self, session, task):
        """Import hook for fetching lyrics automatically.
        """
        if self.config['auto']:
            for item in task.imported_items():
                self.fetch_item_lyrics(session.lib, item,
                                       False, self.config['force'])

    def fetch_item_lyrics(self, lib, item, write, force):
        """Fetch and store lyrics for a single item. If ``write``, then the
        lyrics will also be written to the file itself."""
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
