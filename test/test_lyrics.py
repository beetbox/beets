#!/usr/bin/python
# -*- coding: UTF-8 -*-

"""Tests for the 'lyrics' plugin"""

import _common
from _common import unittest
import _lyricstext
from beetsplug import lyrics
from beets import config
from beets.util import confit
from bs4 import BeautifulSoup

try:
    googlekey = config['lyrics']['google_API_key'].get(unicode)
except confit.NotFoundError :
    googlekey = None

# default query for tests
definfo = dict(artist=u'The Beatles',title=u'Lady Madonna')


def is_lyrics_content_ok(title, text):
    """Compare lyrics text to expected lyrics for given title"""

    setexpected = set(_lyricstext.texts[title].split())
    settext = set(text.split())
    setinter = setexpected.intersection(settext)
    # consider lyrics ok if they share 50% or more with the reference
    if len(setinter):
        ratio = 1.0*max(len(setexpected), len(settext)) / len(setinter)
        return (ratio > .5 and ratio < 2)
    return False

class LyricsPluginTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration"""
        lyrics.LyricsPlugin()

    def test_default_ok(self):
        """Test each lyrics engine with the default query"""

        self.assertNotEqual(lyrics.fetch_lyricswiki(definfo['artist'], definfo['title']), None)
        self.assertNotEqual(lyrics.fetch_lyricscom(definfo['artist'], definfo['title']), None)
        if googlekey:
            self.assertNotEqual(lyrics.fetch_google(definfo['artist'], definfo['title']), None)

class LyricsScrapingPluginTest(unittest.TestCase):

    # Every source entered in default beets google custom search engine
    # must be listed below.
    # Use default query when possible, or override artist and title field
    # if website don't have lyrics for default query.
    sourcesOk = [  \
        dict(definfo, artist=u'Lilly Wood & the prick',title=u"Hey it's ok",
            url=u'http://www.paroles.net/',
            path=u'lilly-wood-the-prick/paroles-hey-it-s-ok'),
        dict(definfo, artist=u'Amy Winehouse',title=u"Jazz'n'blues", 
            url=u'http://www.lyricsontop.com', 
            path=u'/amy-winehouse-songs/jazz-n-blues-lyrics.html'),
        dict(definfo, url=u'http://www.sweetslyrics.com', 
            path=u'/761696.The%20Beatles%20-%20Lady%20Madonna.html'),  
        dict(definfo, url=u'http://www.lyrics007.com', 
            path=u'/The%20Beatles%20Lyrics/Lady%20Madonna%20Lyrics.html'),   
        dict(definfo, url=u'http://lyrics.wikia.com', 
            path=u'/The_Beatles:Lady_Madonna'),  
        dict(definfo, url=u'http://www.absolutelyrics.com', 
            path=u'/lyrics/view/the_beatles/lady_madonna'),
        dict(definfo, url=u'http://www.azlyrics.com/', 
            path=u'/lyrics/beatles/ladymadonna.html'),
        dict(definfo, url=u'http://www.smartlyrics.com', 
            path=u'/Song18148-The-Beatles-Lady-Madonna-lyrics.aspx'),
        dict(definfo, url=u'http://www.elyricsworld.com', 
            path=u'/lady_madonna_lyrics_beatles.html'),
        dict(artist=u'Beres Hammond',title=u'I could beat myself',
            url=u'http://www.reggaelyrics.info', 
            path=u'/beres-hammond/i-could-beat-myself/'),
        dict(artist=u'Beres Hammond',title=u'I could beat myself',
            url=u'http://www.jah-lyrics.com',
            path='/index.php?songid=5632'),
        dict(definfo, artist=u'Lilly Wood & the prick',title=u"Hey it's ok",
            url=u'http://www.lyricsmania.com',
            path=u'/hey_its_ok_lyrics_lilly_wood_and_the_prick.html'),
              ]  

    # Websites that can't be scraped yet and whose results must be 
    # flagged as invalid lyrics.    
    sourcesFail = [
        dict(definfo, url=u'http://www.chartlyrics.com', 
            path=u'/_LsLsZ7P4EK-F-LD4dJgDQ/Lady+Madonna.aspx'),
        dict(definfo, url='http://www.songlyrics.com',
            path=u'/the-beatles/lady-madonna-lyrics/'),
        dict(definfo, url='http://www.maxilyrics.com',
            path=u'/the-beatles-lady-madonna-lyrics-92e7.html'),
        dict(definfo, url='http://www.metrolyrics.com/', 
            path='best-for-last-lyrics-adele.html')
    ]

    # Websites that return truncated lyrics because of scraping issues, and 
    # thus should not be included as sources to Google CSE.
    # They are good candidates for later inclusion after improvement
    # iterations of the scraping algorithm.
    sourcesIncomplete = [
        dict(definfo, artist=u'Lilly Wood & the prick',title=u"Hey it's ok",
            url=u'http://www.lacoccinelle.net', 
            path=u'/paroles-officielles/550512.html'),
        ]

    def test_sources_ok(self):
        for s in self.sourcesOk:
            url = s['url']+s['path']
            res = lyrics.scrape_lyrics_from_url(url)
            self.assertTrue(lyrics.is_lyrics(res), url)
            self.assertTrue(is_lyrics_content_ok(s['title'], res), url)

    def test_sources_fail(self):
        for s in self.sourcesFail:
            url = s['url']+s['path']
            res = lyrics.scrape_lyrics_from_url(url)
            # very unlikely these sources pass if the scraping algo is not
            # tweaked on purpose for these cases
            self.assertFalse(lyrics.is_lyrics(res), res)

    def test_missing_lyrics(self):
        for msg in _lyricstext.missing_texts:
            self.assertFalse(lyrics.is_lyrics(msg), msg)

    def test_sources_incomplete(self):
        for s in self.sourcesIncomplete:
            url = s['url']+s['path']
            res = lyrics.scrape_lyrics_from_url(url)

            self.assertTrue(lyrics.is_lyrics(res))
            # these sources may pass if the html source evolve or after 
            # a random improvement in the scraping algo: we want to
            # be noticed if it's the case.
            if is_lyrics_content_ok(s['title'], res):
                print('Source %s actually return valid lyrics!' % s['url'])

    def test_remove_featuring_artist(self):
        self.assertEqual(lyrics.remove_featuring_artist('Bob featuring Marcia'), 'Bob')
        self.assertEqual(lyrics.remove_featuring_artist('Bob feat Marcia'), 'Bob')
        self.assertEqual(lyrics.remove_featuring_artist('Bob and Marcia'), 'Bob')
        self.assertEqual(lyrics.remove_featuring_artist('Bob feat. Marcia'), 'Bob')
        self.assertEqual(lyrics.remove_featuring_artist('Bob & Marcia'), 'Bob')
        self.assertEqual(lyrics.remove_featuring_artist('Bob feats Marcia'), 'Bob feats Marcia')

    def test_is_page_candidate(self):
        for s in self.sourcesOk:
            url = unicode(s['url']+s['path'])
            html = lyrics.fetch_url(url)
            soup = BeautifulSoup(html)
            if not soup.title:
                continue
            self.assertEqual(lyrics.is_page_candidate(url, soup.title.string, s['title'], s['artist']), True)
        
def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')

