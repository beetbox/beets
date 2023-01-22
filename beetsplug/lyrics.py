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

"""Fetches, embeds, and displays lyrics."""

from __future__ import annotations

import atexit
import errno
import itertools
import math
import os.path
import re
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from functools import cached_property, partial, total_ordering
from html import unescape
from http import HTTPStatus
from typing import TYPE_CHECKING, Iterable, Iterator, NamedTuple
from urllib.parse import quote, quote_plus, urlencode, urlparse

import langdetect
import requests
from bs4 import BeautifulSoup
from unidecode import unidecode
import warnings
import urllib
import tidalapi
import datetime
import confuse

import beets
from beets import plugins, ui
from beets.autotag.hooks import string_dist

if TYPE_CHECKING:
    from beets.importer import ImportTask
    from beets.library import Item

    from ._typing import GeniusAPI, GoogleCustomSearchAPI, JSONDict, LRCLibAPI

USER_AGENT = f"beets/{beets.__version__}"
INSTRUMENTAL_LYRICS = "[Instrumental]"

# The content for the base index.rst generated in ReST mode.
REST_INDEX_TEMPLATE = """Lyrics
======

* :ref:`Song index <genindex>`
* :ref:`search`

Artist index:

.. toctree::
   :maxdepth: 1
   :glob:

   artists/*
"""

# The content for the base conf.py generated.
REST_CONF_TEMPLATE = """# -*- coding: utf-8 -*-
master_doc = 'index'
project = 'Lyrics'
copyright = 'none'
author = 'Various Authors'
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
"""


class NotFoundError(requests.exceptions.HTTPError):
    pass


class CaptchaError(requests.exceptions.HTTPError):
    pass


class TimeoutSession(requests.Session):
    def request(self, *args, **kwargs):
        """Wrap the request method to raise an exception on HTTP errors."""
        kwargs.setdefault("timeout", 10)
        r = super().request(*args, **kwargs)
        if r.status_code == HTTPStatus.NOT_FOUND:
            raise NotFoundError("HTTP Error: Not Found", response=r)
        if 300 <= r.status_code < 400:
            raise CaptchaError("Captcha is required", response=r)

        r.raise_for_status()

        return r


r_session = TimeoutSession()
r_session.headers.update({"User-Agent": USER_AGENT})


@atexit.register
def close_session():
    """Close the requests session on shut down."""
    r_session.close()


# Utilities.


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

    title, artist, artist_sort = (
        item.title.strip(),
        item.artist.strip(),
        item.artist_sort.strip(),
    )
    if not title or not artist:
        return ()

    patterns = [
        # Remove any featuring artists from the artists name
        rf"(.*?) {plugins.feat_tokens()}"
    ]

    # Skip various artists
    artists = []
    lower_artist = artist.lower()
    if "various" not in lower_artist:
        artists.extend(generate_alternatives(artist, patterns))
    # Use the artist_sort as fallback only if it differs from artist to avoid
    # repeated remote requests with the same search terms
    artist_sort_lower = artist_sort.lower()
    if (
        artist_sort
        and lower_artist != artist_sort_lower
        and "various" not in artist_sort_lower
    ):
        artists.append(artist_sort)

    patterns = [
        # Remove a parenthesized suffix from a title string. Common
        # examples include (live), (remix), and (acoustic).
        r"(.+?)\s+[(].*[)]$",
        # Remove any featuring artists from the title
        r"(.*?) {}".format(plugins.feat_tokens(for_artist=False)),
        # Remove part of title after colon ':' for songs with subtitles
        r"(.+?)\s*:.*",
    ]
    titles = generate_alternatives(title, patterns)

    # Check for a dual song (e.g. Pink Floyd - Speak to Me / Breathe)
    # and each of them.
    multi_titles = []
    for title in titles:
        multi_titles.append([title])
        if " / " in title:
            multi_titles.append([x.strip() for x in title.split(" / ")])

    return itertools.product(artists, multi_titles)


def slug(text: str) -> str:
    """Make a URL-safe, human-readable version of the given text

    This will do the following:

    1. decode unicode characters into ASCII
    2. shift everything to lowercase
    3. strip whitespace
    4. replace other non-word characters with dashes
    5. strip extra dashes
    """
    return re.sub(r"\W+", "-", unidecode(text).lower().strip()).strip("-")


