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

"""Fetches, embeds, and displays lyrics.
"""
import urllib
import re
import logging

from beets.plugins import BeetsPlugin
from beets import ui
from beets.ui import commands


# Global logger.

log = logging.getLogger('beets')


# Lyrics scrapers.

COMMENT_RE = re.compile(r'<!--.*-->', re.S)
DIV_RE = re.compile(r'<(/?)div>?')
TAG_RE = re.compile(r'<[^>]*>')
BREAK_RE = re.compile(r'<br\s*/?>')

def fetch_url(url):
    """Retrieve the content at a given URL, or return None if the source
    is unreachable.
    """
    try:
        return urllib.urlopen(url).read()
    except IOError as exc:
        log.debug('failed to fetch: {0} ({1})'.format(url, str(exc)))
        return None

def unescape(text):
    """Resolves &#xxx; HTML entities (and some others)."""
    out = text.replace('&nbsp;', ' ')
    def replchar(m):
        num = m.group(1)
        return unichr(int(num))
    out = re.sub("&#(\d+);", replchar, out)
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
        print 'no closing tag found!'
        return
    lyrics = ''.join(parts)

    # Strip cruft.
    lyrics = COMMENT_RE.sub('', lyrics)
    lyrics = unescape(lyrics)
    lyrics = re.sub(r'\s+', ' ', lyrics) # Whitespace collapse.
    lyrics = BREAK_RE.sub('\n', lyrics) # <BR> newlines.
    lyrics = re.sub(r'\n +', '\n', lyrics)
    lyrics = re.sub(r' +\n', '\n', lyrics)
    lyrics = TAG_RE.sub('', lyrics) # Strip remaining HTML tags.
    lyrics = lyrics.strip()
    return lyrics

LYRICSWIKI_URL_PATTERN = 'http://lyrics.wikia.com/%s:%s'
def _lw_encode(s):
    s = re.sub(r'\s+', '_', s)
    s = s.replace("<", "Less_Than")
    s = s.replace(">", "Greater_Than")
    s = s.replace("#", "Number_")
    s = re.sub(r'[\[\{]', '(', s)
    s = re.sub(r'[\]\}]', ')', s)
    if isinstance(s, unicode):
        s = s.encode('utf8', 'ignore')
    return urllib.quote(s)
def fetch_lyricswiki(artist, title):
    """Fetch lyrics from LyricsWiki."""
    url = LYRICSWIKI_URL_PATTERN % (_lw_encode(artist), _lw_encode(title))
    html = fetch_url(url)
    if not html:
        return

    lyrics = extract_text(html, "<div class='lyricbox'>")
    if lyrics and 'Unfortunately, we are not licensed' not in lyrics:
        return lyrics

LYRICSCOM_URL_PATTERN = 'http://www.lyrics.com/%s-lyrics-%s.html'
def _lc_encode(s):
    s = re.sub(r'\s+', '-', s)
    if isinstance(s, unicode):
        s = s.encode('utf8', 'ignore')
    return urllib.quote(s)
def fetch_lyricscom(artist, title):
    """Fetch lyrics from Lyrics.com."""
    url = LYRICSCOM_URL_PATTERN % (_lc_encode(title), _lc_encode(artist))
    html = fetch_url(url)
    if not html:
        return

    lyrics = extract_text(html, '<div id="lyric_space">')
    if lyrics and 'Sorry, we do not have the lyric' not in lyrics:
        parts = lyrics.split('\n---\nLyrics powered by', 1)
        if parts:
            return parts[0]

BACKENDS = [fetch_lyricswiki, fetch_lyricscom]
def get_lyrics(artist, title):
    """Fetch lyrics, trying each source in turn."""
    for backend in BACKENDS:
        lyrics = backend(artist, title)
        if lyrics:
            if isinstance(lyrics, str):
                lyrics = lyrics.decode('utf8', 'ignore')
            return lyrics


# Plugin logic.

def fetch_item_lyrics(lib, loglevel, item, write):
    """Fetch and store lyrics for a single item. If ``write``, then the
    lyrics will also be written to the file itself. The ``loglevel``
    parameter controls the visibility of the function's status log
    messages.
    """
    # Skip if the item already has lyrics.
    if item.lyrics:
        log.log(loglevel, u'lyrics already present: %s - %s' %
                          (item.artist, item.title))
        return

    # Fetch lyrics.
    lyrics = get_lyrics(item.artist, item.title)
    if not lyrics:
        log.log(loglevel, u'lyrics not found: %s - %s' %
                          (item.artist, item.title))
        return

    log.log(loglevel, u'fetched lyrics: %s - %s' %
                      (item.artist, item.title))
    item.lyrics = lyrics
    if write:
        item.write()
    lib.store(item)

AUTOFETCH = True
class LyricsPlugin(BeetsPlugin):
    def commands(self):
        cmd = ui.Subcommand('lyrics', help='fetch song lyrics')
        cmd.parser.add_option('-p', '--print', dest='printlyr',
                              action='store_true', default=False,
                              help='print lyrics to console')
        def func(lib, config, opts, args):
            # The "write to files" option corresponds to the
            # import_write config value.
            write = ui.config_val(config, 'beets', 'import_write',
                                  commands.DEFAULT_IMPORT_WRITE, bool)
            for item in lib.items(ui.decargs(args)):
                fetch_item_lyrics(lib, logging.INFO, item, write)
                if opts.printlyr and item.lyrics:
                    ui.print_(item.lyrics)
        cmd.func = func
        return [cmd]

    def configure(self, config):
        global AUTOFETCH
        AUTOFETCH = ui.config_val(config, 'lyrics', 'autofetch', True, bool)

# Auto-fetch lyrics on import.
@LyricsPlugin.listen('album_imported')
def album_imported(lib, album, config):
    if AUTOFETCH:
        for item in album.items():
            fetch_item_lyrics(lib, logging.DEBUG, item, config.write)
@LyricsPlugin.listen('item_imported')
def item_imported(lib, item, config):
    if AUTOFETCH:
        fetch_item_lyrics(lib, logging.DEBUG, item, config.write)
