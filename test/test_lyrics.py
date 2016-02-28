# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Fabrice Laporte.
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

"""Tests for the 'lyrics' plugin."""

from __future__ import division, absolute_import, print_function

import os
from test import _common
import sys
import re

from mock import MagicMock

from test._common import unittest
from beetsplug import lyrics
from beets.library import Item
from beets.util import confit
from beets import logging

log = logging.getLogger('beets.test_lyrics')
raw_backend = lyrics.Backend({}, log)
google = lyrics.Google(MagicMock(), log)


class LyricsPluginTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration"""
        lyrics.LyricsPlugin()

    def test_search_artist(self):
        item = Item(artist='Alice ft. Bob', title='song')
        self.assertIn(('Alice ft. Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

        item = Item(artist='Alice feat Bob', title='song')
        self.assertIn(('Alice feat Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

        item = Item(artist='Alice feat. Bob', title='song')
        self.assertIn(('Alice feat. Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

        item = Item(artist='Alice feats Bob', title='song')
        self.assertIn(('Alice feats Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertNotIn(('Alice', ['song']),
                         lyrics.search_pairs(item))

        item = Item(artist='Alice featuring Bob', title='song')
        self.assertIn(('Alice featuring Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

        item = Item(artist='Alice & Bob', title='song')
        self.assertIn(('Alice & Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

        item = Item(artist='Alice and Bob', title='song')
        self.assertIn(('Alice and Bob', ['song']),
                      lyrics.search_pairs(item))
        self.assertIn(('Alice', ['song']),
                      lyrics.search_pairs(item))

    def test_search_pairs_multi_titles(self):
        item = Item(title='1 / 2', artist='A')
        self.assertIn(('A', ['1 / 2']), lyrics.search_pairs(item))
        self.assertIn(('A', ['1', '2']), lyrics.search_pairs(item))

        item = Item(title='1/2', artist='A')
        self.assertIn(('A', ['1/2']), lyrics.search_pairs(item))
        self.assertIn(('A', ['1', '2']), lyrics.search_pairs(item))

    def test_search_pairs_titles(self):
        item = Item(title='Song (live)', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song (live)']), lyrics.search_pairs(item))

        item = Item(title='Song (live) (new)', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song (live) (new)']), lyrics.search_pairs(item))

        item = Item(title='Song (live (new))', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song (live (new))']), lyrics.search_pairs(item))

        item = Item(title='Song ft. B', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song ft. B']), lyrics.search_pairs(item))

        item = Item(title='Song featuring B', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song featuring B']), lyrics.search_pairs(item))

        item = Item(title='Song and B', artist='A')
        self.assertNotIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song and B']), lyrics.search_pairs(item))

    def test_remove_credits(self):
        self.assertEqual(
            lyrics.remove_credits("""It's close to midnight
                                     Lyrics brought by example.com"""),
            "It's close to midnight"
        )
        self.assertEqual(
            lyrics.remove_credits("""Lyrics brought by example.com"""),
            ""
        )

        # don't remove 2nd verse for the only reason it contains 'lyrics' word
        text = """Look at all the shit that i done bought her
                  See lyrics ain't nothin
                  if the beat aint crackin"""
        self.assertEqual(lyrics.remove_credits(text), text)

    def test_is_lyrics(self):
        texts = ['LyricsMania.com - Copyright (c) 2013 - All Rights Reserved']
        texts += ["""All material found on this site is property\n
                     of mywickedsongtext brand"""]
        for t in texts:
            self.assertFalse(google.is_lyrics(t))

    def test_slugify(self):
        text = u"http://site.com/\xe7afe-au_lait(boisson)"
        self.assertEqual(google.slugify(text),
                         'http://site.com/cafe_au_lait')

    def test_scrape_strip_cruft(self):
        text = u"""<!--lyrics below-->
                  &nbsp;one
                  <br class='myclass'>
                  two  !
                  <br><br \>
                  <blink>four</blink>"""
        self.assertEqual(lyrics._scrape_strip_cruft(text, True),
                         "one\ntwo !\n\nfour")

    def test_scrape_strip_scripts(self):
        text = u"""foo<script>bar</script>baz"""
        self.assertEqual(lyrics._scrape_strip_cruft(text, True),
                         "foobaz")

    def test_scrape_strip_tag_in_comment(self):
        text = u"""foo<!--<bar>-->qux"""
        self.assertEqual(lyrics._scrape_strip_cruft(text, True),
                         "fooqux")

    def test_scrape_merge_paragraphs(self):
        text = u"one</p>   <p class='myclass'>two</p><p>three"
        self.assertEqual(lyrics._scrape_merge_paragraphs(text),
                         "one\ntwo\nthree")

    def test_missing_lyrics(self):
        self.assertFalse(google.is_lyrics(LYRICS_TEXTS['missing_texts']))


def url_to_filename(url):
    url = re.sub(r'https?://|www.', '', url)
    fn = "".join(x for x in url if (x.isalnum() or x == '/'))
    fn = fn.split('/')
    fn = os.path.join(LYRICS_ROOT_DIR, fn[0], fn[-1]) + '.txt'
    return fn


def check_lyrics_fetched():
    """Return True if lyrics_download_samples.py has been runned and lyrics
    pages are present in resources directory"""
    lyrics_dirs = len([d for d in os.listdir(LYRICS_ROOT_DIR) if
                      os.path.isdir(os.path.join(LYRICS_ROOT_DIR, d))])
    # example.com is the only lyrics dir added to repo
    return lyrics_dirs > 1


class MockFetchUrl(object):
    def __init__(self, pathval='fetched_path'):
        self.pathval = pathval
        self.fetched = None

    def __call__(self, url, filename=None):
        self.fetched = url
        fn = url_to_filename(url)
        with open(fn, 'r') as f:
            content = f.read()
        return content


def is_lyrics_content_ok(title, text):
    """Compare lyrics text to expected lyrics for given title"""

    keywords = LYRICS_TEXTS[google.slugify(title)]
    return all(x in text.lower() for x in keywords)

LYRICS_ROOT_DIR = os.path.join(_common.RSRC, 'lyrics')
LYRICS_TEXTS = confit.load_yaml(os.path.join(_common.RSRC, 'lyricstext.yaml'))
DEFAULT_SONG = dict(artist=u'The Beatles', title=u'Lady Madonna')

DEFAULT_SOURCES = [
    dict(DEFAULT_SONG, url=u'http://lyrics.wikia.com/',
         path=u'The_Beatles:Lady_Madonna'),
    dict(artist=u'Santana', title=u'Black magic woman',
         url='http://www.lyrics.com/',
         path=u'black-magic-woman-lyrics-santana.html'),
    dict(DEFAULT_SONG, url='https://www.musixmatch.com/',
         path=u'lyrics/The-Beatles/Lady-Madonna'),
]

# Every source entered in default beets google custom search engine
# must be listed below.
# Use default query when possible, or override artist and title fields
# if website don't have lyrics for default query.
GOOGLE_SOURCES = [
    dict(DEFAULT_SONG,
         url=u'http://www.absolutelyrics.com',
         path=u'/lyrics/view/the_beatles/lady_madonna'),
    dict(DEFAULT_SONG,
         url=u'http://www.azlyrics.com',
         path=u'/lyrics/beatles/ladymadonna.html'),
    dict(DEFAULT_SONG,
         url=u'http://www.chartlyrics.com',
         path=u'/_LsLsZ7P4EK-F-LD4dJgDQ/Lady+Madonna.aspx'),
    dict(DEFAULT_SONG,
         url=u'http://www.elyricsworld.com',
         path=u'/lady_madonna_lyrics_beatles.html'),
    dict(url=u'http://www.lacoccinelle.net',
         artist=u'Jacques Brel', title=u"Amsterdam",
         path=u'/paroles-officielles/275679.html'),
    dict(DEFAULT_SONG,
         url=u'http://letras.mus.br/', path=u'the-beatles/275/'),
    dict(DEFAULT_SONG,
         url='http://www.lyricsmania.com/',
         path='lady_madonna_lyrics_the_beatles.html'),
    dict(artist=u'Santana', title=u'Black magic woman',
         url='http://www.lyrics.com/',
         path=u'black-magic-woman-lyrics-santana.html'),
    dict(DEFAULT_SONG, url=u'http://lyrics.wikia.com/',
         path=u'The_Beatles:Lady_Madonna'),
    dict(DEFAULT_SONG,
         url=u'http://www.lyrics.net', path=u'/lyric/19110224'),
    dict(DEFAULT_SONG,
         url=u'http://www.lyricsmode.com',
         path=u'/lyrics/b/beatles/lady_madonna.html'),
    dict(url=u'http://www.lyricsontop.com',
         artist=u'Amy Winehouse', title=u"Jazz'n'blues",
         path=u'/amy-winehouse-songs/jazz-n-blues-lyrics.html'),
    dict(DEFAULT_SONG,
         url='http://www.metrolyrics.com/',
         path='lady-madonna-lyrics-beatles.html'),
    dict(url='http://www.musica.com/', path='letras.asp?letra=2738',
         artist=u'Santana', title=u'Black magic woman'),
    dict(DEFAULT_SONG,
         url=u'http://www.onelyrics.net/',
         artist=u'Ben & Ellen Harper', title=u'City of dreams',
         path='ben-ellen-harper-city-of-dreams-lyrics'),
    dict(url=u'http://www.paroles.net/',
         artist=u'Lilly Wood & the prick', title=u"Hey it's ok",
         path=u'lilly-wood-the-prick/paroles-hey-it-s-ok'),
    dict(DEFAULT_SONG,
         url='http://www.releaselyrics.com',
         path=u'/346e/the-beatles-lady-madonna-(love-version)/'),
    dict(DEFAULT_SONG,
         url=u'http://www.smartlyrics.com',
         path=u'/Song18148-The-Beatles-Lady-Madonna-lyrics.aspx'),
    dict(DEFAULT_SONG,
         url='http://www.songlyrics.com',
         path=u'/the-beatles/lady-madonna-lyrics'),
    dict(DEFAULT_SONG,
         url=u'http://www.stlyrics.com',
         path=u'/songs/r/richiehavens48961/ladymadonna2069109.html'),
    dict(DEFAULT_SONG,
         url=u'http://www.sweetslyrics.com',
         path=u'/761696.The%20Beatles%20-%20Lady%20Madonna.html')
]


class LyricsGooglePluginTest(unittest.TestCase):
    """Test scraping heuristics on a fake html page.
    Or run lyrics_download_samples.py first to check that beets google
    custom search engine sources are correctly scraped.
    """
    source = dict(url=u'http://www.example.com', artist=u'John Doe',
                  title=u'Beets song', path=u'/lyrics/beetssong')

    def setUp(self):
        """Set up configuration"""
        try:
            __import__('bs4')
        except ImportError:
            self.skipTest('Beautiful Soup 4 not available')
        if sys.version_info[:3] < (2, 7, 3):
            self.skipTest("Python's built-in HTML parser is not good enough")
        lyrics.LyricsPlugin()
        raw_backend.fetch_url = MockFetchUrl()

    def test_mocked_source_ok(self):
        """Test that lyrics of the mocked page are correctly scraped"""
        url = self.source['url'] + self.source['path']
        if os.path.isfile(url_to_filename(url)):
            res = lyrics.scrape_lyrics_from_html(raw_backend.fetch_url(url))
            self.assertTrue(google.is_lyrics(res), url)
            self.assertTrue(is_lyrics_content_ok(self.source['title'], res),
                            url)

    def test_google_sources_ok(self):
        """Test if lyrics present on websites registered in beets google custom
        search engine are correctly scraped."""
        if not check_lyrics_fetched():
            self.skipTest("Run lyrics_download_samples.py script first.")
        for s in GOOGLE_SOURCES:
            url = s['url'] + s['path']
            if os.path.isfile(url_to_filename(url)):
                res = lyrics.scrape_lyrics_from_html(
                    raw_backend.fetch_url(url))
                self.assertTrue(google.is_lyrics(res), url)
                self.assertTrue(is_lyrics_content_ok(s['title'], res), url)

    def test_default_ok(self):
        """Test default engines with the default query"""
        if not check_lyrics_fetched():
            self.skipTest("Run lyrics_download_samples.py script first.")
        for (source, s) in zip([lyrics.LyricsWiki,
                                lyrics.LyricsCom,
                                lyrics.MusiXmatch], DEFAULT_SOURCES):
            url = s['url'] + s['path']
            if os.path.isfile(url_to_filename(url)):
                res = source({}, log).fetch(s['artist'], s['title'])
                self.assertTrue(google.is_lyrics(res), url)
                self.assertTrue(is_lyrics_content_ok(s['title'], res), url)

    def test_is_page_candidate_exact_match(self):
        """Test matching html page title with song infos -- when song infos are
        present in the title."""
        from bs4 import SoupStrainer, BeautifulSoup
        s = self.source
        url = unicode(s['url'] + s['path'])
        html = raw_backend.fetch_url(url)
        soup = BeautifulSoup(html, "html.parser",
                             parse_only=SoupStrainer('title'))
        self.assertEqual(google.is_page_candidate(url, soup.title.string,
                                                  s['title'], s['artist']),
                         True, url)

    def test_is_page_candidate_fuzzy_match(self):
        """Test matching html page title with song infos -- when song infos are
        not present in the title."""
        s = self.source
        url = s['url'] + s['path']
        urlTitle = u'example.com | Beats song by John doe'

        # very small diffs (typo) are ok eg 'beats' vs 'beets' with same artist
        self.assertEqual(google.is_page_candidate(url, urlTitle, s['title'],
                         s['artist']), True, url)
        # reject different title
        urlTitle = u'example.com | seets bong lyrics by John doe'
        self.assertEqual(google.is_page_candidate(url, urlTitle, s['title'],
                         s['artist']), False, url)

    def test_is_page_candidate_special_chars(self):
        """Ensure that `is_page_candidate` doesn't crash when the artist
        and such contain special regular expression characters.
        """
        # https://github.com/beetbox/beets/issues/1673
        s = self.source
        url = s['url'] + s['path']
        url_title = u'foo'

        google.is_page_candidate(url, url_title, s['title'], u'Sunn O)))')


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == b'__main__':
    unittest.main(defaultTest='suite')