class RequestHandler:
    _log: beets.logging.Logger

    def debug(self, message: str, *args) -> None:
        """Log a debug message with the class name."""
        self._log.debug(f"{self.__class__.__name__}: {message}", *args)

    def info(self, message: str, *args) -> None:
        """Log an info message with the class name."""
        self._log.info(f"{self.__class__.__name__}: {message}", *args)

    def warn(self, message: str, *args) -> None:
        """Log warning with the class name."""
        self._log.warning(f"{self.__class__.__name__}: {message}", *args)

    @staticmethod
    def format_url(url: str, params: JSONDict | None) -> str:
        if not params:
            return url

        return f"{url}?{urlencode(params)}"

    def fetch_text(
        self, url: str, params: JSONDict | None = None, **kwargs
    ) -> str:
        """Return text / HTML data from the given URL.

        Set the encoding to None to let requests handle it because some sites
        set it incorrectly.
        """
        url = self.format_url(url, params)
        self.debug("Fetching HTML from {}", url)
        r = r_session.get(url, **kwargs)
        r.encoding = None
        return r.text

    def fetch_json(self, url: str, params: JSONDict | None = None, **kwargs):
        """Return JSON data from the given URL."""
        url = self.format_url(url, params)
        self.debug("Fetching JSON from {}", url)
        return r_session.get(url, **kwargs).json()

    @contextmanager
    def handle_request(self) -> Iterator[None]:
        try:
            yield
        except requests.JSONDecodeError:
            self.warn("Could not decode response JSON data")
        except requests.RequestException as exc:
            self.warn("Request error: {}", exc)


class BackendClass(type):
    @property
    def name(cls) -> str:
        """Return lowercase name of the backend class."""
        return cls.__name__.lower()


class Backend(RequestHandler, metaclass=BackendClass):
    def __init__(self, config, log):
        self._log = log
        self.config = config

    def fetch(
        self, artist: str, title: str, album: str, length: int
    ) -> tuple[str, str] | None:
        raise NotImplementedError


@dataclass
@total_ordering
class LRCLyrics:
    #: Percentage tolerance for max duration difference between lyrics and item.
    DURATION_DIFF_TOLERANCE = 0.05

    target_duration: float
    id: int
    duration: float
    instrumental: bool
    plain: str
    synced: str | None

    def __le__(self, other: LRCLyrics) -> bool:
        """Compare two lyrics items by their score."""
        return self.dist < other.dist

    @classmethod
    def make(
        cls, candidate: LRCLibAPI.Item, target_duration: float
    ) -> LRCLyrics:
        return cls(
            target_duration,
            candidate["id"],
            candidate["duration"] or 0.0,
            candidate["instrumental"],
            candidate["plainLyrics"],
            candidate["syncedLyrics"],
        )

    @cached_property
    def duration_dist(self) -> float:
        """Return the absolute difference between lyrics and target duration."""
        return abs(self.duration - self.target_duration)

    @cached_property
    def is_valid(self) -> bool:
        """Return whether the lyrics item is valid.
        Lyrics duration must be within the tolerance defined by
        :attr:`DURATION_DIFF_TOLERANCE`.
        """
        return (
            self.duration_dist
            <= self.target_duration * self.DURATION_DIFF_TOLERANCE
        )

    @cached_property
    def dist(self) -> tuple[bool, float]:
        """Distance/score of the given lyrics item.

        Return a tuple with the following values:
        1. Absolute difference between lyrics and target duration
        2. Boolean telling whether synced lyrics are available.

        Best lyrics match is the one that has the closest duration to
        ``target_duration`` and has synced lyrics available.
        """
        return not self.synced, self.duration_dist

    def get_text(self, want_synced: bool) -> str:
        if self.instrumental:
            return INSTRUMENTAL_LYRICS

        if want_synced and self.synced:
            return "\n".join(map(str.strip, self.synced.splitlines()))

        return self.plain


