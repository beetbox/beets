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

"""Tests for the 'lyrics' plugin"""

import os
import logging
import _common
from _common import unittest
from beetsplug import lyrics
from beets import config
from beets.util import confit
from bs4 import BeautifulSoup

log = logging.getLogger('beets')
LYRICS_TEXTS = confit.load_yaml(os.path.join(_common.RSRC, 'lyricstext.yaml'))

try:
    googlekey = config['lyrics']['google_API_key'].get(unicode)
except confit.NotFoundError:
    googlekey = None

# default query for tests
definfo = dict(artist=u'The Beatles', title=u'Lady Madonna')


class MockFetchUrl(object):
    def __init__(self, pathval='fetched_path'):
        self.pathval = pathval
        self.fetched = None

    def __call__(self, url, filename=None):
        self.fetched = url
        url = url.replace('http://', '').replace('www.', '')
        fn = "".join(x for x in url if (x.isalnum() or x == '/'))
        fn = fn.split('/')
        fn = os.path.join('rsrc', 'lyrics', fn[0], fn[-1]) + '.txt'
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
        return (ratio > .5 and ratio < 2)
    return False


class LyricsSourcesPluginTest(unittest.TestCase):
    # Every source entered in default beets google custom search engine
    # must be listed below.
    # Use default query when possible, or override artist and title field
    # if website don't have lyrics for default query.
    sourcesOk = [
      #  dict(definfo, url='http://www.songlyrics.com',
       #      path=u'/the-beatles/lady-madonna-lyrics'),
       # dict(definfo, url=u'http://www.elyricsworld.com',
        #     path=u'/lady_madonna_lyrics_beatles.html'),
        dict(artist=u'Beres Hammond', title=u'I could beat myself',
             url=u'http://www.reggaelyrics.info',
             path=u'/beres-hammond/i-could-beat-myself'),
        dict(definfo, artist=u'Lilly Wood & the prick', title=u"Hey it's ok",
             url=u'http://www.paroles.net/',
             path=u'lilly-wood-the-prick/paroles-hey-it-s-ok'),
        dict(definfo, artist=u'Amy Winehouse', title=u"Jazz'n'blues",
             url=u'http://www.lyricsontop.com',
             path=u'/amy-winehouse-songs/jazz-n-blues-lyrics.html'),
        dict(definfo, url=u'http://www.sweetslyrics.com',
             path=u'/761696.The%20Beatles%20-%20Lady%20Madonna.html'),
        dict(definfo, url=u'http://www.absolutelyrics.com',
             path=u'/lyrics/view/the_beatles/lady_madonna'),
        dict(definfo, url=u'http://www.azlyrics.com/',
             path=u'/lyrics/beatles/ladymadonna.html'),
        dict(definfo, url=u'http://www.chartlyrics.com',
             path=u'/_LsLsZ7P4EK-F-LD4dJgDQ/Lady+Madonna.aspx'),
        dict(definfo, artist=u'Lilly Wood & the prick', title=u"Hey it's ok",
             url=u'http://www.lyricsmania.com',
             path=u'/hey_its_ok_lyrics_lilly_wood_and_the_prick.html'),
        dict(definfo, url=u'http://www.lyrics007.com',
             path=u'/The%20Beatles%20Lyrics/Lady%20Madonna%20Lyrics.html'),
        dict(definfo, url=u'http://www.smartlyrics.com',
             path=u'/Song18148-The-Beatles-Lady-Madonna-lyrics.aspx'),
        dict(definfo, url='http://www.releaselyrics.com',
            path=u'/e35f/the-beatles-lady-madonna'),
        dict(definfo, url='http://www.metrolyrics.com/',
             path='lady-madonna-lyrics-beatles.html'),
    ]

    # Websites that can't be scraped yet.
    # The reason why the scraping fail is indicated before each source dict. 
    sourcesFail = [


        # Lyrics consist in multiple small <p> sections instead of a long one
        #dict(definfo, artist=u'Lilly Wood & the prick', title=u"Hey it's ok",
        #     url=u'http://www.lacoccinelle.net',
        #     path=u'/paroles-officielles/550512.html'),
    ]

    def setUp(self):
        """Set up configuration"""
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

    def test_sources_fail(self):
        for s in self.sourcesFail:
            url = s['url'] + s['path'] 
            html = lyrics.fetch_url(url)
            res = lyrics.scrape_lyrics_from_html(html)
            if lyrics.is_lyrics(res):
                if is_lyrics_content_ok(s['title'], res):
                    log.info(u'{0} can be added to sources :\n{1}'
                              .format(s['url'], res))
                else: 
                    log.info(u'{0} return invalid lyrics:\n{1}'.
                             format(s['url'], res))

    def test_is_page_candidate(self):
        for s in self.sourcesOk:
            url = unicode(s['url'] + s['path'])
            html = lyrics.fetch_url(url)
            soup = BeautifulSoup(html)
            if not soup.title:
                continue
            self.assertEqual(lyrics.is_page_candidate(url, soup.title.string,
                                                      s['title'], s['artist']),
                             True, url)


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
