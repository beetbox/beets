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

from __future__ import absolute_import, division, print_function

import itertools
from io import open
import os
import re
import six
import sys
import unittest

import confuse
from mock import MagicMock, patch

from beets import logging
from beets.library import Item
from beets.util import bytestring_path
from beetsplug import lyrics
from test import _common


log = logging.getLogger('beets.test_lyrics')
raw_backend = lyrics.Backend({}, log)
google = lyrics.Google(MagicMock(), log)
genius = lyrics.Genius(MagicMock(), log)


class LyricsPluginTest(unittest.TestCase):

    def setUp(self):
        """Set up configuration."""
        lyrics.LyricsPlugin()

    def test_search_artist(self):
        item = Item(artist=u'Alice ft. Bob', title=u'song')
        self.assertIn((u'Alice ft. Bob', [u'song']),
                      lyrics.search_pairs(item))
        self.assertIn((u'Alice', [u'song']),
                      lyrics.search_pairs(item))

        item = Item(artist=u'Alice feat Bob', title=u'song')
        self.assertIn((u'Alice feat Bob', [u'song']),
                      lyrics.search_pairs(item))
        self.assertIn((u'Alice', [u'song']),
                      lyrics.search_pairs(item))

        item = Item(artist=u'Alice feat. Bob', title=u'song')
        self.assertIn((u'Alice feat. Bob', [u'song']),
                      lyrics.search_pairs(item))
        self.assertIn((u'Alice', [u'song']),
                      lyrics.search_pairs(item))

        item = Item(artist=u'Alice feats Bob', title=u'song')
        self.assertIn((u'Alice feats Bob', [u'song']),
                      lyrics.search_pairs(item))
        self.assertNotIn((u'Alice', [u'song']),
                         lyrics.search_pairs(item))

        item = Item(artist=u'Alice featuring Bob', title=u'song')
        self.assertIn((u'Alice featuring Bob', [u'song']),
                      lyrics.search_pairs(item))
        self.assertIn((u'Alice', [u'song']),
                      lyrics.search_pairs(item))

        item = Item(artist=u'Alice & Bob', title=u'song')
        self.assertIn((u'Alice & Bob', [u'song']),
                      lyrics.search_pairs(item))
        self.assertIn((u'Alice', [u'song']),
                      lyrics.search_pairs(item))

        item = Item(artist=u'Alice and Bob', title=u'song')
        self.assertIn((u'Alice and Bob', [u'song']),
                      lyrics.search_pairs(item))
        self.assertIn((u'Alice', [u'song']),
                      lyrics.search_pairs(item))

        item = Item(artist=u'Alice and Bob', title=u'song')
        self.assertEqual((u'Alice and Bob', [u'song']),
                         list(lyrics.search_pairs(item))[0])

    def test_search_artist_sort(self):
        item = Item(artist=u'CHVRCHΞS', title=u'song', artist_sort=u'CHVRCHES')
        self.assertIn((u'CHVRCHΞS', [u'song']),
                      lyrics.search_pairs(item))
        self.assertIn((u'CHVRCHES', [u'song']),
                      lyrics.search_pairs(item))

        # Make sure that the original artist name is still the first entry
        self.assertEqual((u'CHVRCHΞS', [u'song']),
                         list(lyrics.search_pairs(item))[0])

        item = Item(artist=u'横山克', title=u'song',
                    artist_sort=u'Masaru Yokoyama')
        self.assertIn((u'横山克', [u'song']),
                      lyrics.search_pairs(item))
        self.assertIn((u'Masaru Yokoyama', [u'song']),
                      lyrics.search_pairs(item))

        # Make sure that the original artist name is still the first entry
        self.assertEqual((u'横山克', [u'song']),
                         list(lyrics.search_pairs(item))[0])

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

        item = Item(title='Song: B', artist='A')
        self.assertIn(('A', ['Song']), lyrics.search_pairs(item))
        self.assertIn(('A', ['Song: B']), lyrics.search_pairs(item))

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
                  <br><br \\>
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
    fn = os.path.join(LYRICS_ROOT_DIR,
                      bytestring_path(fn[0]),
                      bytestring_path(fn[-1] + '.txt'))
    return fn