class LRCLib(Backend):
    """Fetch lyrics from the LRCLib API."""

    BASE_URL = "https://lrclib.net/api"
    GET_URL = f"{BASE_URL}/get"
    SEARCH_URL = f"{BASE_URL}/search"

    def fetch_candidates(
        self, artist: str, title: str, album: str, length: int
    ) -> Iterator[list[LRCLibAPI.Item]]:
        """Yield lyrics candidates for the given song data.

        I found that the ``/get`` endpoint sometimes returns inaccurate or
        unsynced lyrics, while ``search`` yields more suitable candidates.
        Therefore, we prioritize the latter and rank the results using our own
        algorithm. If the search does not give suitable lyrics, we fall back to
        the ``/get`` endpoint.

        Return an iterator over lists of candidates.
        """
        base_params = {"artist_name": artist, "track_name": title}
        get_params = {**base_params, "duration": length}
        if album:
            get_params["album_name"] = album

        yield self.fetch_json(self.SEARCH_URL, params=base_params)

        with suppress(NotFoundError):
            yield [self.fetch_json(self.GET_URL, params=get_params)]

    @classmethod
    def pick_best_match(cls, lyrics: Iterable[LRCLyrics]) -> LRCLyrics | None:
        """Return best matching lyrics item from the given list."""
        return min((li for li in lyrics if li.is_valid), default=None)

    def fetch(
        self, artist: str, title: str, album: str, length: int
    ) -> tuple[str, str] | None:
        """Fetch lyrics text for the given song data."""
        evaluate_item = partial(LRCLyrics.make, target_duration=length)

        for group in self.fetch_candidates(artist, title, album, length):
            candidates = [evaluate_item(item) for item in group]
            if item := self.pick_best_match(candidates):
                lyrics = item.get_text(self.config["synced"])
                return lyrics, f"{self.GET_URL}/{item.id}"

        return None


class MusiXmatch(Backend):
    URL_TEMPLATE = "https://www.musixmatch.com/lyrics/{}/{}"

    REPLACEMENTS = {
        r"\s+": "-",
        "<": "Less_Than",
        ">": "Greater_Than",
        "#": "Number_",
        r"[\[\{]": "(",
        r"[\]\}]": ")",
    }

    @classmethod
    def encode(cls, text: str) -> str:
        for old, new in cls.REPLACEMENTS.items():
            text = re.sub(old, new, text)

        return quote(unidecode(text))

    @classmethod
    def build_url(cls, *args: str) -> str:
        return cls.URL_TEMPLATE.format(*map(cls.encode, args))

    def fetch(self, artist: str, title: str, *_) -> tuple[str, str] | None:
        url = self.build_url(artist, title)

        html = self.fetch_text(url)
        if "We detected that your IP is blocked" in html:
            self.warn("Failed: Blocked IP address")
            return None
        html_parts = html.split('<p class="mxm-lyrics__content')
        # Sometimes lyrics come in 2 or more parts
        lyrics_parts = []
        for html_part in html_parts:
            lyrics_parts.append(re.sub(r"^[^>]+>|</p>.*", "", html_part))
        lyrics = "\n".join(lyrics_parts)
        lyrics = lyrics.strip(',"').replace("\\n", "\n")
        # another odd case: sometimes only that string remains, for
        # missing songs. this seems to happen after being blocked
        # above, when filling in the CAPTCHA.
        if "Instant lyrics for all your music." in lyrics:
            return None
        # sometimes there are non-existent lyrics with some content
        if "Lyrics | Musixmatch" in lyrics:
            return None
        return lyrics


