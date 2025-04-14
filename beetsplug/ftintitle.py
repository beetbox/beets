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
from typing import TYPE_CHECKING

from beets import plugins, ui
from beets.util import displayable_path

if TYPE_CHECKING:
    from beets.importer import ImportSession, ImportTask
    from beets.library import Item


def split_on_feat(artist: str) -> tuple[str, str | None]:
    """Given an artist string, split the "main" artist from any artist
    on the right-hand side of a string like "feat". Return the main
    artist, which is always a string, and the featuring artist, which
    may be a string or None if none is present.
    """
    # split on the first "feat".
    regex = re.compile(plugins.feat_tokens(), re.IGNORECASE)
    parts = tuple(s.strip() for s in regex.split(artist, 1))
    if len(parts) == 1:
        return parts[0], None
    else:
        assert len(parts) == 2  # help mypy out
        return parts


def contains_feat(title: str) -> bool:
    """Determine whether the title contains a "featured" marker."""
    return bool(
        re.search(
            plugins.feat_tokens(for_artist=False),
            title,
            flags=re.IGNORECASE,
        )
    )


def find_feat_part(artist: str, albumartist: str) -> str | None:
    """Attempt to find featured artists in the item's artist fields and
    return the results. Returns None if no featured artist found.
    """
    # Look for the album artist in the artist field. If it's not
    # present, give up.
    albumartist_split = artist.split(albumartist, 1)
    if len(albumartist_split) <= 1:
        return None

    # If the last element of the split (the right-hand side of the
    # album artist) is nonempty, then it probably contains the
    # featured artist.
    elif albumartist_split[1] != "":
        # Extract the featured artist from the right-hand side.
        _, feat_part = split_on_feat(albumartist_split[1])
        return feat_part

    # Otherwise, if there's nothing on the right-hand side, look for a
    # featuring artist on the left-hand side.
    else:
        lhs, rhs = split_on_feat(albumartist_split[0])
        if lhs:
            return lhs

    return None


class FtInTitlePlugin(plugins.BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {
                "auto": True,
                "drop": False,
                "format": "feat. {0}",
                "keep_in_artist": False,
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
            write = ui.should_write()

            for item in lib.items(ui.decargs(args)):
                if self.ft_in_title(item, drop_feat, keep_in_artist_field):
                    item.store()
                    if write:
                        item.try_write()

        self._command.func = func
        return [self._command]

    def imported(self, session: ImportSession, task: ImportTask) -> None:
        """Import hook for moving featuring artist automatically."""
        drop_feat = self.config["drop"].get(bool)
        keep_in_artist_field = self.config["keep_in_artist"].get(bool)

        for item in task.imported_items():
            if self.ft_in_title(item, drop_feat, keep_in_artist_field):
                item.store()

    def update_metadata(
        self,
        item: Item,
        feat_part: str,
        drop_feat: bool,
        keep_in_artist_field: bool,
    ) -> None:
        """Choose how to add new artists to the title and set the new
        metadata. Also, print out messages about any changes that are made.
        If `drop_feat` is set, then do not add the artist to the title; just
        remove it from the artist field.
        """
        # In case the artist is kept, do not update the artist fields.
        if keep_in_artist_field:
            self._log.info(
                "artist: {0} (Not changing due to keep_in_artist)", item.artist
            )
        else:
            self._log.info("artist: {0} -> {1}", item.artist, item.albumartist)
            item.artist = item.albumartist

        if item.artist_sort:
            # Just strip the featured artist from the sort name.
            item.artist_sort, _ = split_on_feat(item.artist_sort)

        # Only update the title if it does not already contain a featured
        # artist and if we do not drop featuring information.
        if not drop_feat and not contains_feat(item.title):
            feat_format = self.config["format"].as_str()
            new_format = feat_format.format(feat_part)
            new_title = f"{item.title} {new_format}"
            self._log.info("title: {0} -> {1}", item.title, new_title)
            item.title = new_title

    def ft_in_title(
        self,
        item: Item,
        drop_feat: bool,
        keep_in_artist_field: bool,
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
        _, featured = split_on_feat(artist)
        if featured and albumartist != artist and albumartist:
            self._log.info("{}", displayable_path(item.path))

            feat_part = None

            # Attempt to find the featured artist.
            feat_part = find_feat_part(artist, albumartist)

            # If we have a featuring artist, move it to the title.
            if feat_part:
                self.update_metadata(
                    item, feat_part, drop_feat, keep_in_artist_field
                )
                return True
            else:
                self._log.info("no featuring artists found")
        return False
