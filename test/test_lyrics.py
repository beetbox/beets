# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2014, Fabrice Laporte.
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

import os
import _common
import sys
from _common import unittest
from beetsplug import lyrics
from beets.library import Item
from beets.util import confit


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
            self.assertFalse(lyrics.is_lyrics(t))

    def test_slugify(self):
        text = u"http://site.com/çafe-au_lait(boisson)"
        self.assertEqual(lyrics.slugify(text), 'http://site.com/cafe_au_lait')

    def test_scrape_strip_cruft(self):
        text = u"""<!--lyrics below-->
                  &nbsp;one
                  <br class='myclass'>
                  two  !
                  <br><br \>
                  <blink>four</blink>"""
        self.assertEqual(lyrics._scrape_strip_cruft(text, True),
                         "one\ntwo !\n\nfour")

    def test_scrape_merge_paragraphs(self):
        text = u"one</p>   <p class='myclass'>two</p><p>three"
        self.assertEqual(lyrics._scrape_merge_paragraphs(text),
                         "one\ntwo\nthree")


LYRICS_TEXTS = confit.load_yaml(os.path.join(_common.RSRC, 'lyricstext.yaml'))
definfo = dict(artist=u'The Beatles', title=u'Lady Madonna')  # default query


class MockFetchUrl(object):
    def __init__(self, pathval='fetched_path'):
        self.pathval = pathval
        self.fetched = None

    def __call__(self, url, filename=None):
        self.fetched = url
        url = url.replace('http://', '').replace('www.', '')
        fn = "".join(x for x in url if (x.isalnum() or x == '/'))
        fn = fn.split('/')
        fn = os.path.join(_common.RSRC, 'lyrics', fn[0], fn[-1]) + '.txt'
        with open(fn, 'r') as f:
            content = f.read()
        return content


def is_lyrics_content_ok(title, text):
    """Compare lyrics text to expected lyrics for given title"""

    setexpected = set(LYRICS_TEXTS[lyrics.slugify(title)].split())
    settext = set(text.split())
    setinter = setexpected.intersection(settext)
    # consider lyrics ok if they share 50% or more with the reference
    if len(setinter):
        ratio = 1.0 * max(len(setexpected), len(settext)) / len(setinter)
        return (ratio > .5 and ratio < 2.5)
    return False