class Genius(Backend):
    """Fetch lyrics from Genius via genius-api.

    Simply adapted from
    bigishdata.com/2016/09/27/getting-song-lyrics-from-geniuss-api-scraping/
    """

    REQUIRES_BS = True

    base_url = "https://api.genius.com"

    def __init__(self, config, log):
        super().__init__(config, log)
        self.api_key = config['genius_api_key'].as_str()
        self.headers = {
            'Authorization': "Bearer %s" % self.api_key,
            'User-Agent': USER_AGENT,
        }

    def fetch(self, artist, title):
        """Fetch lyrics from genius.com

        Because genius doesn't allow accesssing lyrics via the api,
        we first query the api for a url matching our artist & title,
        then attempt to scrape that url for the lyrics.
        """
        json = self._search(artist, title)
        if not json:
            self._log.debug('Genius API request returned invalid JSON')
            return None

        # find a matching artist in the json
        for hit in json["response"]["hits"]:
            hit_artist = hit["result"]["primary_artist"]["name"]

            if slug(hit_artist) == slug(artist):
                html = self.fetch_url(hit["result"]["url"])
                if not html:
                    return None
                return self._scrape_lyrics_from_html(html)

        self._log.debug('Genius failed to find a matching artist for \'{0}\'',
                        artist)
        return None

    def _search(self, artist, title):
        """Searches the genius api for a given artist and title

        https://docs.genius.com/#search-h2

        :returns: json response
        """
        search_url = self.base_url + "/search"
        data = {'q': title + " " + artist.lower()}
        try:
            response = requests.get(
                search_url, params=data, headers=self.headers)
        except requests.RequestException as exc:
            self._log.debug('Genius API request failed: {0}', exc)
            return None

        try:
            return response.json()
        except ValueError:
            return None

    def replace_br(self, lyrics_div):
        for br in lyrics_div.find_all("br"):
            br.replace_with("\n")

    def _scrape_lyrics_from_html(self, html):
        """Scrape lyrics from a given genius.com html"""

        soup = try_parse_html(html)
        if not soup:
            return

        # Remove script tags that they put in the middle of the lyrics.
        [h.extract() for h in soup('script')]

        # Most of the time, the page contains a div with class="lyrics" where
        # all of the lyrics can be found already correctly formatted
        # Sometimes, though, it packages the lyrics into separate divs, most
        # likely for easier ad placement

        lyrics_div = soup.find("div", {"data-lyrics-container": True})

        if lyrics_div:
            self.replace_br(lyrics_div)

        if not lyrics_div:
            self._log.debug('Received unusual song page html')
            verse_div = soup.find("div",
                                  class_=re.compile("Lyrics__Container"))
            if not verse_div:
                if soup.find("div",
                             class_=re.compile("LyricsPlaceholder__Message"),
                             string="This song is an instrumental"):
                    self._log.debug('Detected instrumental')
                    return "[Instrumental]"
                else:
                    self._log.debug("Couldn't scrape page using known layouts")
                    return None

            lyrics_div = verse_div.parent
            self.replace_br(lyrics_div)

            ads = lyrics_div.find_all("div",
                                      class_=re.compile("InreadAd__Container"))
            for ad in ads:
                ad.replace_with("\n")

            footers = lyrics_div.find_all("div",
                                          class_=re.compile("Lyrics__Footer"))
            for footer in footers:
                footer.replace_with("")
        return lyrics_div.get_text()

class Tidal(Backend):
    REQUIRES_BS = False
    
    def __init__(self, config, log):
        super().__init__(config, log)
        self._log = log
        
        sessionfile = self.config["tidal_session_file"].get(
            confuse.Filename(in_app_dir=True)
        )

        self.session = self.load_session(sessionfile)
        
        if not self.session:
            self._log.debug("JSON file corrupted or does not exist, performing simple OAuth login.")
            self.session = tidalapi.Session()
            self.session.login_oauth_simple()
            self.save_session(sessionfile)
        
    def fetch(self, artist, title):
        self._log.debug(f"Fetching lyrics for {title} from {artist}!")
        
        results = self.session.search(f"{artist} {title}", models = [tidalapi.media.Track], limit = 5)
        if results["top_hit"]:
                top_hit = results["top_hit"]
        elif len(results["tracks"]) > 0:
                self._log.debug("Top Hit result does not exist, using first result")
                top_hit = results["tracks"][0]
        else:
                return None

        self._log.debug(f"Top Hit result for query `{artist} {title}`: {top_hit.name} from {top_hit.artist.name} with ID {top_hit.id}")
        
        # This could be considered paranoid, but there is a chance that the Tidal top hit isn't what we're looking for.
        if top_hit.artist.name.lower() != artist.lower():
            self._log.warning(f"Tidal lyrics query returned artist {top_hit.artist.name}, but the file is under artist {artist}")
        
        elif top_hit.name.lower() != title.lower():
            self._log.warning(f"Tidal lyrics query returned track {top_hit.name}, but the file is {title}")
            
        try:
                lyrics = top_hit.lyrics()
        except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                        return None

                raise e

        if lyrics.subtitles:
            return lyrics.subtitles
        else:
            self._log.warning(f"Timed lyrics not available... returning regular lyrics.")
            return lyrics.text
        
        
    def load_session(self, sfile):
        self._log.debug(f"Loading tidal session from {sfile}")
        s = tidalapi.Session()
        
        try:
            with open(sfile, "r") as file:
                data = json.load(file)
                if s.load_oauth_session(data["token_type"], data["access_token"], data["refresh_token"], datetime.datetime.fromtimestamp(data["expiry_time"])):
                    return s
                else:
                    return None
        except FileNotFoundError:
            return None
            
    def save_session(self, sfile):
        self._log.debug(f"Saving tidal session to {sfile}")
        with open(sfile, "w") as file:
            json.dump({
            "token_type": self.session.token_type,
            "access_token": self.session.access_token,
            "refresh_token": self.session.refresh_token,
            "expiry_time": self.session.expiry_time.timestamp()}, file, indent = 2)
        