class MockFetchUrl(object):

    def __init__(self, pathval='fetched_path'):
        self.pathval = pathval
        self.fetched = None

    def __call__(self, url, filename=None):
        self.fetched = url
        fn = url_to_filename(url)
        with open(fn, 'r', encoding="utf8") as f:
            content = f.read()
        return content


def is_lyrics_content_ok(title, text):
    """Compare lyrics text to expected lyrics for given title."""
    if not text:
        return
    keywords = set(LYRICS_TEXTS[google.slugify(title)].split())
    words = set(x.strip(".?, ") for x in text.lower().split())
    return keywords <= words

LYRICS_ROOT_DIR = os.path.join(_common.RSRC, b'lyrics')
yaml_path = os.path.join(_common.RSRC, b'lyricstext.yaml')
LYRICS_TEXTS = confuse.load_yaml(yaml_path)


class LyricsGoogleBaseTest(unittest.TestCase):

    def setUp(self):
        """Set up configuration."""
        try:
            __import__('bs4')
        except ImportError:
            self.skipTest('Beautiful Soup 4 not available')
        if sys.version_info[:3] < (2, 7, 3):
            self.skipTest("Python's built-in HTML parser is not good enough")


class LyricsPluginSourcesTest(LyricsGoogleBaseTest):
    """Check that beets google custom search engine sources are correctly
       scraped.
    """

    DEFAULT_SONG = dict(artist=u'The Beatles', title=u'Lady Madonna')

    DEFAULT_SOURCES = [
        # dict(artist=u'Santana', title=u'Black magic woman',
        #      backend=lyrics.MusiXmatch),
        dict(DEFAULT_SONG, backend=lyrics.Genius,
             # GitHub actions is on some form of Cloudflare blacklist.
             skip=os.environ.get('GITHUB_ACTIONS') == 'true'),
        dict(artist=u'Boy In Space', title=u'u n eye',
             backend=lyrics.Tekstowo),
    ]

    GOOGLE_SOURCES = [
        dict(DEFAULT_SONG,
             url=u'http://www.absolutelyrics.com',
             path=u'/lyrics/view/the_beatles/lady_madonna'),
        dict(DEFAULT_SONG,
             url=u'http://www.azlyrics.com',
             path=u'/lyrics/beatles/ladymadonna.html',
             # AZLyrics returns a 403 on GitHub actions.
             skip=os.environ.get('GITHUB_ACTIONS') == 'true'),
        dict(DEFAULT_SONG,
             url=u'http://www.chartlyrics.com',
             path=u'/_LsLsZ7P4EK-F-LD4dJgDQ/Lady+Madonna.aspx'),
        # dict(DEFAULT_SONG,
        #      url=u'http://www.elyricsworld.com',
        #      path=u'/lady_madonna_lyrics_beatles.html'),
        dict(url=u'http://www.lacoccinelle.net',
             artist=u'Jacques Brel', title=u"Amsterdam",
             path=u'/paroles-officielles/275679.html'),
        dict(DEFAULT_SONG,
             url=u'http://letras.mus.br/', path=u'the-beatles/275/'),
        dict(DEFAULT_SONG,
             url='http://www.lyricsmania.com/',
             path='lady_madonna_lyrics_the_beatles.html'),
        dict(DEFAULT_SONG,
             url=u'http://www.lyricsmode.com',
             path=u'/lyrics/b/beatles/lady_madonna.html'),
        dict(url=u'http://www.lyricsontop.com',
             artist=u'Amy Winehouse', title=u"Jazz'n'blues",
             path=u'/amy-winehouse-songs/jazz-n-blues-lyrics.html'),
        # dict(DEFAULT_SONG,
        #      url='http://www.metrolyrics.com/',
        #      path='lady-madonna-lyrics-beatles.html'),
        # dict(url='http://www.musica.com/', path='letras.asp?letra=2738',
        #      artist=u'Santana', title=u'Black magic woman'),
        dict(url=u'http://www.paroles.net/',
             artist=u'Lilly Wood & the prick', title=u"Hey it's ok",
             path=u'lilly-wood-the-prick/paroles-hey-it-s-ok'),
        dict(DEFAULT_SONG,
             url='http://www.songlyrics.com',
             path=u'/the-beatles/lady-madonna-lyrics'),
        dict(DEFAULT_SONG,
             url=u'http://www.sweetslyrics.com',
             path=u'/761696.The%20Beatles%20-%20Lady%20Madonna.html')
    ]

    def setUp(self):
        LyricsGoogleBaseTest.setUp(self)
        self.plugin = lyrics.LyricsPlugin()

    @unittest.skipUnless(
        os.environ.get('INTEGRATION_TEST', '0') == '1',
        'integration testing not enabled')
    def test_backend_sources_ok(self):
        """Test default backends with songs known to exist in respective databases.
        """
        errors = []
        # Don't test any sources marked as skipped.
        sources = [s for s in self.DEFAULT_SOURCES if not s.get("skip", False)]
        for s in sources:
            res = s['backend'](self.plugin.config, self.plugin._log).fetch(
                s['artist'], s['title'])
            if not is_lyrics_content_ok(s['title'], res):
                errors.append(s['backend'].__name__)
        self.assertFalse(errors)

    @unittest.skipUnless(
        os.environ.get('INTEGRATION_TEST', '0') == '1',
        'integration testing not enabled')
    def test_google_sources_ok(self):
        """Test if lyrics present on websites registered in beets google custom
           search engine are correctly scraped.
        """
        # Don't test any sources marked as skipped.
        sources = [s for s in self.GOOGLE_SOURCES if not s.get("skip", False)]
        for s in sources:
            url = s['url'] + s['path']
            res = lyrics.scrape_lyrics_from_html(
                raw_backend.fetch_url(url))
            self.assertTrue(google.is_lyrics(res), url)
            self.assertTrue(is_lyrics_content_ok(s['title'], res), url)


