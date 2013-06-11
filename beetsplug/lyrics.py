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

"""Fetches, embeds, and displays lyrics.
"""
from __future__ import print_function

import re
import logging
import urllib
import json
import unicodedata
import difflib

from beets.plugins import BeetsPlugin
from beets import ui
from beets import config


# Global logger.

log = logging.getLogger('beets')

DIV_RE = re.compile(r'<(/?)div>?')
COMMENT_RE = re.compile(r'<!--.*-->', re.S)
TAG_RE = re.compile(r'<[^>]*>')
BREAK_RE = re.compile(r'<br\s*/?>')
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
        return urllib.urlopen(url).read()
    except IOError as exc:
        log.debug(u'failed to fetch: {0} ({1})'.format(url, unicode(exc)))
        return None

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

def extract_text(html, starttag):
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
        if match.group(1): # Closing tag.
            level -= 1
            if level == 0:
                pos = match.end()
        else: # Opening tag.
            if level == 0:
                parts.append(html[pos:match.start()])

            level += 1

        if level == -1:
            parts.append(html[pos:match.start()])
            break
    else:
        print('no closing tag found!')
        return
    lyrics = ''.join(parts)
    return strip_cruft(lyrics)

def strip_cruft(lyrics, wscollapse=True):
    """Clean up HTML from an extracted lyrics string. For example, <BR>
    tags are replaced with newlines.
    """
    lyrics = COMMENT_RE.sub('', lyrics)
    lyrics = unescape(lyrics)
    if wscollapse:
        lyrics = re.sub(r'\s+', ' ', lyrics) # Whitespace collapse.
    lyrics = BREAK_RE.sub('\n', lyrics) # <BR> newlines.
    lyrics = re.sub(r'\n +', '\n', lyrics)
    lyrics = re.sub(r' +\n', '\n', lyrics)
    lyrics = TAG_RE.sub('', lyrics) # Strip remaining HTML tags.
    lyrics = lyrics.replace('\r','\n')
    lyrics = lyrics.strip()
    return lyrics

def _encode(s):
    """Encode the string for inclusion in a URL (common to both
    LyricsWiki and Lyrics.com).
    """
    if isinstance(s, unicode):
        for char, repl in URL_CHARACTERS.items():
            s = s.replace(char, repl)
        s = s.encode('utf8', 'ignore')
    return urllib.quote(s)


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

    lyrics = extract_text(html, "<div class='lyricbox'>")
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

    lyrics = extract_text(html, '<div id="lyric_space">')
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
    # http://stackoverflow.com/questions/295135/turn-a-string-into-a-valid-
    # filename-in-python
    try:
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore')
        text = unicode(re.sub('[-\s]+', ' ', text))
    except UnicodeDecodeError:
        log.exception("Failing to normalize '%s'" % (text))
    return urllib.quote(text)


BY_TRANS     = ['by', 'par']
LYRICS_TRANS = ['lyrics', 'paroles']

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
    tokens = [by+'%20'+artist for by in BY_TRANS] + \
             [artist, sitename, sitename.replace('www.','')] + LYRICS_TRANS
    songTitle = re.sub(u'(%s)' % u'|'.join(tokens) ,u'', urlTitle).strip('%20')

    if songTitle:
        log.debug("Match ratio of '%s' with title: %s" %
                  (songTitle,
                   difflib.SequenceMatcher(None, songTitle, title).ratio()))

    typoRatio = .8
    return difflib.SequenceMatcher(None, songTitle, title).ratio() > typoRatio

def insert_line_feeds(text):
    """Insert newlines before upper-case characters.
    """
    tokensStr = re.split("([a-z][A-Z])", text)
    for idx in range(1, len(tokensStr), 2):
        ltoken = list(tokensStr[idx])
        tokensStr[idx] = ltoken[0] + '\n' + ltoken[1]
    return ''.join(tokensStr)

def sanitize_lyrics(text):
    """Clean text, returning raw lyrics as output or None if it happens
    that input text is actually not lyrics content.  Clean (x)html tags
    in text, correct layout and syntax...
    """
    text = strip_cruft(text, False)

    # Suppress advertisements.
    # Match lines with an opening bracket but no ending one, ie lines that
    # contained html link that has been wiped out when scraping.
    LINK1_RE = re.compile(r'(\(|\[).*[^\)\]]$')
    # Match lines containing url between brackets
    LINK2_RE = re.compile(r'(\(|\[).*[http|www].*(\]|\))')
    text = LINK1_RE.sub('', text)
    text = LINK2_RE.sub('', text)

    # Restore \n in input text
    if '\n' not in text:
        text = insert_line_feeds(text)

    while text.count('\n\n') > text.count('\n')/4:
        # Remove first occurrence of \n for each sequence of \n
        text = re.sub(r'\n(\n+)', '\g<1>', text)

    text = re.sub(r'\n\n+', '\n\n', text)   # keep at most two \n in a row

    return text

def is_lyrics(text, artist):
    """Determine whether the text seems to be valid lyrics.
    """
    badTriggers = []
    nbLines = text.count('\n')
    if nbLines <= 1:
        log.debug("Ignoring too short lyrics '%s'" % text)
        return 0
    elif nbLines < 5:
        badTriggers.append('too_short')

    for item in artist, 'lyrics', 'copyright', 'property':
        badTriggers += [item] * len(re.findall(r'\W%s\W' % item, text, re.I))

    if badTriggers:
        log.debug('Bad triggers detected: %s' % badTriggers)

    return len(badTriggers) < 2

