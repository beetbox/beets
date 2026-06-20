# This file is part of beets.
# Copyright 2016, Verrus, <github.com/Verrus/beets-plugin-featInTitle>
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

"""Moves "featured" artists to the title from the artist field."""

from __future__ import annotations

import re
from functools import cached_property, lru_cache
from typing import TYPE_CHECKING

from beets import config, plugins, ui

if TYPE_CHECKING:
    from beets.autotag import AlbumInfo, Info, TrackInfo
    from beets.importer import ImportSession, ImportTask
    from beets.library import Album, Item


DEFAULT_BRACKET_KEYWORDS: tuple[str, ...] = (
    "abridged",
    "acapella",
    "club",
    "demo",
    "edit",
    "edition",
    "extended",
    "instrumental",
    "live",
    "mix",
    "radio",
    "release",
    "remaster",
    "remastered",
    "remix",
    "rmx",
    "unabridged",
    "unreleased",
    "version",
    "vip",
)


def _split_on_feat_token(
    regex: re.Pattern[str], artist: str
) -> tuple[str, str] | None:
    match = regex.search(artist)
    if not match:
        return None

    left = artist[: match.start()].strip()
    right = artist[match.end() :].strip()
    opener = match.group(0)[0]

    if opener == "(":
        closing = ")"
    elif opener == "[":
        closing = "]"
    else:
        closing = None

    if closing:
        if right.endswith(closing):
            right = right[:-1].strip()
        else:
            left = f"{left} {opener}".strip()

    return left, right


def split_on_feat(
    artist: str, for_artist: bool = True, custom_words: list[str] | None = None
) -> tuple[str, str | None]:
    """Given an artist string, split the "main" artist from any artist
    on the right-hand side of a string like "feat". Return the main
    artist, which is always a string, and the featuring artist, which
    may be a string or None if none is present.
    """
    # Try explicit featuring tokens first (ft, feat, featuring, etc.)
    # to avoid splitting on generic separators like "&" when both are present
    regex_explicit = re.compile(
        plugins.feat_tokens(for_artist=False, custom_words=custom_words),
        re.IGNORECASE,
    )
    parts = _split_on_feat_token(regex_explicit, artist)
    if parts:
        return parts

    # Try comma as separator
    # (e.g. "Alice, Bob & Charlie" where Bob and Charlie are featuring)
    if for_artist and "," in artist:
        comma_parts = artist.split(",", 1)
        return comma_parts[0].strip(), comma_parts[1].strip()

    # Fall back to all tokens including generic separators if no explicit match
    if for_artist:
        regex = re.compile(
            plugins.feat_tokens(for_artist, custom_words), re.IGNORECASE
        )
        parts = _split_on_feat_token(regex, artist)
        if parts:
            return parts

    return artist.strip(), None


def contains_feat(title: str, custom_words: list[str] | None = None) -> bool:
    """Determine whether the title contains a "featured" marker."""
    return bool(
        re.search(
            plugins.feat_tokens(for_artist=False, custom_words=custom_words),
            title,
            flags=re.IGNORECASE,
        )
    )


def find_feat_part(
    artist: str, albumartist: str | None, custom_words: list[str] | None = None
) -> str | None:
    """Attempt to find featured artists in the item's artist fields and
    return the results. Returns None if no featured artist found.
    """
    if not albumartist:
        _, feat_part = split_on_feat(
            artist, for_artist=True, custom_words=custom_words
        )
        return feat_part

    # If the album artist is featured, move the remaining artist to the title.
    artist_part, feat_part = split_on_feat(artist, custom_words=custom_words)
    if feat_part == albumartist and artist_part:
        return artist_part

    # Handle a wider variety of extraction cases if the album artist is
    # contained within the track artist.
    if albumartist in artist:
        albumartist_split = artist.split(albumartist, 1)

        # If the last element of the split (the right-hand side of the
        # album artist) is nonempty, then it probably contains the
        # featured artist.
        if albumartist_split[1] != "":
            # Extract the featured artist from the right-hand side.
            _, feat_part = split_on_feat(
                albumartist_split[1], custom_words=custom_words
            )
            return feat_part

        # Otherwise, if there's nothing on the right-hand side,
        # look for a featuring artist on the left-hand side.
        lhs, _ = split_on_feat(albumartist_split[0], custom_words=custom_words)
        if lhs:
            return lhs

    # Fall back to conservative handling of the track artist without relying
    # on albumartist, which covers compilations using a 'Various Artists'
    # albumartist and album tracks by a guest artist featuring a third artist.
    _, feat_part = split_on_feat(artist, False, custom_words)
    return feat_part


def _album_artist_no_feat(album: Album) -> str:
    custom_words = config["ftintitle"]["custom_words"].as_str_seq()
    return split_on_feat(album["albumartist"], False, list(custom_words))[0]