class LyricsGooglePluginMachineryTest(LyricsGoogleBaseTest):
    """Test scraping heuristics on a fake html page.
    """

    source = dict(url=u'http://www.example.com', artist=u'John Doe',
                  title=u'Beets song', path=u'/lyrics/beetssong')

    def setUp(self):
        """Set up configuration"""
        LyricsGoogleBaseTest.setUp(self)
        self.plugin = lyrics.LyricsPlugin()

    @patch.object(lyrics.Backend, 'fetch_url', MockFetchUrl())
    def test_mocked_source_ok(self):
        """Test that lyrics of the mocked page are correctly scraped"""
        url = self.source['url'] + self.source['path']
        res = lyrics.scrape_lyrics_from_html(raw_backend.fetch_url(url))
        self.assertTrue(google.is_lyrics(res), url)
        self.assertTrue(is_lyrics_content_ok(self.source['title'], res),
                        url)

    @patch.object(lyrics.Backend, 'fetch_url', MockFetchUrl())
    def test_is_page_candidate_exact_match(self):
        """Test matching html page title with song infos -- when song infos are
           present in the title.
        """
        from bs4 import SoupStrainer, BeautifulSoup
        s = self.source
        url = six.text_type(s['url'] + s['path'])
        html = raw_backend.fetch_url(url)
        soup = BeautifulSoup(html, "html.parser",
                             parse_only=SoupStrainer('title'))
        self.assertEqual(
            google.is_page_candidate(url, soup.title.string,
                                     s['title'], s['artist']), True, url)

    def test_is_page_candidate_fuzzy_match(self):
        """Test matching html page title with song infos -- when song infos are
           not present in the title.
        """
        s = self.source
        url = s['url'] + s['path']
        url_title = u'example.com | Beats song by John doe'

        # very small diffs (typo) are ok eg 'beats' vs 'beets' with same artist
        self.assertEqual(google.is_page_candidate(url, url_title, s['title'],
                                                  s['artist']), True, url)
        # reject different title
        url_title = u'example.com | seets bong lyrics by John doe'
        self.assertEqual(google.is_page_candidate(url, url_title, s['title'],
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


# test Genius backend

class GeniusBaseTest(unittest.TestCase):
    def setUp(self):
        """Set up configuration."""
        try:
            __import__('bs4')
        except ImportError:
            self.skipTest('Beautiful Soup 4 not available')
        if sys.version_info[:3] < (2, 7, 3):
            self.skipTest("Python's built-in HTML parser is not good enough")


class GeniusScrapeLyricsFromHtmlTest(GeniusBaseTest):
    """tests Genius._scrape_lyrics_from_html()"""

    def setUp(self):
        """Set up configuration"""
        GeniusBaseTest.setUp(self)
        self.plugin = lyrics.LyricsPlugin()

    def test_no_lyrics_div(self):
        """Ensure we don't crash when the scraping the html for a genius page
        doesn't contain <div class="lyrics"></div>
        """
        # https://github.com/beetbox/beets/issues/3535
        # expected return value None
        url = 'https://genius.com/sample'
        mock = MockFetchUrl()
        self.assertEqual(genius._scrape_lyrics_from_html(mock(url)), None)

    def test_good_lyrics(self):
        """Ensure we are able to scrape a page with lyrics"""
        url = 'https://genius.com/Wu-tang-clan-cream-lyrics'
        mock = MockFetchUrl()
        self.assertIsNotNone(genius._scrape_lyrics_from_html(mock(url)))

    # TODO: find an example of a lyrics page with multiple divs and test it


class GeniusFetchTest(GeniusBaseTest):
    """tests Genius.fetch()"""

    def setUp(self):
        """Set up configuration"""
        GeniusBaseTest.setUp(self)
        self.plugin = lyrics.LyricsPlugin()

    @patch.object(lyrics.Genius, '_scrape_lyrics_from_html')
    @patch.object(lyrics.Backend, 'fetch_url', return_value=True)
    def test_json(self, mock_fetch_url, mock_scrape):
        """Ensure we're finding artist matches"""
        with patch.object(
            lyrics.Genius, '_search', return_value={
                "response": {
                    "hits": [
                        {
                            "result": {
                                "primary_artist": {
                                    "name": u"\u200Bblackbear",
                                    },
                                "url": "blackbear_url"
                                }
                        },
                        {
                            "result": {
                                "primary_artist": {
                                    "name": u"El\u002Dp"
                                    },
                                "url": "El-p_url"
                                }
                        }
                    ]
                }
            }
        ) as mock_json:
            # genius uses zero-width-spaces (\u200B) for lowercase
            # artists so we make sure we can match those
            self.assertIsNotNone(genius.fetch('blackbear', 'Idfc'))
            mock_fetch_url.assert_called_once_with("blackbear_url")
            mock_scrape.assert_called_once_with(True)

            # genius uses the hypen minus (\u002D) as their dash
            self.assertIsNotNone(genius.fetch('El-p', 'Idfc'))
            mock_fetch_url.assert_called_with('El-p_url')
            mock_scrape.assert_called_with(True)

            # test no matching artist
            self.assertIsNone(genius.fetch('doesntexist', 'none'))

            # test invalid json
            mock_json.return_value = None
            self.assertIsNone(genius.fetch('blackbear', 'Idfc'))

    # TODO: add integration test hitting real api


# test utilties

class SlugTests(unittest.TestCase):

    def test_slug(self):
        # plain ascii passthrough
        text = u"test"
        self.assertEqual(lyrics.slug(text), 'test')

        # german unicode and capitals
        text = u"Mørdag"
        self.assertEqual(lyrics.slug(text), 'mordag')

        # more accents and quotes
        text = u"l'été c'est fait pour jouer"
        self.assertEqual(lyrics.slug(text), 'l-ete-c-est-fait-pour-jouer')

        # accents, parens and spaces
        text = u"\xe7afe au lait (boisson)"
        self.assertEqual(lyrics.slug(text), 'cafe-au-lait-boisson')
        text = u"Multiple  spaces -- and symbols! -- merged"
        self.assertEqual(lyrics.slug(text),
                         'multiple-spaces-and-symbols-merged')
        text = u"\u200Bno-width-space"
        self.assertEqual(lyrics.slug(text), 'no-width-space')

        # variations of dashes should get standardized
        dashes = [u'\u200D', u'\u2010']
        for dash1, dash2 in itertools.combinations(dashes, 2):
            self.assertEqual(lyrics.slug(dash1), lyrics.slug(dash2))


def suite():
    return unittest.TestLoader().loadTestsFromName(__name__)

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
