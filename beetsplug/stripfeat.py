# This file is part of beets.
# Copyright 2025, Austin Tinkel, <github.com/ARTINKEL/beets-plugin-stripfeat>
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

"""Splits featured artist by delimiter."""

import re

from beets import plugins, ui
from beets.importer import ImportSession, ImportTask
from beets.library import Item


def artist_contains_feat_token(artist) -> bool:
    return (
        re.search(plugins.feat_tokens(), artist, flags=re.IGNORECASE)
        is not None
    )


def convert_feat_to_delimiter(artist: str, delimiter: str) -> str:
    # split on the first "feat"
    regex_result = re.compile(plugins.feat_tokens(), re.IGNORECASE)
    regex_groups = regex_result.split(artist)
    split_artist = regex_groups[0].strip() + delimiter + regex_groups[1].strip()

    return split_artist


class StripFeatPlugin(plugins.BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {"auto": True, "delimiter": ";", "strip_from_album_artist": False}
        )

        self._command = ui.Subcommand(
            "stripfeat", help="convert feat. in artist name to delimiter"
        )

        self._command.parser.add_option(
            "-a",
            "--albumartist",
            dest="strip_from_album_artist",
            action="store_true",
            default=None,
            help="convert feat. in albumartist name to delimiter as well",
        )

        if self.config["auto"]:
            self.import_stages = [self.imported]

    def commands(self) -> list[ui.Subcommand]:
        def func(lib, opts, args):
            self.config.set_args(opts)
            delimiter = self.config["delimiter"].as_str()
            strip_from_album_artist = self.config[
                "strip_from_album_artist"
            ].get(bool)
            write = ui.should_write()

            for item in lib.items(args):
                if self.strip_feat(item, delimiter, strip_from_album_artist):
                    item.store()
                    if write:
                        item.try_write()

        self._command.func = func
        return [self._command]

    def imported(self, session: ImportSession, task: ImportTask) -> None:
        strip_from_album_artist = self.config["strip_from_album_artist"].get(
            bool
        )
        delimiter = self.config["delimiter"].as_str()

        for item in task.imported_items():
            if self.strip_feat(item, delimiter, strip_from_album_artist):
                item.store()

    def strip_feat(
        self, item: Item, delimiter: str, strip_from_album_artist: bool
    ) -> bool:
        artist = item.artist.strip()

        if not artist_contains_feat_token(artist):
            self._log.info("no featuring artist in artist")
            return False

        if strip_from_album_artist:
            albumartist = item.albumartist.strip()
            if not artist_contains_feat_token(albumartist):
                self._log.info("no featuring artist in albumartist")
            item.albumartist = convert_feat_to_delimiter(albumartist, delimiter)
            self._log.info("Changed " + albumartist + " to " + item.albumartist)

        item.artist = convert_feat_to_delimiter(artist, delimiter)
        self._log.info("Changed " + artist + " to " + item.artist)
        return True
