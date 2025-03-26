# This file is part of beets.
# Copyright 2016, Jakob Schnitzer.
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

"""Synchronise library metadata with metadata source backends."""

from collections import defaultdict

from beets import autotag, library, metadata_plugins, ui, util
from beets.plugins import BeetsPlugin, apply_item_changes


class MBSyncPlugin(BeetsPlugin):
    def __init__(self):
        super().__init__()

    def commands(self):
        cmd = ui.Subcommand("mbsync", help="update metadata from musicbrainz")
        cmd.parser.add_option(
            "-p",
            "--pretend",
            action="store_true",
            help="show all changes but do nothing",
        )
        cmd.parser.add_option(
            "-m",
            "--move",
            action="store_true",
            dest="move",
            help="move files in the library directory",
        )
        cmd.parser.add_option(
            "-M",
            "--nomove",
            action="store_false",
            dest="move",
            help="don't move files in library",
        )
        cmd.parser.add_option(
            "-W",
            "--nowrite",
            action="store_false",
            default=None,
            dest="write",
            help="don't write updated metadata to files",
        )
        cmd.parser.add_format_option()
        cmd.func = self.func
        return [cmd]

    def func(self, lib, opts, args):
        """Command handler for the mbsync function."""
        move = ui.should_move(opts.move)
        pretend = opts.pretend
        write = ui.should_write(opts.write)

        self.singletons(lib, args, move, pretend, write)
        self.albums(lib, args, move, pretend, write)

    def singletons(self, lib, query, move, pretend, write):
        """Retrieve and apply info from the autotagger for items matched by
        query.
        """
        for item in ui.iprogress_bar(
            lib.items(query + ["singleton:true"]),
            desc="Syncing singletons",
            unit="singletons",
        ):
            if not item.mb_trackid:
                self._log.info(
                    "Skipping singleton with no mb_trackid: {}", item
                )
                continue

            if not (
                track_info := metadata_plugins.track_for_id(item.mb_trackid)
            ):
                self._log.info(
                    "Recording ID not found: {0.mb_trackid} for track {0}", item
                )
                continue

            # Apply.
            with lib.transaction():
                autotag.apply_item_metadata(item, track_info)
                apply_item_changes(lib, item, move, pretend, write)

    def albums(self, lib, query, move, pretend, write):
        """Retrieve and apply info from the autotagger for albums matched by
        query and their items.
        """
        for album in ui.iprogress_bar(
            lib.albums(query),
            desc="Syncing albums",
            unit="albums",
        ):
            if not album.mb_albumid:
                self._log.info("Skipping album with no mb_albumid: {}", album)
                continue

            if not (
                album_info := metadata_plugins.album_for_id(album.mb_albumid)
            ):
                self._log.info(
                    "Release ID {0.mb_albumid} not found for album {0}", album
                )
                continue

            # Map release track and recording MBIDs to their information.
            # Recordings can appear multiple times on a release, so each MBID
            # maps to a list of TrackInfo objects.
            releasetrack_index = {}
            track_index = defaultdict(list)
            for track_info in album_info.tracks:
                releasetrack_index[track_info.release_track_id] = track_info
                track_index[track_info.track_id].append(track_info)

            # Construct a track mapping according to MBIDs (release track MBIDs
            # first, if available, and recording MBIDs otherwise). This should
            # work for albums that have missing or extra tracks.
            mapping = {}
            items = list(album.items())
            for item in items:
                if (
                    item.mb_releasetrackid
                    and item.mb_releasetrackid in releasetrack_index
                ):
                    mapping[item] = releasetrack_index[item.mb_releasetrackid]
                else:
                    candidates = track_index[item.mb_trackid]
                    if len(candidates) == 1:
                        mapping[item] = candidates[0]
                    else:
                        # If there are multiple copies of a recording, they are
                        # disambiguated using their disc and track number.
                        for c in candidates:
                            if (
                                c.medium_index == item.track
                                and c.medium == item.disc
                            ):
                                mapping[item] = c
                                break

            # Apply.
            self._log.debug("applying changes to {}", album)
            with lib.transaction():
                autotag.apply_metadata(album_info, mapping)
                changed = False
                # Find any changed item to apply changes to album.
                any_changed_item = items[0]
                for item in items:
                    item_changed = ui.show_model_changes(item)
                    changed |= item_changed
                    if item_changed:
                        any_changed_item = item
                        apply_item_changes(lib, item, move, pretend, write)

                if not changed:
                    # No change to any item.
                    continue

                if not pretend:
                    # Update album structure to reflect an item in it.
                    for key in library.Album.item_keys:
                        album[key] = any_changed_item[key]
                    album.store()

                    # Move album art (and any inconsistent items).
                    if move and lib.directory in util.ancestry(items[0].path):
                        self._log.debug("moving album {}", album)
                        album.move()
