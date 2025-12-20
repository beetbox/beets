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

from beets import plugins, ui

if TYPE_CHECKING:
    from beets.importer import ImportSession, ImportTask
    from beets.library import Item


def split_on_feat(
    artist: str,
    for_artist: bool = True,
    custom_words: list[str] | None = None,
) -> tuple[str, str | None]:
    """Given an artist string, split the "main" artist from any artist
    on the right-hand side of a string like "feat". Return the main
    artist, which is always a string, and the featuring artist, which
    may be a string or None if none is present.
    """
    # split on the first "feat".
    regex = re.compile(
        plugins.feat_tokens(for_artist, custom_words), re.IGNORECASE
    )
    parts = tuple(s.strip() for s in regex.split(artist, 1))
    if len(parts) == 1:
        return parts[0], None
    else:
        assert len(parts) == 2  # help mypy out
        return parts


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
    artist: str,
    albumartist: str | None,
    custom_words: list[str] | None = None,
) -> str | None:
    """Attempt to find featured artists in the item's artist fields and
    return the results. Returns None if no featured artist found.
    """
    # Handle a wider variety of extraction cases if the album artist is
    # contained within the track artist.
    if albumartist and albumartist in artist:
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
        else:
            lhs, _ = split_on_feat(
                albumartist_split[0], custom_words=custom_words
            )
            if lhs:
                return lhs

    # Fall back to conservative handling of the track artist without relying
    # on albumartist, which covers compilations using a 'Various Artists'
    # albumartist and album tracks by a guest artist featuring a third artist.
    _, feat_part = split_on_feat(artist, False, custom_words)
    return feat_part


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


class FtInTitlePlugin(plugins.BeetsPlugin):
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
        # If kw == "", the lookahead becomes trivially true and we match any bracket content.
        kw = rf"\b(?:{kw_inner})\b" if kw_inner else ""

        return re.compile(
            rf"""
            (?:                     # Match ONE bracketed segment of any supported type
              \(                    # "("
                (?=[^)]*{kw})       # Lookahead: keyword must appear before closing ")"
                                      # - if kw == "", this is always true
                [^)]*               # Consume bracket content (no nested ")" handling)
              \)                    # ")"

            | \[                    # "["
                (?=[^\]]*{kw})      # Lookahead
                [^\]]*              # Consume content up to first "]"
              \]                    # "]"

            | <                     # "<"
                (?=[^>]*{kw})       # Lookahead
                [^>]*               # Consume content up to first ">"
              >                     # ">"

            | \x7B                  # Literal open brace
                (?=[^\x7D]*{kw})    # Lookahead
                [^\x7D]*            # Consume content up to first close brace
              \x7D                  # Literal close brace
            )                       # End bracketed segment alternation
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

        if self.config["auto"]:
            self.import_stages = [self.imported]

    def commands(self) -> list[ui.Subcommand]:
        def func(lib, opts, args):
            self.config.set_args(opts)
            drop_feat = self.config["drop"].get(bool)
            keep_in_artist_field = self.config["keep_in_artist"].get(bool)
            preserve_album_artist = self.config["preserve_album_artist"].get(
                bool
            )
            custom_words = self.config["custom_words"].get(list)
            write = ui.should_write()

            for item in lib.items(args):
                if self.ft_in_title(
                    item,
                    drop_feat,
                    keep_in_artist_field,
                    preserve_album_artist,
                    custom_words,
                ):
                    item.store()
                    if write:
                        item.try_write()

        self._command.func = func
        return [self._command]

    def imported(self, session: ImportSession, task: ImportTask) -> None:
        """Import hook for moving featuring artist automatically."""
        drop_feat = self.config["drop"].get(bool)
        keep_in_artist_field = self.config["keep_in_artist"].get(bool)
        preserve_album_artist = self.config["preserve_album_artist"].get(bool)
        custom_words = self.config["custom_words"].get(list)

        for item in task.imported_items():
            if self.ft_in_title(
                item,
                drop_feat,
                keep_in_artist_field,
                preserve_album_artist,
                custom_words,
            ):
                item.store()

    def update_metadata(
        self,
        item: Item,
        feat_part: str,
        drop_feat: bool,
        keep_in_artist_field: bool,
        custom_words: list[str],
    ) -> None:
        """Choose how to add new artists to the title and set the new
        metadata. Also, print out messages about any changes that are made.
        If `drop_feat` is set, then do not add the artist to the title; just
        remove it from the artist field.
        """
        # In case the artist is kept, do not update the artist fields.
        if keep_in_artist_field:
            self._log.info(
                "artist: {.artist} (Not changing due to keep_in_artist)", item
            )
        else:
            track_artist, _ = split_on_feat(
                item.artist, custom_words=custom_words
            )
            self._log.info("artist: {0.artist} -> {1}", item, track_artist)
            item.artist = track_artist

        if item.artist_sort:
            # Just strip the featured artist from the sort name.
            item.artist_sort, _ = split_on_feat(
                item.artist_sort, custom_words=custom_words
            )

        # Only update the title if it does not already contain a featured
        # artist and if we do not drop featuring information.
        if not drop_feat and not contains_feat(item.title, custom_words):
            feat_format = self.config["format"].as_str()
            formatted = feat_format.format(feat_part)
            new_title = FtInTitlePlugin.insert_ft_into_title(
                item.title, formatted, self.bracket_keywords
            )
            self._log.info("title: {.title} -> {}", item, new_title)
            item.title = new_title

    def ft_in_title(
        self,
        item: Item,
        drop_feat: bool,
        keep_in_artist_field: bool,
        preserve_album_artist: bool,
        custom_words: list[str],
    ) -> bool:
        """Look for featured artists in the item's artist fields and move
        them to the title.

        Returns:
            True if the item has been modified. False otherwise.
        """
        artist = item.artist.strip()
        albumartist = item.albumartist.strip()

        # Check whether there is a featured artist on this track and the
        # artist field does not exactly match the album artist field. In
        # that case, we attempt to move the featured artist to the title.
        if preserve_album_artist and albumartist and artist == albumartist:
            return False

        _, featured = split_on_feat(artist, custom_words=custom_words)
        if not featured:
            return False

        self._log.info("{.filepath}", item)

        # Attempt to find the featured artist.
        feat_part = find_feat_part(artist, albumartist, custom_words)

        if not feat_part:
            self._log.info("no featuring artists found")
            return False

        # If we have a featuring artist, move it to the title.
        self.update_metadata(
            item, feat_part, drop_feat, keep_in_artist_field, custom_words
        )
        return True

    @staticmethod
    def find_bracket_position(
        title: str, keywords: list[str] | None = None
    ) -> int | None:
        normalized = (
            DEFAULT_BRACKET_KEYWORDS if keywords is None else tuple(keywords)
        )
        pattern = FtInTitlePlugin._bracket_position_pattern(normalized)
        m: re.Match[str] | None = pattern.search(title)
        return m.start() if m else None

    @staticmethod
    def insert_ft_into_title(
        title: str, feat_part: str, keywords: list[str] | None = None
    ) -> str:
        """Insert featured artist before the first bracket containing
        remix/edit keywords if present.
        """
        if (
            bracket_pos := FtInTitlePlugin.find_bracket_position(
                title, keywords
            )
        ) is not None:
            title_before = title[:bracket_pos].rstrip()
            title_after = title[bracket_pos:]
            return f"{title_before} {feat_part} {title_after}"
        return f"{title} {feat_part}"
