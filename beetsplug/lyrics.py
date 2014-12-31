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

"""Fetches, embeds, and displays lyrics.
"""
from __future__ import print_function

import re
import logging
import requests
import json
import unicodedata
import urllib
import difflib
import itertools
from HTMLParser import HTMLParseError

from beets import plugins
from beets import config, ui


# Global logger.

log = logging.getLogger('beets')

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

def fetch_url(url):
    """Retrieve the content at a given URL, or return None if the source
    is unreachable.
    """
    try:
        r = requests.get(url, verify=False)
    except requests.RequestException as exc:
        log.debug(u'lyrics request failed: {0}'.format(exc))
        return
    if r.status_code == requests.codes.ok:
        return r.text
    else:
        log.debug(u'failed to fetch: {0} ({1})'.format(url, r.status_code))


def unescape(text):
    """Resolves &#xxx; HTML entities (and some others)."""
    if isinstance(text, str):
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


def _encode(s):
    """Encode the string for inclusion in a URL (common to both
    LyricsWiki and Lyrics.com).
    """
    if isinstance(s, unicode):
        for char, repl in URL_CHARACTERS.items():
            s = s.replace(char, repl)
        s = s.encode('utf8', 'ignore')
    return urllib.quote(s)

# Musixmatch

MUSIXMATCH_URL_PATTERN = 'https://www.musixmatch.com/lyrics/%s/%s'


def fetch_musixmatch(artist, title):
    url = MUSIXMATCH_URL_PATTERN % (_lw_encode(artist.title()),
                                    _lw_encode(title.title()))
    html = fetch_url(url)
    if not html:
        return
    lyrics = extract_text_between(html, '"lyrics_body":', '"lyrics_language":')
    return lyrics.strip(',"').replace('\\n', '\n')

# LyricsWiki.

LYRICSWIKI_URL_PATTERN = 'http://lyrics.wikia.com/%s:%s'


def _lw_encode(s):
    s = re.sub(r'\s+', '_', s)
    s = s.replace("<", "Less_Than")
    s = s.replace(">", "Greater_Than")
    s = s.replace("#", "Number_")
    s = re.sub(r'[\[\{]', '(', s)
    s = re.sub(r'[\]\}]', ')', s)
    return _encode(s)


def fetch_lyricswiki(artist, title):
    """Fetch lyrics from LyricsWiki."""
    url = LYRICSWIKI_URL_PATTERN % (_lw_encode(artist), _lw_encode(title))
    html = fetch_url(url)
    if not html:
        return

    lyrics = extract_text_in(html, u"<div class='lyricbox'>")
    if lyrics and 'Unfortunately, we are not licensed' not in lyrics:
        return lyrics


# Lyrics.com.

LYRICSCOM_URL_PATTERN = 'http://www.lyrics.com/%s-lyrics-%s.html'
LYRICSCOM_NOT_FOUND = (
    'Sorry, we do not have the lyric',
    'Submit Lyrics',
)


def _lc_encode(s):
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'\s+', '-', s)
    return _encode(s).lower()


def fetch_lyricscom(artist, title):
    """Fetch lyrics from Lyrics.com."""
    url = LYRICSCOM_URL_PATTERN % (_lc_encode(title), _lc_encode(artist))
    html = fetch_url(url)
    if not html:
        return
    lyrics = extract_text_between(html, '<div id="lyrics" class="SCREENONLY" '
                                  'itemprop="description">', '</div>')
    if not lyrics:
        return
    for not_found_str in LYRICSCOM_NOT_FOUND:
        if not_found_str in lyrics:
            return

    parts = lyrics.split('\n---\nLyrics powered by', 1)
    if parts:
        return parts[0]


# Optional Google custom search API backend.

def slugify(text):
    """Normalize a string and remove non-alphanumeric characters.
    """
    text = re.sub(r"[-'_\s]", '_', text)
    text = re.sub(r"_+", '_', text).strip('_')
    pat = "([^,\(]*)\((.*?)\)"  # Remove content within parentheses
    text = re.sub(pat, '\g<1>', text).strip()
    try:
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore')
        text = unicode(re.sub('[-\s]+', ' ', text))
    except UnicodeDecodeError:
        log.exception(u"Failing to normalize '{0}'".format(text))
    return text


BY_TRANS = ['by', 'par', 'de', 'von']
LYRICS_TRANS = ['lyrics', 'paroles', 'letras', 'liedtexte']


def is_page_candidate(urlLink, urlTitle, title, artist):
    """Return True if the URL title makes it a good candidate to be a
    page that contains lyrics of title by artist.
    """
    title = slugify(title.lower())
    artist = slugify(artist.lower())
    sitename = re.search(u"//([^/]+)/.*", slugify(urlLink.lower())).group(1)
    urlTitle = slugify(urlTitle.lower())
    # Check if URL title contains song title (exact match)
    if urlTitle.find(title) != -1:
        return True
    # or try extracting song title from URL title and check if
    # they are close enough
    tokens = [by + '_' + artist for by in BY_TRANS] + \
             [artist, sitename, sitename.replace('www.', '')] + LYRICS_TRANS
    songTitle = re.sub(u'(%s)' % u'|'.join(tokens), u'', urlTitle)
    songTitle = songTitle.strip('_|')
    typoRatio = .9
    return difflib.SequenceMatcher(None, songTitle, title).ratio() >= typoRatio


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


