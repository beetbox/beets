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

import difflib
import errno
import itertools
import json
import os.path
import re
import struct
import unicodedata
import warnings
from functools import partial
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import quote, urlencode

import requests
from typing_extensions import TypedDict
from unidecode import unidecode

import beets
from beets import plugins, ui

if TYPE_CHECKING:
    from beets.importer import ImportTask
    from beets.library import Item

try:
    import bs4
    from bs4 import SoupStrainer

    HAS_BEAUTIFUL_SOUP = True
except ImportError:
    HAS_BEAUTIFUL_SOUP = False

try:
    import langdetect

    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False

DIV_RE = re.compile(r"<(/?)div>?", re.I)
COMMENT_RE = re.compile(r"<!--.*-->", re.S)
TAG_RE = re.compile(r"<[^>]*>")
BREAK_RE = re.compile(r"\n?\s*<br([\s|/][^>]*)*>\s*\n?", re.I)
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


# Utilities.


def unichar(i):
    try:
        return chr(i)
    except ValueError:
        return struct.pack("i", i).decode("utf-32")


def unescape(text):
    """Resolve &#xxx; HTML entities (and some others)."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "ignore")
    out = text.replace("&nbsp;", " ")

    def replchar(m):
        num = m.group(1)
        return unichar(int(num))

    out = re.sub("&#(\\d+);", replchar, out)
    return out


def extract_text_between(html, start_marker, end_marker):
    try:
        _, html = html.split(start_marker, 1)
        html, _ = html.split(end_marker, 1)
    except ValueError:
        return ""
    return html


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
    artists = generate_alternatives(artist, patterns)
    # Use the artist_sort as fallback only if it differs from artist to avoid
    # repeated remote requests with the same search terms
    if artist_sort and artist.lower() != artist_sort.lower():
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
        if "/" in title:
            multi_titles.append([x.strip() for x in title.split("/")])

    return itertools.product(artists, multi_titles)


def slug(text):
    """Make a URL-safe, human-readable version of the given text

    This will do the following:

    1. decode unicode characters into ASCII
    2. shift everything to lowercase
    3. strip whitespace
    4. replace other non-word characters with dashes
    5. strip extra dashes

    This somewhat duplicates the :func:`Google.slugify` function but
    slugify is not as generic as this one, which can be reused
    elsewhere.
    """
    return re.sub(r"\W+", "-", unidecode(text).lower().strip()).strip("-")


if HAS_BEAUTIFUL_SOUP:

    def try_parse_html(html, **kwargs):
        return bs4.BeautifulSoup(html, "html.parser", **kwargs)

else:

    def try_parse_html(html, **kwargs):
        return None


class Backend:
    REQUIRES_BS = False

    def __init__(self, config, log):
        self._log = log
        self.config = config

    def fetch_url(self, url, **kwargs):
        """Retrieve the content at a given URL, or return None if the source
        is unreachable.
        """
        try:
            # Disable the InsecureRequestWarning that comes from using
            # `verify=false`.
            # https://github.com/kennethreitz/requests/issues/2214
            # We're not overly worried about the NSA MITMing our lyrics scraper
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = requests.get(
                    url,
                    verify=False,
                    headers={
                        "User-Agent": USER_AGENT,
                    },
                    timeout=10,
                    **kwargs,
                )
        except requests.RequestException as exc:
            self._log.debug("lyrics request failed: {0}", exc)
            return
        if r.status_code == requests.codes.ok:
            return r.text
        else:
            self._log.debug("failed to fetch: {0} ({1})", url, r.status_code)
            return None

    def fetch(
        self, artist: str, title: str, album: str, length: int
    ) -> str | None:
        raise NotImplementedError


class LRCLibItem(TypedDict):
    """Lyrics data item returned by the LRCLib API."""

    id: int
    name: str
    trackName: str
    artistName: str
    albumName: str
    duration: float
    instrumental: bool
    plainLyrics: str
    syncedLyrics: str | None


class LRCLib(Backend):
    base_url = "https://lrclib.net/api/search"

    def warn(self, message: str, *args) -> None:
        """Log a warning message with the class name."""
        self._log.warning(f"{self.__class__.__name__}: {message}", *args)

    def fetch_json(self, *args, **kwargs):
        """Wrap the request method to raise an exception on HTTP errors."""
        kwargs.setdefault("timeout", 10)
        kwargs.setdefault("headers", {"User-Agent": USER_AGENT})
        r = requests.get(*args, **kwargs)
        r.raise_for_status()

        return r.json()

    @staticmethod
    def get_rank(
        target_duration: float, item: LRCLibItem
    ) -> tuple[float, bool]:
        """Rank the given lyrics item.

        Return a tuple with the following values:
        1. Absolute difference between lyrics and target duration
        2. Boolean telling whether synced lyrics are available.
        """
        return (
            abs(item["duration"] - target_duration),
            not item["syncedLyrics"],
        )

    @classmethod
    def pick_lyrics(
        cls, target_duration: float, data: list[LRCLibItem]
    ) -> LRCLibItem:
        """Return best matching lyrics item from the given list.

        Best lyrics match is the one that has the closest duration to
        ``target_duration`` and has synced lyrics available.

        Note that the incoming list is guaranteed to be non-empty.
        """
        return min(data, key=lambda item: cls.get_rank(target_duration, item))

    def fetch(
        self, artist: str, title: str, album: str, length: int
    ) -> str | None:
        """Fetch lyrics for the given artist, title, and album."""
        params: dict[str, str | int] = {
            "artist_name": artist,
            "track_name": title,
        }
        if album:
            params["album_name"] = album

        if length:
            params["duration"] = length

        try:
            data = self.fetch_json(self.base_url, params=params)
        except requests.JSONDecodeError:
            self.warn("Could not decode response JSON data")
        except requests.RequestException as exc:
            self.warn("Request error: {}", exc)
        else:
            if data:
                item = self.pick_lyrics(length, data)

                if item["instrumental"]:
                    return INSTRUMENTAL_LYRICS

                if self.config["synced"] and (synced := item["syncedLyrics"]):
                    return synced

                return item["plainLyrics"]

        return None


class DirectBackend(Backend):
    """A backend for fetching lyrics directly."""

    URL_TEMPLATE: ClassVar[str]  #: May include formatting placeholders

    @classmethod
    def encode(cls, text: str) -> str:
        """Encode the string for inclusion in a URL."""
        raise NotImplementedError

    @classmethod
    def build_url(cls, *args: str) -> str:
        return cls.URL_TEMPLATE.format(*map(cls.encode, args))


class MusiXmatch(DirectBackend):
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

    def fetch(self, artist: str, title: str, *_) -> str | None:
        url = self.build_url(artist, title)

        html = self.fetch_url(url)
        if not html:
            return None
        if "We detected that your IP is blocked" in html:
            self._log.warning(
                "we are blocked at MusixMatch: url %s failed" % url
            )
            return None
        html_parts = html.split('<p class="mxm-lyrics__content')
        # Sometimes lyrics come in 2 or more parts
        lyrics_parts = []
        for html_part in html_parts:
            lyrics_parts.append(extract_text_between(html_part, ">", "</p>"))
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
        self.api_key = config["genius_api_key"].as_str()
        self.headers = {
            "Authorization": "Bearer %s" % self.api_key,
            "User-Agent": USER_AGENT,
        }

    def fetch(self, artist: str, title: str, *_) -> str | None:
        """Fetch lyrics from genius.com

        Because genius doesn't allow accessing lyrics via the api,
        we first query the api for a url matching our artist & title,
        then attempt to scrape that url for the lyrics.
        """
        json = self._search(artist, title)
        if not json:
            self._log.debug("Genius API request returned invalid JSON")
            return None

        # find a matching artist in the json
        for hit in json["response"]["hits"]:
            hit_artist = hit["result"]["primary_artist"]["name"]

            if slug(hit_artist) == slug(artist):
                html = self.fetch_url(hit["result"]["url"])
                if not html:
                    return None
                return self._scrape_lyrics_from_html(html)

        self._log.debug(
            "Genius failed to find a matching artist for '{0}'", artist
        )
        return None

    def _search(self, artist, title):
        """Searches the genius api for a given artist and title

        https://docs.genius.com/#search-h2

        :returns: json response
        """
        search_url = self.base_url + "/search"
        data = {"q": title + " " + artist.lower()}
        try:
            response = requests.get(
                search_url,
                params=data,
                headers=self.headers,
                timeout=10,
            )
        except requests.RequestException as exc:
            self._log.debug("Genius API request failed: {0}", exc)
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
        [h.extract() for h in soup("script")]

        # Most of the time, the page contains a div with class="lyrics" where
        # all of the lyrics can be found already correctly formatted
        # Sometimes, though, it packages the lyrics into separate divs, most
        # likely for easier ad placement

        lyrics_divs = soup.find_all("div", {"data-lyrics-container": True})
        if not lyrics_divs:
            self._log.debug("Received unusual song page html")
            return self._try_extracting_lyrics_from_non_data_lyrics_container(
                soup
            )
        lyrics = ""
        for lyrics_div in lyrics_divs:
            self.replace_br(lyrics_div)
            lyrics += lyrics_div.get_text() + "\n\n"
        while lyrics[-1] == "\n":
            lyrics = lyrics[:-1]
        return lyrics

    def _try_extracting_lyrics_from_non_data_lyrics_container(self, soup):
        """Extract lyrics from a div without attribute data-lyrics-container
        This is the second most common layout on genius.com
        """
        verse_div = soup.find("div", class_=re.compile("Lyrics__Container"))
        if not verse_div:
            if soup.find(
                "div",
                class_=re.compile("LyricsPlaceholder__Message"),
                string="This song is an instrumental",
            ):
                self._log.debug("Detected instrumental")
                return INSTRUMENTAL_LYRICS
            else:
                self._log.debug("Couldn't scrape page using known layouts")
                return None

        lyrics_div = verse_div.parent
        self.replace_br(lyrics_div)

        ads = lyrics_div.find_all(
            "div", class_=re.compile("InreadAd__Container")
        )
        for ad in ads:
            ad.replace_with("\n")

        footers = lyrics_div.find_all(
            "div", class_=re.compile("Lyrics__Footer")
        )
        for footer in footers:
            footer.replace_with("")
        return lyrics_div.get_text()


class Tekstowo(DirectBackend):
    """Fetch lyrics from Tekstowo.pl."""

    REQUIRES_BS = True
    URL_TEMPLATE = "https://www.tekstowo.pl/piosenka,{},{}.html"

    non_alpha_to_underscore = partial(re.compile(r"\W").sub, "_")

    @classmethod
    def encode(cls, text: str) -> str:
        return cls.non_alpha_to_underscore(unidecode(text.lower()))

    def fetch(self, artist: str, title: str, *_) -> str | None:
        if html := self.fetch_url(self.build_url(artist, title)):
            return self.extract_lyrics(html)

        return None

    def extract_lyrics(self, html: str) -> str | None:
        html = _scrape_strip_cruft(html)
        html = _scrape_merge_paragraphs(html)

        soup = try_parse_html(html)

        if lyrics_div := soup.select_one("div.song-text > div.inner-text"):
            return lyrics_div.get_text()

        return None


def remove_credits(text):
    """Remove first/last line of text if it contains the word 'lyrics'
    eg 'Lyrics by songsdatabase.com'
    """
    textlines = text.split("\n")
    credits = None
    for i in (0, -1):
        if textlines and "lyrics" in textlines[i].lower():
            credits = textlines.pop(i)
    if credits:
        text = "\n".join(textlines)
    return text


def _scrape_strip_cruft(html, plain_text_out=False):
    """Clean up HTML"""
    html = unescape(html)

    html = html.replace("\r", "\n")  # Normalize EOL.
    html = re.sub(r" +", " ", html)  # Whitespaces collapse.
    html = BREAK_RE.sub("\n", html)  # <br> eats up surrounding '\n'.
    html = re.sub(r"(?s)<(script).*?</\1>", "", html)  # Strip script tags.
    html = re.sub("\u2005", " ", html)  # replace unicode with regular space
    html = re.sub("<aside .+?</aside>", "", html)  # remove Google Ads tags
    html = re.sub(r"</?(em|strong)[^>]*>", "", html)  # remove italics / bold

    if plain_text_out:  # Strip remaining HTML tags
        html = COMMENT_RE.sub("", html)
        html = TAG_RE.sub("", html)

    html = "\n".join([x.strip() for x in html.strip().split("\n")])
    html = re.sub(r"\n{3,}", r"\n\n", html)
    return html


def _scrape_merge_paragraphs(html):
    html = re.sub(r"</p>\s*<p(\s*[^>]*)>", "\n", html)
    return re.sub(r"<div .*>\s*</div>", "\n", html)


def scrape_lyrics_from_html(html):
    """Scrape lyrics from a URL. If no lyrics can be found, return None
    instead.
    """

    def is_text_notcode(text):
        if not text:
            return False
        length = len(text)
        return (
            length > 20
            and text.count(" ") > length / 25
            and (text.find("{") == -1 or text.find(";") == -1)
        )

    html = _scrape_strip_cruft(html)
    html = _scrape_merge_paragraphs(html)

    # extract all long text blocks that are not code
    soup = try_parse_html(html, parse_only=SoupStrainer(string=is_text_notcode))
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
    SEARCH_URL = "https://www.googleapis.com/customsearch/v1"

    def is_lyrics(self, text, artist=None):
        """Determine whether the text seems to be valid lyrics."""
        if not text:
            return False
        bad_triggers_occ = []
        nb_lines = text.count("\n")
        if nb_lines <= 1:
            self._log.debug("Ignoring too short lyrics '{0}'", text)
            return False
        elif nb_lines < 5:
            bad_triggers_occ.append("too_short")
        else:
            # Lyrics look legit, remove credits to avoid being penalized
            # further down
            text = remove_credits(text)

        bad_triggers = ["lyrics", "copyright", "property", "links"]
        if artist:
            bad_triggers += [artist]

        for item in bad_triggers:
            bad_triggers_occ += [item] * len(
                re.findall(r"\W%s\W" % item, text, re.I)
            )

        if bad_triggers_occ:
            self._log.debug("Bad triggers detected: {0}", bad_triggers_occ)
        return len(bad_triggers_occ) < 2

    def slugify(self, text):
        """Normalize a string and remove non-alphanumeric characters."""
        text = re.sub(r"[-'_\s]", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        pat = r"([^,\(]*)\((.*?)\)"  # Remove content within parentheses
        text = re.sub(pat, r"\g<1>", text).strip()
        try:
            text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore")
            text = str(re.sub(r"[-\s]+", " ", text.decode("utf-8")))
        except UnicodeDecodeError:
            self._log.exception("Failing to normalize '{0}'", text)
        return text

    BY_TRANS = ["by", "par", "de", "von"]
    LYRICS_TRANS = ["lyrics", "paroles", "letras", "liedtexte"]

    def is_page_candidate(self, url_link, url_title, title, artist):
        """Return True if the URL title makes it a good candidate to be a
        page that contains lyrics of title by artist.
        """
        title = self.slugify(title.lower())
        artist = self.slugify(artist.lower())
        sitename = re.search(
            "//([^/]+)/.*", self.slugify(url_link.lower())
        ).group(1)
        url_title = self.slugify(url_title.lower())

        # Check if URL title contains song title (exact match)
        if url_title.find(title) != -1:
            return True

        # or try extracting song title from URL title and check if
        # they are close enough
        tokens = (
            [by + "_" + artist for by in self.BY_TRANS]
            + [artist, sitename, sitename.replace("www.", "")]
            + self.LYRICS_TRANS
        )
        tokens = [re.escape(t) for t in tokens]
        song_title = re.sub("(%s)" % "|".join(tokens), "", url_title)

        song_title = song_title.strip("_|")
        typo_ratio = 0.9
        ratio = difflib.SequenceMatcher(None, song_title, title).ratio()
        return ratio >= typo_ratio

    def fetch(self, artist: str, title: str, *_) -> str | None:
        params = {
            "key": self.config["google_API_key"].as_str(),
            "cx": self.config["google_engine_ID"].as_str(),
            "q": f"{artist} {title}",
        }

        data = self.fetch_url(self.SEARCH_URL, params=params)
        if not data:
            self._log.debug("google backend returned no data")
            return None
        try:
            data = json.loads(data)
        except ValueError as exc:
            self._log.debug("google backend returned malformed JSON: {}", exc)
        if "error" in data:
            reason = data["error"]["errors"][0]["reason"]
            self._log.debug("google backend error: {0}", reason)
            return None

        if "items" in data.keys():
            for item in data["items"]:
                url_link = item["link"]
                url_title = item.get("title", "")
                if not self.is_page_candidate(
                    url_link, url_title, title, artist
                ):
                    continue
                html = self.fetch_url(url_link)
                if not html:
                    continue
                lyrics = scrape_lyrics_from_html(html)
                if not lyrics:
                    continue

                if self.is_lyrics(lyrics, artist):
                    self._log.debug("got lyrics from {0}", item["displayLink"])
                    return lyrics

        return None


class LyricsPlugin(plugins.BeetsPlugin):
    SOURCES = ["lrclib", "google", "musixmatch", "genius", "tekstowo"]
    SOURCE_BACKENDS = {
        "google": Google,
        "musixmatch": MusiXmatch,
        "genius": Genius,
        "tekstowo": Tekstowo,
        "lrclib": LRCLib,
    }

    def __init__(self):
        super().__init__()
        self.import_stages = [self.imported]
        self.config.add(
            {
                "auto": True,
                "bing_client_secret": None,
                "bing_lang_from": [],
                "bing_lang_to": None,
                "google_API_key": None,
                "google_engine_ID": "009217259823014548361:lndtuqkycfu",
                "genius_api_key": "Ryq93pUGm8bM6eUWwD_M3NOFFDAtp2yEE7W"
                "76V-uFL5jks5dNvcGCdarqFjDhP9c",
                "fallback": None,
                "force": False,
                "local": False,
                "synced": False,
                # Musixmatch is disabled by default as they are currently blocking
                # requests with the beets user agent.
                "sources": [s for s in self.SOURCES if s != "musixmatch"],
                "dist_thresh": 0.1,
            }
        )
        self.config["bing_client_secret"].redact = True
        self.config["google_API_key"].redact = True
        self.config["google_engine_ID"].redact = True
        self.config["genius_api_key"].redact = True

        # State information for the ReST writer.
        # First, the current artist we're writing.
        self.artist = "Unknown artist"
        # The current album: False means no album yet.
        self.album = False
        # The current rest file content. None means the file is not
        # open yet.
        self.rest = None

        available_sources = list(self.SOURCES)
        sources = plugins.sanitize_choices(
            self.config["sources"].as_str_seq(), available_sources
        )

        if not HAS_BEAUTIFUL_SOUP:
            sources = self.sanitize_bs_sources(sources)

        if "google" in sources:
            if not self.config["google_API_key"].get():
                # We log a *debug* message here because the default
                # configuration includes `google`. This way, the source
                # is silent by default but can be enabled just by
                # setting an API key.
                self._log.debug(
                    "Disabling google source: " "no API key configured."
                )
                sources.remove("google")

        self.config["bing_lang_from"] = [
            x.lower() for x in self.config["bing_lang_from"].as_str_seq()
        ]
        self.bing_auth_token = None

        if not HAS_LANGDETECT and self.config["bing_client_secret"].get():
            self._log.warning(
                "To use bing translations, you need to "
                "install the langdetect module. See the "
                "documentation for further details."
            )

        self.backends = [
            self.SOURCE_BACKENDS[source](self.config, self._log)
            for source in sources
        ]

    def sanitize_bs_sources(self, sources):
        enabled_sources = []
        for source in sources:
            if self.SOURCE_BACKENDS[source].REQUIRES_BS:
                self._log.debug(
                    "To use the %s lyrics source, you must "
                    "install the beautifulsoup4 module. See "
                    "the documentation for further details." % source
                )
            else:
                enabled_sources.append(source)

        return enabled_sources

    def get_bing_access_token(self):
        params = {
            "client_id": "beets",
            "client_secret": self.config["bing_client_secret"],
            "scope": "https://api.microsofttranslator.com",
            "grant_type": "client_credentials",
        }

        oauth_url = "https://datamarket.accesscontrol.windows.net/v2/OAuth2-13"
        oauth_token = json.loads(
            requests.post(
                oauth_url,
                data=urlencode(params),
                timeout=10,
            ).content
        )
        if "access_token" in oauth_token:
            return "Bearer " + oauth_token["access_token"]
        else:
            self._log.warning(
                "Could not get Bing Translate API access token."
                ' Check your "bing_client_secret" password'
            )

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
            self._log.info("lyrics already present: {0}", item)
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
            self._log.info("fetched lyrics: {0}", item)
            if HAS_LANGDETECT and self.config["bing_client_secret"].get():
                lang_from = langdetect.detect(lyrics)
                if self.config["bing_lang_to"].get() != lang_from and (
                    not self.config["bing_lang_from"]
                    or (lang_from in self.config["bing_lang_from"].as_str_seq())
                ):
                    lyrics = self.append_translation(
                        lyrics, self.config["bing_lang_to"]
                    )
        else:
            self._log.info("lyrics not found: {0}", item)
            fallback = self.config["fallback"].get()
            if fallback:
                lyrics = fallback
            else:
                return
        item.lyrics = lyrics
        if write:
            item.try_write()
        item.store()

    def get_lyrics(self, artist: str, title: str, *args) -> str | None:
        """Fetch lyrics, trying each source in turn. Return a string or
        None if no lyrics were found.
        """
        for backend in self.backends:
            lyrics = backend.fetch(artist, title, *args)
            if lyrics:
                self._log.debug(
                    "got lyrics from backend: {0}", backend.__class__.__name__
                )
                return _scrape_strip_cruft(lyrics, True)

        return None

    def append_translation(self, text, to_lang):
        from xml.etree import ElementTree

        if not self.bing_auth_token:
            self.bing_auth_token = self.get_bing_access_token()
        if self.bing_auth_token:
            # Extract unique lines to limit API request size per song
            text_lines = set(text.split("\n"))
            url = (
                "https://api.microsofttranslator.com/v2/Http.svc/"
                "Translate?text=%s&to=%s" % ("|".join(text_lines), to_lang)
            )
            r = requests.get(
                url,
                headers={"Authorization ": self.bing_auth_token},
                timeout=10,
            )
            if r.status_code != 200:
                self._log.debug(
                    "translation API error {}: {}", r.status_code, r.text
                )
                if "token has expired" in r.text:
                    self.bing_auth_token = None
                    return self.append_translation(text, to_lang)
                return text
            lines_translated = ElementTree.fromstring(
                r.text.encode("utf-8")
            ).text
            # Use a translation mapping dict to build resulting lyrics
            translations = dict(zip(text_lines, lines_translated.split("|")))
            result = ""
            for line in text.split("\n"):
                result += "{} / {}\n".format(line, translations[line])
            return result
