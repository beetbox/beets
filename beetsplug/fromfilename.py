# This file is part of beets.
# Copyright 2016, Jan-Erik Dahlin
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

"""If the title is empty, try to extract it from the filename
(possibly also extract track and artist)
"""

import re
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any, TypedDict

from typing_extensions import NotRequired

from beets import config
from beets.importer import ImportSession, ImportTask
from beets.library import Item
from beets.plugins import BeetsPlugin
from beets.util import displayable_path

# Filename field extraction patterns
RE_TRACK_INFO = re.compile(
    r"""
    (?P<disc>\d+(?=[\.\-_]\d))?
        # a disc must be followed by punctuation and a digit
    [\.\-]{,1}
        # disc punctuation
    (?P<track>\d+)?
        # match the track number
    [\.\-_\s]*
        # artist separators
    (?P<artist>.+?(?=[\s*_]?[\.\-by].+))?
        # artist match depends on title existing
    [\.\-_\s]*
    (?P<by>by)?
        # if 'by' is found, artist and title will need to be swapped
    [\.\-_\s]*
        # title separators
    (?P<title>.+)?
        # match the track title
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Catalog number extraction pattern
RE_CATALOGNUM = re.compile(
    r"""
    [\(\[\{]
        # starts with a bracket
    (?!flac|mp3|wav)
        # does not start with file format
    (?P<catalognum>[\w\s]+)
        # actual catalog number
    (?<!flac|.mp3|.wav)
        # does not end with file format
    [\)\]\}]
        # ends with a bracker
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Match the disc names of parent folders
RE_DISC = re.compile(r"((?:cd|disc)\s*\d+)", re.IGNORECASE)

# Matches fields that are empty or only whitespace
RE_BAD_FIELD = re.compile(r"^\s*$")

# First priority for matching a year is a year surrounded
# by brackets, dashes, or punctuation
RE_YEAR_BRACKETED = re.compile(
    r"[\(\[\{\-\_]\s*(?P<year>\d{4}).*?[\)\]\}\-\_,]"
)

# Look for a year at the start
RE_YEAR_START = re.compile(r"^(?P<year>\d{4})")

# Look for a year at the end
RE_YEAR_END = re.compile(r"$(?P<year>\d{4})")

# Just look for four digits
RE_YEAR_ANY = re.compile(r"(?P<year>\d{4})")

# All year regexp in order of preference
YEAR_REGEX = [RE_YEAR_BRACKETED, RE_YEAR_START, RE_YEAR_END, RE_YEAR_ANY]

RE_MEDIA = re.compile(
    r"""
    [\(\[\{].*?
    ((?P<vinyl>vinyl)|
    (?P<cd>cd)|
    (?P<web>web)|
    (?P<cassette>cassette))
    .*?[\)\]\}]
    """,
    re.VERBOSE | re.IGNORECASE,
)

RE_VARIOUS = re.compile(r"va(rious)?(\sartists)?", re.IGNORECASE)

RE_SPLIT = re.compile(r"[\-\_]+")

RE_BRACKETS = re.compile(r"[\(\[\{].*?[\)\]\}]")


class TrackMatches(TypedDict):
    disc: str | None
    track: str | None
    by: NotRequired[str | None]
    artist: str | None
    title: str | None


class AlbumMatches(TypedDict):
    albumartist: str | None
    album: str | None
    year: str | None
    catalognum: str | None
    media: str | None


def equal_fields(matchdict: dict[Any, TrackMatches], field: str) -> bool:
    """Do all items in `matchdict`, whose values are dictionaries, have
    the same value for `field`? (If they do, the field is probably not
    the title.)
    """
    return len(set(m[field] for m in matchdict.values())) <= 1


def all_matches(
    names: dict[Item, str], pattern: str
) -> dict[Item, TrackMatches] | None:
    """If all the filenames in the item/filename mapping match the
    pattern, return a dictionary mapping the items to dictionaries
    giving the value for each named subpattern in the match. Otherwise,
    return None.
    """
    matches = {}
    for item, name in names.items():
        m = re.match(pattern, name, re.IGNORECASE)
        if m and m.groupdict():
            # Only yield a match when the regex applies *and* has
            # capture groups. Otherwise, no information can be extracted
            # from the filename.
            matches[item] = m.groupdict()
        else:
            return None
    return matches


class FromFilenamePlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add(
            {
                "fields": [
                    "disc",
                    "track",
                    "title",
                    "artist",
                    "albumartist",
                    "media",
                    "catalognum",
                ]
            }
        )
        self.register_listener("import_task_start", self.filename_task)

    @cached_property
    def current_year(self) -> int:
        return datetime.now().year

    @cached_property
    def fields(self) -> set[str]:
        return set(self.config["fields"].as_str_seq())

    def filename_task(self, task: ImportTask, session: ImportSession) -> None:
        """Examine each item in the task to see if we can extract a title
        from the filename. Try to match all filenames to a number of
        regexps, starting with the most complex patterns and successively
        trying less complex patterns. As soon as all filenames match the
        same regex we can make an educated guess of which part of the
        regex that contains the title.
        """
        # Create the list of items to process

        # TODO: If it's a singleton import task, use the .item field
        items: list[Item] = task.items

        # TODO: Switch this to gather data anyway, but only
        # update where missing
        # Look for suspicious (empty or meaningless) titles.
        missing_titles = sum(self._bad_field(i.title) for i in items)

        if missing_titles:
            # Get the base filenames (no path or extension).
            parent_path: str = ""
            names: dict[Item, str] = {}
            for item in items:
                path: Path = Path(displayable_path(item.path))
                name = path.stem
                names[item] = name
                if not parent_path:
                    parent_path = path.parent.stem
                    self._log.debug(f"Parent Path: {parent_path}")

            album_matches: AlbumMatches = self.parse_album_info(parent_path)
            self._log.debug(album_matches)
            # Look for useful information in the filenames.
            track_matches: dict[Item, TrackMatches] = {}
            for item, name in names.items():
                m = self.parse_track_info(name)
                track_matches[item] = m
            self._apply_matches(album_matches, track_matches)

    def parse_track_info(self, text: str) -> TrackMatches:
        m = RE_TRACK_INFO.match(text)
        matches: TrackMatches = m.groupdict()
        # if the phrase "by" is matched, swap
        # artist and title
        if matches["by"]:
            artist = matches["title"]
            matches["title"] = matches["artist"]
            matches["artist"] = artist
        # remove that key
        del matches["by"]
        # if all fields except `track` are none
        # set title to track number as well
        # we can't be sure if it's actually the track number
        # or track title
        if set(matches.values()) == {None, matches["track"]}:
            matches["title"] = matches["track"]

        return matches

    def parse_album_info(self, text: str) -> AlbumMatches:
        matches: AlbumMatches = {
            "albumartist": None,
            "album": None,
            "year": None,
            "catalognum": None,
            "media": None,
        }
        # Start with the extra fields to make parsing
        # the album artist and artist field easier
        year, span = self._parse_year(text)
        if year:
            # Remove it from the string if found
            text = self._mutate_string(text, span)
            matches["year"] = year

        # Look for the catalog number, it must be in brackets
        # It will not contain the filetype, flac, mp3, wav, etc
        catalognum, span = self._parse_catalognum(text)
        if catalognum:
            text = self._mutate_string(text, span)
            matches["catalognum"] = catalognum
        # Look for a media type
        media, span = self._parse_media(text)
        if media:
            text = self._mutate_string(text, span)
            matches["media"] = media

        # Remove anything left within brackets
        brackets = RE_BRACKETS.search(text)
        while brackets:
            span = brackets.span()
            text = self._mutate_string(text, span)
            brackets = RE_BRACKETS.search(text)
        # Remaining text used for album, albumartist
        album, albumartist = self._parse_album_and_albumartist(text)
        matches["album"] = album
        matches["albumartist"] = albumartist

        return matches

    def _parse_album_and_albumartist(
        self, text
    ) -> tuple[str | None, str | None]:
        """Takes the remaining string and splits it along common dividers.
        Assumes the first field to be the albumartist and the last field to be the
        album. Checks against various artist fields.
        """
        possible_albumartist = None
        possible_album = None
        # What is left we can assume to contain the title and artist
        remaining = [
            f for field in RE_SPLIT.split(text) if (f := field.strip())
        ]
        if remaining:
            # If two fields remain, assume artist and album artist
            if len(remaining) == 2:
                possible_albumartist = remaining[0]
                possible_album = remaining[1]
                # Look for known album artists
                # VA, Various, Vartious Artists will all result in
                # using the beets VA default for album artist name
                # assume the artist comes before the title in most situations
                if RE_VARIOUS.match(possible_album):
                    possible_album = possible_albumartist
                    possible_albumartist = config["va_name"].as_str()
                elif RE_VARIOUS.match(possible_albumartist):
                    possible_albumartist = config["va_name"].as_str()
            else:
                # If one field remains, assume album title
                possible_album = remaining[0].strip()
        return possible_album, possible_albumartist

    def _parse_year(self, text: str) -> tuple[str | None, tuple[int, int]]:
        """The year will be a four digit number. The search goes
        through a list of ordered patterns to try and find the year.
        To be a valid year, it must be less than the current year.
        """
        year = None
        span = (0, 0)
        for exp in YEAR_REGEX:
            match = exp.search(text)
            if not match:
                continue
            year_candidate = match.group("year")
            # If the year is matched and not in the future
            if year_candidate and int(year_candidate) <= self.current_year:
                year = year_candidate
                span = match.span()
                break
        return year, span

    def _parse_media(self, text: str) -> tuple[str | None, tuple[int, int]]:
        """Look for the media type, we are only interested in a few common
        types - CD, Vinyl, Cassette or WEB. To avoid overreach, in the
        case of titles containing a medium, only searches for media types
        within a pair of brackets.
        """
        mappings = {
            "cd": "CD",
            "vinyl": "Vinyl",
            "web": "Digital Media",
            "cassette": "Cassette",
        }
        match = RE_MEDIA.search(text)
        if match:
            media = None
            for key, value in match.groupdict().items():
                if value:
                    media = mappings[key]
            return media, match.span()
        return None, (0, 0)

    def _parse_catalognum(
        self, text: str
    ) -> tuple[str | None, tuple[int, int]]:
        match = RE_CATALOGNUM.search(text)
        # assert that it cannot be mistaken for a media type
        if match and not RE_MEDIA.match(match[0]):
            return match.group("catalognum"), match.span()
        return None, (0, 0)

    def _mutate_string(self, text, span: tuple[int, int]) -> str:
        """Replace a matched field with a seperator"""
        start, end = span
        text = text[:start] + "-" + text[end:]
        return text

    def _sanity_check_matches(
        self, album_match: AlbumMatches, track_matches: dict[Item, TrackMatches]
    ) -> None:
        """Check to make sure data is coherent between
        track and album matches. Largely looking to see
        if the arist and album artist fields are properly
        identified.
        """
        # If the album artist is not various artists
        # check that all artists, if any, match
        # if they do not, try seeing if all the titles match
        # if all the titles match, swap title and artist fields

        # If the suspected title and albumartist fields are not equal
        # we have ruled out a self titled album
        # Check if the suspected title appears in the track artists
        # If so, we should swap the title and albumartist in albummatches

        # If any track title is the same as the album artist
        # some_map = list(track_matches.values())[0]
        # keys = some_map.keys()

        # Given both an "artist" and "title" field, assume that one is
        # *actually* the artist, which must be uniform, and use the other
        # for the title. This, of course, won't work for VA albums.
        # Only check for "artist": patterns containing it, also contain "title"
        # if "artist" in keys:
        #     if equal_fields(track_matches, "artist"):
        #         artist = some_map["artist"]
        #         title_field = "title"
        #     elif equal_fields(track_matches, "title"):
        #         artist = some_map["title"]
        #         title_field = "artist"
        #     else:
        #         # Both vary. Abort.
        #         return
        #
        #     for item in track_matches:
        #         if not item.artist and artist:
        #             item.artist = artist
        #             self._log.info(f"Artist replaced with: {item.artist}")
        # # otherwise, if the pattern contains "title", use that for title_field

        return

    def _apply_matches(
        self, album_match: AlbumMatches, track_matches: dict[Item, TrackMatches]
    ) -> None:
        """Apply all valid matched fields to all items in the match dictionary."""
        match = album_match
        for item in track_matches:
            match.update(track_matches[item])
            found_data: dict[str, int | str] = {}
            self._log.debug(f"Attempting keys: {match.keys()}")
            for key in match.keys():
                if key in self.fields:
                    old_value = item.get(key)
                    new_value = match[key]
                    if self._bad_field(old_value) and new_value:
                        found_data[key] = new_value
            self._log.info(f"Item updated with: {found_data.values()}")
            item.update(found_data)

    @staticmethod
    def _bad_field(field: str | int) -> bool:
        """Determine whether a given title is "bad" (empty or otherwise
        meaningless) and in need of replacement.
        """
        if isinstance(field, int):
            return True if field <= 0 else False
        return True if RE_BAD_FIELD.match(field) else False