def scrape_lyrics_from_url(url):
    """Scrape lyrics from a URL. If no lyrics can be found, return None
    instead.
    """
    from bs4 import BeautifulSoup, Tag, Comment
    html = fetch_url(url)
    soup = BeautifulSoup(html)

    for tag in soup.findAll('br'):
        tag.replaceWith('\n')

    # Remove non relevant html parts
    [s.extract() for s in soup(['head', 'script'])]
    comments = soup.findAll(text=lambda text:isinstance(text, Comment))
    [s.extract() for s in comments]

    try:
        for tag in soup.findAll(True):
            tag.name = 'p'          # keep tag contents

    except Exception, e:
        log.debug('Error %s when replacing containing marker by p marker' % e,
            exc_info=True)

    # Make better soup from current soup! The previous unclosed <p> sections
    # are now closed.  Use str() rather than prettify() as it's more
    # conservative concerning EOL
    soup = BeautifulSoup(str(soup))

    # In case lyrics are nested in no markup but <body>
    # Insert the whole body in a <p>
    bodyTag = soup.find('body')
    if bodyTag:
        pTag = soup.new_tag("p")
        bodyTag.parent.insert(0, pTag)
        pTag.insert(0, bodyTag)

    tagTokens = []

    for tag in soup.findAll('p'):
        soup2 = BeautifulSoup(str(tag))
        # Extract all text of <p> section.
        tagTokens += soup2.findAll(text=True)

    if tagTokens:
        # Lyrics are expected to be the longest paragraph
        tagTokens = sorted(tagTokens, key=len, reverse=True)
        soup = BeautifulSoup(tagTokens[0])
        return unescape(tagTokens[0].strip("\n\r: "))

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
        log.debug(u'google lyrics backend error: %s' % reason)
        return None

    if 'items' in data.keys():
        for item in data['items']:
            urlLink = item['link']
            urlTitle = item['title']
            if not is_page_candidate(urlLink, urlTitle, title, artist):
                continue
            lyrics = scrape_lyrics_from_url(urlLink)
            if not lyrics:
                continue

            lyrics = sanitize_lyrics(lyrics)

            if is_lyrics(lyrics, artist):
                return lyrics


# Plugin logic.

class LyricsPlugin(BeetsPlugin):
    def __init__(self):
        super(LyricsPlugin, self).__init__()
        self.import_stages = [self.imported]
        self.config.add({
            'auto': True,
            'google_API_key': None,
            'google_engine_ID': u'009217259823014548361:lndtuqkycfu',
            'fallback': None,
        })

        self.backends = [fetch_lyricswiki, fetch_lyricscom]

        if self.config['google_API_key'].get():
            self.backends.insert(0, fetch_google)

    def commands(self):
        cmd = ui.Subcommand('lyrics', help='fetch song lyrics')
        cmd.parser.add_option('-p', '--print', dest='printlyr',
                              action='store_true', default=False,
                              help='print lyrics to console')
        def func(lib, opts, args):
            # The "write to files" option corresponds to the
            # import_write config value.
            write = config['import']['write'].get(bool)
            for item in lib.items(ui.decargs(args)):
                self.fetch_item_lyrics(lib, logging.INFO, item, write)
                if opts.printlyr and item.lyrics:
                    ui.print_(item.lyrics)
        cmd.func = func
        return [cmd]

    # Auto-fetch lyrics on import.
    def imported(self, session, task):
        if self.config['auto']:
            for item in task.imported_items():
                self.fetch_item_lyrics(session.lib, logging.DEBUG, item, False)

    def fetch_item_lyrics(self, lib, loglevel, item, write):
        """Fetch and store lyrics for a single item. If ``write``, then the
        lyrics will also be written to the file itself. The ``loglevel``
        parameter controls the visibility of the function's status log
        messages.
        """
        fallback = self.config['fallback'].get()

        # Skip if the item already has lyrics.
        if item.lyrics:
            log.log(loglevel, u'lyrics already present: %s - %s' %
                              (item.artist, item.title))
            return

        # Fetch lyrics.
        lyrics = self.get_lyrics(item.artist, item.title)
        if not lyrics:
            log.log(loglevel, u'lyrics not found: %s - %s' %
                              (item.artist, item.title))
            if fallback:
                lyrics = fallback
            else:
                return
        else:
            log.log(loglevel, u'fetched lyrics: %s - %s' %
                              (item.artist, item.title))

        item.lyrics = lyrics

        if write:
            item.write()
        lib.store(item)

    def get_lyrics(self, artist, title):
        """Fetch lyrics, trying each source in turn. Return a string or
        None if no lyrics were found.
        """
        # Remove featuring artists from search.
        pattern = u"(.*) feat(uring|\.)?\s\S+"
        match = re.search(pattern, artist, re.IGNORECASE)
        if match:
            artist = match.group(0)

        for backend in self.backends:
            lyrics = backend(artist, title)
            if lyrics:
                if isinstance(lyrics, str):
                    lyrics = lyrics.decode('utf8', 'ignore')
                log.debug(u'got lyrics from backend: {0}'.format(
                    backend.__name__
                ))
                return lyrics