def is_lyrics(text, artist=None):
    """Determine whether the text seems to be valid lyrics.
    """
    if not text:
        return False
    badTriggersOcc = []
    nbLines = text.count('\n')
    if nbLines <= 1:
        log.debug(u"Ignoring too short lyrics '{0}'".format(text))
        return False
    elif nbLines < 5:
        badTriggersOcc.append('too_short')
    else:
        # Lyrics look legit, remove credits to avoid being penalized further
        # down
        text = remove_credits(text)

    badTriggers = ['lyrics', 'copyright', 'property', 'links']
    if artist:
        badTriggersOcc += [artist]

    for item in badTriggers:
        badTriggersOcc += [item] * len(re.findall(r'\W%s\W' % item,
                                                  text, re.I))

    if badTriggersOcc:
        log.debug(u'Bad triggers detected: {0}'.format(badTriggersOcc))
    return len(badTriggersOcc) < 2


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


def fetch_google(artist, title):
    """Fetch lyrics from Google search results.
    """
    query = u"%s %s" % (artist, title)
    api_key = config['lyrics']['google_API_key'].get(unicode)
    engine_id = config['lyrics']['google_engine_ID'].get(unicode)
    url = u'https://www.googleapis.com/customsearch/v1?key=%s&cx=%s&q=%s' % \
          (api_key, engine_id, urllib.quote(query.encode('utf8')))

    data = urllib.urlopen(url)
    data = json.load(data)
    if 'error' in data:
        reason = data['error']['errors'][0]['reason']
        log.debug(u'google lyrics backend error: {0}'.format(reason))
        return

    if 'items' in data.keys():
        for item in data['items']:
            urlLink = item['link']
            urlTitle = item.get('title', u'')
            if not is_page_candidate(urlLink, urlTitle, title, artist):
                continue
            html = fetch_url(urlLink)
            lyrics = scrape_lyrics_from_html(html)
            if not lyrics:
                continue

            if is_lyrics(lyrics, artist):
                log.debug(u'got lyrics from {0}'.format(item['displayLink']))
                return lyrics


# Plugin logic.

SOURCES = ['google', 'lyricwiki', 'lyrics.com', 'musixmatch']
SOURCE_BACKENDS = {
    'google': fetch_google,
    'lyricwiki': fetch_lyricswiki,
    'lyrics.com': fetch_lyricscom,
    'musixmatch': fetch_musixmatch,
}


class LyricsPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(LyricsPlugin, self).__init__()
        self.import_stages = [self.imported]
        self.config.add({
            'auto': True,
            'google_API_key': None,
            'google_engine_ID': u'009217259823014548361:lndtuqkycfu',
            'fallback': None,
            'force': False,
            'sources': SOURCES,
        })

        available_sources = list(SOURCES)
        if not self.config['google_API_key'].get() and \
                'google' in SOURCES:
            available_sources.remove('google')
        self.config['sources'] = plugins.sanitize_choices(
            self.config['sources'].as_str_seq(), available_sources)
        self.backends = []
        for key in self.config['sources'].as_str_seq():
            self.backends.append(SOURCE_BACKENDS[key])

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
                    lib, logging.INFO, item, write,
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
                self.fetch_item_lyrics(session.lib, logging.DEBUG, item,
                                       False, self.config['force'])

    def fetch_item_lyrics(self, lib, loglevel, item, write, force):
        """Fetch and store lyrics for a single item. If ``write``, then the
        lyrics will also be written to the file itself. The ``loglevel``
        parameter controls the visibility of the function's status log
        messages.
        """
        # Skip if the item already has lyrics.
        if not force and item.lyrics:
            log.log(loglevel, u'lyrics already present: {0} - {1}'
                    .format(item.artist, item.title))
            return

        lyrics = None
        for artist, titles in search_pairs(item):
            lyrics = [self.get_lyrics(artist, title) for title in titles]
            if any(lyrics):
                break

        lyrics = u"\n\n---\n\n".join([l for l in lyrics if l])

        if lyrics:
            log.log(loglevel, u'fetched lyrics: {0} - {1}'
                              .format(item.artist, item.title))
        else:
            log.log(loglevel, u'lyrics not found: {0} - {1}'
                              .format(item.artist, item.title))
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
            lyrics = backend(artist, title)
            if lyrics:
                log.debug(u'got lyrics from backend: {0}'
                          .format(backend.__name__))
                return _scrape_strip_cruft(lyrics, True)