class LyricsGooglePluginTest(unittest.TestCase):
    # Every source entered in default beets google custom search engine
    # must be listed below.
    # Use default query when possible, or override artist and title fields
    # if website don't have lyrics for default query.
    sourcesOk = [
        dict(definfo,
             url=u'http://www.absolutelyrics.com',
             path=u'/lyrics/view/the_beatles/lady_madonna'),
        dict(definfo,
             url=u'http://www.azlyrics.com',
             path=u'/lyrics/beatles/ladymadonna.html'),
        dict(definfo,
             url=u'http://www.chartlyrics.com',
             path=u'/_LsLsZ7P4EK-F-LD4dJgDQ/Lady+Madonna.aspx'),
        dict(definfo,
             url=u'http://www.elyricsworld.com',
             path=u'/lady_madonna_lyrics_beatles.html'),
        dict(definfo,
             url=u'http://www.lacoccinelle.net',
             artist=u'Jacques Brel', title=u"Amsterdam",
             path=u'/paroles-officielles/275679.html'),
        dict(definfo,
             url=u'http://www.lyrics007.com',
             path=u'/The%20Beatles%20Lyrics/Lady%20Madonna%20Lyrics.html'),
        dict(definfo,
             url='http://www.lyrics.com/',
             path=u'lady-madonna-lyrics-the-beatles.html'),
        dict(definfo,
             url='http://www.lyricsmania.com/',
             path='lady_madonna_lyrics_the_beatles.html'),
        dict(definfo,
             url=u'http://www.lyrics.net',
             path=u'/lyric/17547916'),
        dict(definfo,
             url=u'http://www.lyricsontop.com',
             artist=u'Amy Winehouse', title=u"Jazz'n'blues",
             path=u'/amy-winehouse-songs/jazz-n-blues-lyrics.html'),
        dict(definfo,
             url=u'http://lyrics.wikia.com/',
             path=u'The_Beatles:Lady_Madonna'),
        dict(definfo,
             url='http://www.metrolyrics.com/',
             path='lady-madonna-lyrics-beatles.html'),
        dict(definfo,
             url=u'http://www.onelyrics.net/',
             artist=u'Ben & Ellen Harper', title=u'City of dreams',
             path='ben-ellen-harper-city-of-dreams-lyrics'),
        dict(definfo,
             url=u'http://www.paroles.net/',
             artist=u'Lilly Wood & the prick', title=u"Hey it's ok",
             path=u'lilly-wood-the-prick/paroles-hey-it-s-ok'),
        dict(definfo,
             url=u'http://www.reggaelyrics.info',
             artist=u'Beres Hammond', title=u'I could beat myself',
             path=u'/beres-hammond/i-could-beat-myself'),
        dict(definfo,
             url='http://www.releaselyrics.com',
             path=u'/e35f/the-beatles-lady-madonna'),
        dict(definfo,
             url=u'http://www.smartlyrics.com',
             path=u'/Song18148-The-Beatles-Lady-Madonna-lyrics.aspx'),
        dict(definfo,
             url='http://www.songlyrics.com',
             path=u'/the-beatles/lady-madonna-lyrics'),
        dict(definfo,
             url=u'http://www.stlyrics.com',
             path=u'/songs/r/richiehavens48961/ladymadonna2069109.html'),
        dict(definfo,
             url=u'http://www.sweetslyrics.com',
             path=u'/761696.The%20Beatles%20-%20Lady%20Madonna.html')]

    def setUp(self):
        """Set up configuration"""

        try:
            __import__('bs4')
        except ImportError:
            self.skipTest('Beautiful Soup 4 not available')
        if sys.version_info[:3] < (2, 7, 3):
            self.skipTest("Python’s built-in HTML parser is not good enough")
        lyrics.LyricsPlugin()
        lyrics.fetch_url = MockFetchUrl()

    def test_default_ok(self):
        """Test each lyrics engine with the default query"""

        for f in (lyrics.fetch_lyricswiki, lyrics.fetch_lyricscom):
            res = f(definfo['artist'], definfo['title'])
            self.assertTrue(lyrics.is_lyrics(res))
            self.assertTrue(is_lyrics_content_ok(definfo['title'], res))

    def test_missing_lyrics(self):
        self.assertFalse(lyrics.is_lyrics(LYRICS_TEXTS['missing_texts']))

    def test_sources_ok(self):
        for s in self.sourcesOk:
            url = s['url'] + s['path']
            res = lyrics.scrape_lyrics_from_html(lyrics.fetch_url(url))
            self.assertTrue(lyrics.is_lyrics(res), url)
            self.assertTrue(is_lyrics_content_ok(s['title'], res), url)

    def test_is_page_candidate_exact_match(self):
        from bs4 import SoupStrainer, BeautifulSoup

        for s in self.sourcesOk:
            url = unicode(s['url'] + s['path'])
            html = lyrics.fetch_url(url)
            soup = BeautifulSoup(html, "html.parser",
                                 parse_only=SoupStrainer('title'))
            self.assertEqual(lyrics.is_page_candidate(url, soup.title.string,
                                                      s['title'], s['artist']),
                             True, url)

    def test_is_page_candidate_fuzzy_match(self):
        url = u'http://www.example.com/lazy_madonna_beatles'
        urlTitle = u'example.com | lazy madonna lyrics by the beatles'
        title = u'Lady Madonna'
        artist = u'The Beatles'
        # very small diffs (typo) are ok
        self.assertEqual(lyrics.is_page_candidate(url, urlTitle, title,
                         artist), True, url)
        # reject different title
        urlTitle = u'example.com | busy madonna lyrics by the beatles'
        self.assertEqual(lyrics.is_page_candidate(url, urlTitle, title,
                         artist), False, url)
        # (title, artist) != (artist, title)
        urlTitle = u'example.com | the beatles lyrics by Lazy Madonna'
        self.assertEqual(lyrics.is_page_candidate(url, urlTitle, title,
                         artist), False, url)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
