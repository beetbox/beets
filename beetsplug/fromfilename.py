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
from typing import TypedDict

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
    (?P<artist>.+?(?=[\s_]*?[\.\-]|by.+))?
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
        # ends with a bracket
    """,
    re.VERBOSE | re.IGNORECASE,
)

RE_NAMED_SUBGROUP = re.compile(r"\(\?P\<\w+\>")

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

RE_MEDIA_TYPE = re.compile(
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


class TrackMatch(TypedDict):
    disc: str | None
    track: str | None
    by: NotRequired[str | None]
    artist: str | None
    title: str | None


class AlbumMatch(TypedDict):
    albumartist: str | None
    album: str | None
    year: str | None
    catalognum: str | None
    media: str | None


class FromFilenamePlugin(BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add(
            {
                "fields": [
                    "artist",
                    "album",
                    "albumartist",
                    "catalognum",
                    "disc",
                    "media",
                    "title",
                    "track",
                    "year",
                ],
                "patterns": {"folder": [], "file": []},
                # TODO: Add ignore parent folder
            }
        )
        self.fields = set(self.config["fields"].as_str_seq())
        self.register_listener("import_task_start", self.filename_task)

    @cached_property
    def file_patterns(self) -> list[re.Pattern[str]]:
        return self._user_pattern_to_regex(
            self.config["patterns"]["file"].as_str_seq())

    @cached_property
    def folder_patterns(self) -> list[re.Pattern[str]]:
        return self._user_pattern_to_regex(
            self.config["patterns"]["folder"].as_str_seq()
                                           )

    def filename_task(self, task: ImportTask, session: ImportSession) -> None:
        """ Examines all files in the given import task for any missing
        information it can gather from the file and folder names.

        Once the information has been obtained and checked, it
        is applied to the items to improve later metadata lookup.
        """
        # Create the list of items to process

        items: list[Item] = task.items

        # TODO: Check each of the fields to see if any are missing
        # information on the file.
        parent_folder, item_filenames = self._get_path_strings(items)

        album_matches = self._parse_album_info(parent_folder)
        # Look for useful information in the filenames.
        track_matches = self._build_track_matches(item_filenames)
        # Make sure we got the fields right
        self._sanity_check_matches(album_matches, track_matches)
        # Apply the information
        self._apply_matches(album_matches, track_matches)

    def _user_pattern_to_regex(self, patterns: list[str]) -> list[re.Pattern[str]]:
        """Compile user patterns into a list of usable regex
        patterns. Catches errors are continues without bad regex patterns.
        """
        return [
            re.compile(regexp) for p in patterns if (
            regexp := self._parse_user_pattern_strings(p))
                ]

    @staticmethod
    def _escape(text: str) -> str:
        # escape brackets for fstring logs
        # TODO: Create an issue for brackets in logger
        return re.sub("}", "}}", re.sub("{", "{{", text))

    @staticmethod
    def _get_path_strings(items: list[Item]) -> tuple[str, dict[Item, str]]:
        parent_folder: str = ""
        filenames: dict[Item, str] = {}
        for item in items:
            path: Path = Path(displayable_path(item.path))
            filename = path.stem
            filenames[item] = filename
            if not parent_folder:
                parent_folder = path.parent.stem
        return parent_folder, filenames

    def _check_user_matches(self, text: str,
        patterns: list[re.Pattern[str]]) -> dict[str, str]:
        for p in patterns:
            if (usermatch := p.fullmatch(text)):
                return usermatch.groupdict()
        return None

    def _build_track_matches(self,
        item_filenames: dict[Item, str]) -> dict[Item, dict[str, str]]:
        track_matches: dict[Item, dict[str, str]] = {}
        for item, filename in item_filenames.items():
            if (m := self._check_user_matches(filename, self.file_patterns)):
                track_matches[item] = m
            else:
                match = self._parse_track_info(filename)
                track_matches[item] = match
        return track_matches

    @staticmethod
    def _parse_track_info(text: str) -> TrackMatch:
        trackmatch: TrackMatch = {
            "disc": None,
            "track": None,
            "by": None,
            "artist": None,
            "title": None,
        }
        match = RE_TRACK_INFO.match(text)
        assert match is not None
        if disc := match.group("disc"):
            trackmatch["disc"] = str(disc)
        if track := match.group("track"):
            trackmatch["track"] = str(track).strip()
        if by := match.group("by"):
            trackmatch["by"] = str(by)
        if artist := match.group("artist"):
            trackmatch["artist"] = str(artist).strip()
        if title := match.group("title"):
            trackmatch["title"] = str(title).strip()
        # if the phrase "by" is matched, swap artist and title
        if trackmatch["by"]:
            artist = trackmatch["title"]
            trackmatch["title"] = trackmatch["artist"]
            trackmatch["artist"] = artist
        # remove that key
        del trackmatch["by"]
        # if all fields except `track` are none
        # set title to track number as well
        # we can't be sure if it's actually the track number
        # or track title
        if set(trackmatch.values()) == {None, trackmatch["track"]}:
            trackmatch["title"] = trackmatch["track"]

        return trackmatch

    def _parse_album_info(self, text: str) -> dict[str, str]:
        # Check if a user pattern matches
        if (m := self._check_user_matches(text, self.folder_patterns)):
            return m
        matches: AlbumMatch = {
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

    def _apply_matches(
        self, album_match: AlbumMatch, track_matches: dict[Item, TrackMatch]
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
                    new_value = match[key]  # type: ignore
                    if self._bad_field(old_value) and new_value:
                        found_data[key] = new_value
            self._log.info(f"Item updated with: {found_data.items()}")
            item.update(found_data)

    @staticmethod
    def _parse_album_and_albumartist(
        text: str,
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

    @staticmethod
    def _parse_year(text: str) -> tuple[str | None, tuple[int, int]]:
        """The year will be a four digit number. The search goes
        through a list of ordered patterns to try and find the year.
        To be a valid year, it must be less than the current year.
        """
        current_year = datetime.now().year
        year = None
        span = (0, 0)
        for exp in YEAR_REGEX:
            match = exp.search(text)
            if not match:
                continue
            year_candidate = match.group("year")
            # If the year is matched and not in the future
            if year_candidate and int(year_candidate) <= current_year:
                year = year_candidate
                span = match.span()
                break
        return year, span

    @staticmethod
    def _parse_media(text: str) -> tuple[str | None, tuple[int, int]]:
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
        match = RE_MEDIA_TYPE.search(text)
        if match:
            media = None
            for key, value in match.groupdict().items():
                if value:
                    media = mappings[key]
            return media, match.span()
        return None, (0, 0)

    @staticmethod
    def _parse_catalognum(text: str) -> tuple[str | None, tuple[int, int]]:
        match = RE_CATALOGNUM.search(text)
        # assert that it cannot be mistaken for a media type
        if match and not RE_MEDIA_TYPE.match(match[0]):
            return match.group("catalognum"), match.span()
        return None, (0, 0)

    def _parse_user_pattern_strings(self, text: str) -> str | None:
        # escape any special characters
        fields: list[str] = [s.lower() for s in re.findall(r"\$([a-zA-Z\_]+)", text)]
        if not fields:
            # if there are no usable fields
            return None
        pattern = re.escape(text)
        for f in fields:
            pattern = re.sub(rf"\\\${f}", f"(?P<{f}>.+)", pattern)
            self.fields.add(f)
        return rf"{pattern}"

    @staticmethod
    def _mutate_string(text: str, span: tuple[int, int]) -> str:
        """Replace a matched field with a seperator"""
        start, end = span
        text = text[:start] + "-" + text[end:]
        return text

    def _sanity_check_matches(
        self, album_match: AlbumMatch, track_matches: dict[Item, TrackMatch]
    ) -> None:
        """Check to make sure data is coherent between
        track and album matches. Largely looking to see
        if the arist and album artist fields are properly
        identified.
        """

        def swap_artist_title(tracks: list[TrackMatch]):
            for track in tracks:
                artist = track["title"]
                track["title"] = track["artist"]
                track["artist"] = artist
            # swap the track titles and track artists
            self._log.info("Swapped title and artist fields.")

        # None of this logic applies if there's only one track
        if len(track_matches) < 2:
            return

        tracks: list[TrackMatch] = list(track_matches.values())
        album_artist = album_match["albumartist"]
        one_artist = self._equal_fields(tracks, "artist")
        one_title = self._equal_fields(tracks, "title")

        if not album_artist or album_artist != config["va_name"].as_str():
            if one_artist and not one_title:
                # All the artist fields match, and the title fields don't
                # It's probably the artist
                return
            elif one_title and not one_artist and not album_artist:
                # If the track titles match, and there's no album
                # artist to check on
                swap_artist_title(tracks)
            elif album_artist:
                # The artist fields don't match, and the title fields don't match
                # If the albumartist field matches any track, then we know
                # that the track field is likely the artist field.
                # Sometimes an album has a presenter credited
                track_titles = [str(t["title"]).upper() for t in tracks]
                if album_artist and album_artist.upper() in track_titles:
                    swap_artist_title(tracks)
        return

    @staticmethod
    def _equal_fields(dictionaries: list[TrackMatch], field: str) -> bool:
        """Checks if all values of a field on a dictionary match."""
        return len(set(d[field] for d in dictionaries)) <= 1  # type: ignore

    @staticmethod
    def _bad_field(field: str | int) -> bool:
        """Determine whether a given title is "bad" (empty or otherwise
        meaningless) and in need of replacement.
        """
        if isinstance(field, int):
            return True if field <= 0 else False
        return True if RE_BAD_FIELD.match(field) else False