class FtInTitlePlugin(plugins.BeetsPlugin):
    @cached_property
    def auto(self) -> bool:
        return self.config["auto"].get(bool)

    @cached_property
    def drop_feat(self) -> bool:
        return self.config["drop"].get(bool)

    @cached_property
    def feat_format(self) -> str:
        return self.config["format"].as_str()

    @cached_property
    def keep_in_artist_field(self) -> bool:
        return self.config["keep_in_artist"].get(bool)

    @cached_property
    def preserve_album_artist(self) -> bool:
        return self.config["preserve_album_artist"].get(bool)

    @cached_property
    def custom_words(self) -> list[str]:
        return self.config["custom_words"].as_str_seq()

    @cached_property
    def artist_credit(self) -> bool:
        # This is the root-level import option, not an ftintitle option.
        return config["artist_credit"].get(bool)

    @cached_property
    def bracket_keywords(self) -> list[str]:
        return self.config["bracket_keywords"].as_str_seq()

    @staticmethod
    @lru_cache(maxsize=256)
    def _bracket_position_pattern(keywords: tuple[str, ...]) -> re.Pattern[str]:
        """
        Build a compiled regex to find the first bracketed segment that contains
        any of the provided keywords.

        Cached by keyword tuple to avoid recompiling on every track/title.
        """
        kw_inner = "|".join(map(re.escape, keywords))

        # If we have keywords, require one of them to appear in the bracket text.
        # If kw == "", the lookahead becomes true and we match any bracket content.
        kw = rf"\b(?={kw_inner})\b" if kw_inner else ""
        return re.compile(
            rf"""
            (?:   # non-capturing group for the split
              \s*?  # optional whitespace before brackets
              (?=     # any bracket containing a keyword
                    \([^)]*{kw}.*?\)
                |   \[[^]]*{kw}.*?\]
                |    <[^>]*{kw}.*? >
                | \{{[^}}]*{kw}.*?\}}
                | $   # or the end of the string
              )
            )
            """,
            re.IGNORECASE | re.VERBOSE,
        )

    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {
                "auto": True,
                "drop": False,
                "format": "feat. {}",
                "keep_in_artist": False,
                "preserve_album_artist": True,
                "custom_words": [],
                "bracket_keywords": list(DEFAULT_BRACKET_KEYWORDS),
            }
        )

        self._command = ui.Subcommand(
            "ftintitle", help="move featured artists to the title field"
        )

        self._command.parser.add_option(
            "-d",
            "--drop",
            dest="drop",
            action="store_true",
            default=None,
            help="drop featuring from artists and ignore title update",
        )

        self.import_stages = [self.imported]
        self.register_listener("trackinfo_received", self.trackinfo_received)
        self.register_listener("albuminfo_received", self.albuminfo_received)

        self.album_template_fields["album_artist_no_feat"] = (
            _album_artist_no_feat
        )

    @staticmethod
    def _field_value(metadata: object, field: str) -> str:
        return getattr(metadata, field, None) or ""

    def _effective_artist(self, metadata: object) -> str:
        if self.artist_credit:
            return self._field_value(
                metadata, "artist_credit"
            ) or self._field_value(metadata, "artist")
        return self._field_value(metadata, "artist")

    def _strip_featured_from_field(
        self, metadata: object, field: str, for_artist: bool = True
    ) -> None:
        value = self._field_value(metadata, field)
        if value:
            stripped, _ = split_on_feat(
                value, for_artist=for_artist, custom_words=self.custom_words
            )
            setattr(metadata, field, stripped)

    def commands(self) -> list[ui.Subcommand]:
        def func(lib, opts, args):
            self.config.set_args(opts)
            write = ui.should_write()

            for item in lib.items(args):
                if self.ft_in_title(item):
                    item.store()
                    if write:
                        item.try_write()

        self._command.func = func
        return [self._command]

    def imported(self, session: ImportSession, task: ImportTask) -> None:
        """Import hook for moving featuring artist automatically."""
        if not self.auto:
            return

        for item in task.imported_items():
            if self.ft_in_title(item):
                item.store()

    def trackinfo_received(self, info: TrackInfo) -> None:
        """Move featuring artists in fetched singleton metadata."""
        if not self.auto:
            return

        self.ft_in_info(info)

    def albuminfo_received(self, info: AlbumInfo) -> None:
        """Move featuring artists in fetched album track metadata."""
        if not self.auto:
            return

        albumartist = self._effective_artist(info)
        for track_info in info.tracks:
            self.ft_in_info(track_info, albumartist)

    def update_item_metadata(self, item: Item, feat_part: str) -> bool:
        """Choose how to add new artists to the title and set the new
        metadata. Also, print out messages about any changes that are made.
        If `drop_feat` is set, then do not add the artist to the title; just
        remove it from the artist field.
        """
        changed = False

        # In case the artist is kept, do not update the artist fields.
        if self.keep_in_artist_field:
            self._log.info(
                "artist: {.artist} (Not changing due to keep_in_artist)", item
            )
        else:
            artist = self._field_value(item, "artist")
            track_artist, _ = split_on_feat(
                artist, custom_words=self.custom_words
            )
            self._log.info("artist: {0.artist} -> {1}", item, track_artist)
            item.artist = track_artist
            changed |= artist != track_artist

            if self.artist_credit:
                artist_credit = self._field_value(item, "artist_credit")
                self._strip_featured_from_field(item, "artist_credit")
                changed |= artist_credit != self._field_value(
                    item, "artist_credit"
                )

        artist_sort = self._field_value(item, "artist_sort")
        if artist_sort:
            # Just strip the featured artist from the sort name.
            artist_sort_no_feat, _ = split_on_feat(
                artist_sort, custom_words=self.custom_words
            )
            item.artist_sort = artist_sort_no_feat
            changed |= artist_sort != artist_sort_no_feat

        # Only update the title if it does not already contain a featured
        # artist and if we do not drop featuring information.
        title = self._field_value(item, "title")
        if not self.drop_feat and not contains_feat(title, self.custom_words):
            formatted = self.feat_format.format(feat_part)
            new_title = self.insert_ft_into_title(
                title, formatted, self.bracket_keywords
            )
            self._log.info("title: {.title} -> {}", item, new_title)
            item.title = new_title
            changed |= title != new_title

        return changed

    def update_info_metadata(self, info: Info, feat_part: str) -> bool:
        """Choose how to add featured artists to fetched metadata."""
        changed = False
        if not self.keep_in_artist_field:
            before = (
                self._field_value(info, "artist"),
                self._field_value(info, "artist_credit"),
                self._field_value(info, "artist_sort"),
            )
            self._strip_featured_from_field(info, "artist")
            if self.artist_credit:
                self._strip_featured_from_field(
                    info, "artist_credit", for_artist=False
                )
            self._strip_featured_from_field(info, "artist_sort")
            changed |= before != (
                self._field_value(info, "artist"),
                self._field_value(info, "artist_credit"),
                self._field_value(info, "artist_sort"),
            )

        title = self._field_value(info, "title")
        if not self.drop_feat and not contains_feat(title, self.custom_words):
            formatted = self.feat_format.format(feat_part)
            new_title = self.insert_ft_into_title(
                title, formatted, self.bracket_keywords
            )
            info.title = new_title
            changed |= title != new_title

        return changed

    def ft_in_info(self, info: Info, albumartist: str | None = None) -> bool:
        """Move featuring artists in fetched metadata and clear Info caches."""
        artist = self._effective_artist(info).strip()
        if not self._has_feat_candidate(artist, albumartist):
            return False

        feat_part = find_feat_part(
            artist, (albumartist or "").strip(), self.custom_words
        )
        if not feat_part:
            self._log.info("no featuring artists found")
            return False

        return self.update_info_metadata(info, feat_part)

    def ft_in_title(self, item: Item) -> bool:
        """Look for featured artists in the item's artist fields and move
        them to the title.

        Returns:
            True if the item has been modified. False otherwise.
        """
        artist = self._effective_artist(item).strip()
        albumartist = self._field_value(item, "albumartist")
        if not self._has_feat_candidate(artist, albumartist):
            return False

        self._log.info("{.filepath}", item)
        feat_part = find_feat_part(
            artist, albumartist.strip(), self.custom_words
        )
        if not feat_part:
            self._log.info("no featuring artists found")
            return False

        return self.update_item_metadata(item, feat_part)

    def _has_feat_candidate(self, artist: str, albumartist: str | None) -> bool:
        albumartist = (albumartist or "").strip()
        if self.preserve_album_artist and albumartist and artist == albumartist:
            return False

        for_artist = not albumartist or albumartist in artist
        _, featured = split_on_feat(
            artist, for_artist=for_artist, custom_words=self.custom_words
        )
        return bool(featured)

    @classmethod
    def insert_ft_into_title(
        cls, title: str, feat_part: str, keywords: list[str] | None = None
    ) -> str:
        """Insert featured artist before the first bracket containing
        remix/edit keywords if present.
        """
        normalized = (
            DEFAULT_BRACKET_KEYWORDS if keywords is None else tuple(keywords)
        )
        pattern = cls._bracket_position_pattern(normalized)
        parts = pattern.split(title, maxsplit=1)
        return f" {feat_part} ".join(parts).strip()