class Tekstowo(Backend):
    # Fetch lyrics from Tekstowo.pl.
    REQUIRES_BS = True

    BASE_URL = 'http://www.tekstowo.pl'
    URL_PATTERN = BASE_URL + '/wyszukaj.html?search-title=%s&search-artist=%s'

    def fetch(self, artist, title):
        url = self.build_url(title, artist)
        search_results = self.fetch_url(url)
        if not search_results:
            return None

        song_page_url = self.parse_search_results(search_results)
        if not song_page_url:
            return None

        song_page_html = self.fetch_url(song_page_url)
        if not song_page_html:
            return None

        return self.extract_lyrics(song_page_html, artist, title)

    def parse_search_results(self, html):
        html = _scrape_strip_cruft(html)
        html = _scrape_merge_paragraphs(html)

        soup = try_parse_html(html)
        if not soup:
            return None

        content_div = soup.find("div", class_="content")
        if not content_div:
            return None

        card_div = content_div.find("div", class_="card")
        if not card_div:
            return None

        song_rows = card_div.find_all("div", class_="box-przeboje")
        if not song_rows:
            return None

        song_row = song_rows[0]
        if not song_row:
            return None

        link = song_row.find('a')
        if not link:
            return None

        return self.BASE_URL + link.get('href')

    def extract_lyrics(self, html, artist, title):
        html = _scrape_strip_cruft(html)
        html = _scrape_merge_paragraphs(html)

        soup = try_parse_html(html)
        if not soup:
            return None

        info_div = soup.find("div", class_="col-auto")
        if not info_div:
            return None

        info_elements = info_div.find_all("a")
        if not info_elements:
            return None

        html_title = info_elements[-1].get_text()
        html_artist = info_elements[-2].get_text()

        title_dist = string_dist(html_title, title)
        artist_dist = string_dist(html_artist, artist)

        thresh = self.config['dist_thresh'].get(float)
        if title_dist > thresh or artist_dist > thresh:
            return None

        lyrics_div = soup.select("div.song-text > div.inner-text")
        if not lyrics_div:
            return None

        return lyrics_div[0].get_text()


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
    html = re.sub('\u2005', " ", html)  # replace unicode with regular space

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
    def is_text_notcode(text):
        length = len(text)
        return (length > 20 and
                text.count(' ') > length / 25 and
                (text.find('{') == -1 or text.find(';') == -1))
    html = _scrape_strip_cruft(html)
    html = _scrape_merge_paragraphs(html)

    # extract all long text blocks that are not code
    soup = try_parse_html(html,
                          parse_only=SoupStrainer(string=is_text_notcode))
    if not soup:
        return None

    # Get the longest text element (if any).
    strings = sorted(soup.stripped_strings, key=len, reverse=True)
    if strings:
        return strings[0]
    else:
        return None


class Google(Backend):
    """Fetch lyrics from Google search results."""

    REQUIRES_BS = True

    def __init__(self, config, log):
        super().__init__(config, log)
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
            self._log.debug("Ignoring too short lyrics '{0}'", text)
            return False
        elif nb_lines < 5:
            bad_triggers_occ.append('too_short')
        else:
            # Lyrics look legit, remove credits to avoid being penalized
            # further down
            text = remove_credits(text)

        bad_triggers = ['lyrics', 'copyright', 'property', 'links']
        if artist:
            bad_triggers += [artist]

        for item in bad_triggers:
            bad_triggers_occ += [item] * len(re.findall(r'\W%s\W' % item,
                                                        text, re.I))

        if bad_triggers_occ:
            self._log.debug('Bad triggers detected: {0}', bad_triggers_occ)
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
            text = str(re.sub(r'[-\s]+', ' ', text.decode('utf-8')))
        except UnicodeDecodeError:
            self._log.exception("Failing to normalize '{0}'", text)
        return text

    BY_TRANS = ['by', 'par', 'de', 'von']
    LYRICS_TRANS = ['lyrics', 'paroles', 'letras', 'liedtexte']

    def is_page_candidate(self, url_link, url_title, title, artist):
        """Return True if the URL title makes it a good candidate to be a
        page that contains lyrics of title by artist.
        """
        title = self.slugify(title.lower())
        artist = self.slugify(artist.lower())
        sitename = re.search("//([^/]+)/.*",
                             self.slugify(url_link.lower())).group(1)
        url_title = self.slugify(url_title.lower())

        # Check if URL title contains song title (exact match)
        if url_title.find(title) != -1:
            return True

        if math.isclose(max_dist, self.dist_thresh, abs_tol=0.4):
            # log out the candidate that did not make it but was close.
            # This may show a matching candidate with some noise in the name
            self.debug(
                "({}, {}) does not match ({}, {}) but dist was close: {:.2f}",
                result.artist,
                result.title,
                target_artist,
                target_title,
                max_dist,
            )

        return False

    def search(self, artist: str, title: str) -> Iterable[SearchResult]:
        """Search for the given query and yield search results."""
        raise NotImplementedError

    def get_results(self, artist: str, title: str) -> Iterable[SearchResult]:
        check_match = partial(self.check_match, artist, title)
        for candidate in self.search(artist, title):
            if check_match(candidate):
                yield candidate

    def fetch(self, artist: str, title: str, *_) -> tuple[str, str] | None:
        """Fetch lyrics for the given artist and title."""
        for result in self.get_results(artist, title):
            if (html := self.fetch_text(result.url)) and (
                lyrics := self.scrape(html)
            ):
                return lyrics, result.url

        return None

    @classmethod
    def scrape(cls, html: str) -> str | None:
        """Scrape the lyrics from the given HTML."""
        raise NotImplementedError


class Genius(SearchBackend):
    """Fetch lyrics from Genius via genius-api.

    Because genius doesn't allow accessing lyrics via the api, we first query
    the api for a url matching our artist & title, then scrape the HTML text
    for the JSON data containing the lyrics.
    """

    SEARCH_URL = "https://api.genius.com/search"
    LYRICS_IN_JSON_RE = re.compile(r'(?<=.\\"html\\":\\").*?(?=(?<!\\)\\")')
    remove_backslash = partial(re.compile(r"\\(?=[^\\])").sub, "")

    @cached_property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f'Bearer {self.config["genius_api_key"]}'}

    def search(self, artist: str, title: str) -> Iterable[SearchResult]:
        search_data: GeniusAPI.Search = self.fetch_json(
            self.SEARCH_URL,
            params={"q": f"{artist} {title}"},
            headers=self.headers,
        )
        for r in (hit["result"] for hit in search_data["response"]["hits"]):
            yield SearchResult(r["artist_names"], r["title"], r["url"])

    @classmethod
    def scrape(cls, html: str) -> str | None:
        if m := cls.LYRICS_IN_JSON_RE.search(html):
            html_text = cls.remove_backslash(m[0]).replace(r"\n", "\n")
            return cls.get_soup(html_text).get_text().strip()

        return None


class LyricsPlugin(plugins.BeetsPlugin):
    SOURCES = ['google', 'musixmatch', 'genius', 'tekstowo', 'tidal']
    SOURCE_BACKENDS = {
        'google': Google,
        'musixmatch': MusiXmatch,
        'genius': Genius,
        'tekstowo': Tekstowo,
        'tidal': Tidal
    }

    @cached_property
    def backends(self) -> list[Backend]:
        user_sources = self.config["sources"].get()

        chosen = plugins.sanitize_choices(user_sources, self.BACKEND_BY_NAME)
        if "google" in chosen and not self.config["google_API_key"].get():
            self.warn("Disabling Google source: no API key configured.")
            chosen.remove("google")

        return [self.BACKEND_BY_NAME[c](self.config, self._log) for c in chosen]

    def __init__(self):
        super().__init__()
        self.import_stages = [self.imported]
        self.config.add({
            'auto': True,
            'bing_client_secret': None,
            'bing_lang_from': [],
            'bing_lang_to': None,
            'google_API_key': None,
            'google_engine_ID': '009217259823014548361:lndtuqkycfu',
            'genius_api_key':
                "Ryq93pUGm8bM6eUWwD_M3NOFFDAtp2yEE7W"
                "76V-uFL5jks5dNvcGCdarqFjDhP9c",
            'fallback': None,
            'force': False,
            'local': False,
            # Musixmatch is disabled by default as they are currently blocking
            # requests with the beets user agent.
            #
            # Tidal is disabled by default as it currently requires a paid account.
            'sources': [s for s in self.SOURCES if s != "musixmatch" and s != "tidal"],
            'dist_thresh': 0.1,
            'tidal_session_file': 'tidal.json'
        })
        self.config['bing_client_secret'].redact = True
        self.config['google_API_key'].redact = True
        self.config['google_engine_ID'].redact = True
        self.config['genius_api_key'].redact = True

        # State information for the ReST writer.
        # First, the current artist we're writing.
        self.artist = "Unknown artist"
        # The current album: False means no album yet.
        self.album = False
        # The current rest file content. None means the file is not
        # open yet.
        self.rest = None

        self.config["bing_lang_from"] = [
            x.lower() for x in self.config["bing_lang_from"].as_str_seq()
        ]

    @cached_property
    def bing_access_token(self) -> str | None:
        params = {
            "client_id": "beets",
            "client_secret": self.config["bing_client_secret"],
            "scope": "https://api.microsofttranslator.com",
            "grant_type": "client_credentials",
        }

        oauth_url = "https://datamarket.accesscontrol.windows.net/v2/OAuth2-13"
        with self.handle_request():
            r = r_session.post(oauth_url, params=params)
            return r.json()["access_token"]

    def commands(self):
        cmd = ui.Subcommand("lyrics", help="fetch song lyrics")
        cmd.parser.add_option(
            "-p",
            "--print",
            dest="printlyr",
            action="store_true",
            default=False,
            help="print lyrics to console",
        )
        cmd.parser.add_option(
            "-r",
            "--write-rest",
            dest="writerest",
            action="store",
            default=None,
            metavar="dir",
            help="write lyrics to given directory as ReST files",
        )
        cmd.parser.add_option(
            "-f",
            "--force",
            dest="force_refetch",
            action="store_true",
            default=False,
            help="always re-download lyrics",
        )
        cmd.parser.add_option(
            "-l",
            "--local",
            dest="local_only",
            action="store_true",
            default=False,
            help="do not fetch missing lyrics",
        )

        def func(lib, opts, args):
            # The "write to files" option corresponds to the
            # import_write config value.
            write = ui.should_write()
            if opts.writerest:
                self.writerest_indexes(opts.writerest)
            items = lib.items(ui.decargs(args))
            for item in items:
                if not opts.local_only and not self.config["local"]:
                    self.fetch_item_lyrics(
                        item, write, opts.force_refetch or self.config["force"]
                    )
                if item.lyrics:
                    if opts.printlyr:
                        ui.print_(item.lyrics)
                    if opts.writerest:
                        self.appendrest(opts.writerest, item)
            if opts.writerest and items:
                # flush last artist & write to ReST
                self.writerest(opts.writerest)
                ui.print_("ReST files generated. to build, use one of:")
                ui.print_(
                    "  sphinx-build -b html %s _build/html" % opts.writerest
                )
                ui.print_(
                    "  sphinx-build -b epub %s _build/epub" % opts.writerest
                )
                ui.print_(
                    (
                        "  sphinx-build -b latex %s _build/latex "
                        "&& make -C _build/latex all-pdf"
                    )
                    % opts.writerest
                )

        cmd.func = func
        return [cmd]

    def appendrest(self, directory, item):
        """Append the item to an ReST file

        This will keep state (in the `rest` variable) in order to avoid
        writing continuously to the same files.
        """

        if slug(self.artist) != slug(item.albumartist):
            # Write current file and start a new one ~ item.albumartist
            self.writerest(directory)
            self.artist = item.albumartist.strip()
            self.rest = "%s\n%s\n\n.. contents::\n   :local:\n\n" % (
                self.artist,
                "=" * len(self.artist),
            )

        if self.album != item.album:
            tmpalbum = self.album = item.album.strip()
            if self.album == "":
                tmpalbum = "Unknown album"
            self.rest += "{}\n{}\n\n".format(tmpalbum, "-" * len(tmpalbum))
        title_str = ":index:`%s`" % item.title.strip()
        block = "| " + item.lyrics.replace("\n", "\n| ")
        self.rest += "{}\n{}\n\n{}\n\n".format(
            title_str, "~" * len(title_str), block
        )

    def writerest(self, directory):
        """Write self.rest to a ReST file"""
        if self.rest is not None and self.artist is not None:
            path = os.path.join(
                directory, "artists", slug(self.artist) + ".rst"
            )
            with open(path, "wb") as output:
                output.write(self.rest.encode("utf-8"))

    def writerest_indexes(self, directory):
        """Write conf.py and index.rst files necessary for Sphinx

        We write minimal configurations that are necessary for Sphinx
        to operate. We do not overwrite existing files so that
        customizations are respected."""
        try:
            os.makedirs(os.path.join(directory, "artists"))
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
            else:
                raise
        indexfile = os.path.join(directory, "index.rst")
        if not os.path.exists(indexfile):
            with open(indexfile, "w") as output:
                output.write(REST_INDEX_TEMPLATE)
        conffile = os.path.join(directory, "conf.py")
        if not os.path.exists(conffile):
            with open(conffile, "w") as output:
                output.write(REST_CONF_TEMPLATE)

    def imported(self, _, task: ImportTask) -> None:
        """Import hook for fetching lyrics automatically."""
        if self.config["auto"]:
            for item in task.imported_items():
                self.fetch_item_lyrics(item, False, self.config["force"])

    def fetch_item_lyrics(self, item: Item, write: bool, force: bool) -> None:
        """Fetch and store lyrics for a single item. If ``write``, then the
        lyrics will also be written to the file itself.
        """
        # Skip if the item already has lyrics.
        if not force and item.lyrics:
            self.info("🔵 Lyrics already present: {}", item)
            return

        lyrics_matches = []
        album, length = item.album, round(item.length)
        for artist, titles in search_pairs(item):
            lyrics_matches = [
                self.get_lyrics(artist, title, album, length)
                for title in titles
            ]
            if any(lyrics_matches):
                break

        lyrics = "\n\n---\n\n".join(filter(None, lyrics_matches))

        if lyrics:
            self.info("🟢 Found lyrics: {0}", item)
            if self.config["bing_client_secret"].get():
                lang_from = langdetect.detect(lyrics)
                if self.config["bing_lang_to"].get() != lang_from and (
                    not self.config["bing_lang_from"]
                    or (lang_from in self.config["bing_lang_from"].as_str_seq())
                ):
                    lyrics = self.append_translation(
                        lyrics, self.config["bing_lang_to"]
                    )
        else:
            self.info("🔴 Lyrics not found: {}", item)
            lyrics = self.config["fallback"].get()

        if lyrics not in {None, item.lyrics}:
            item.lyrics = lyrics
            if write:
                item.try_write()
            item.store()

    def get_lyrics(self, artist: str, title: str, *args) -> str | None:
        """Fetch lyrics, trying each source in turn. Return a string or
        None if no lyrics were found.
        """
        self.info("Fetching lyrics for {} - {}", artist, title)
        for backend in self.backends:
            with backend.handle_request():
                if lyrics_info := backend.fetch(artist, title, *args):
                    lyrics, url = lyrics_info
                    return f"{lyrics}\n\nSource: {url}"

        return None

    def append_translation(self, text, to_lang):
        from xml.etree import ElementTree

        if not (token := self.bing_access_token):
            self.warn(
                "Could not get Bing Translate API access token. "
                "Check your 'bing_client_secret' password."
            )
            return text

        # Extract unique lines to limit API request size per song
        lines = text.split("\n")
        unique_lines = set(lines)
        url = "https://api.microsofttranslator.com/v2/Http.svc/Translate"
        with self.handle_request():
            text = self.fetch_text(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={"text": "|".join(unique_lines), "to": to_lang},
            )
            if translated := ElementTree.fromstring(text.encode("utf-8")).text:
                # Use a translation mapping dict to build resulting lyrics
                translations = dict(zip(unique_lines, translated.split("|")))
                return "".join(f"{ln} / {translations[ln]}\n" for ln in lines)

        return text
