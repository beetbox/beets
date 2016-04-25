# -*- coding: utf-8 -*-
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

"""Update library's tags using MusicBrainz.
"""
from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
from beets import autotag, library, ui, util
from beets.autotag import hooks
from collections import defaultdict


def apply_item_changes(lib, item, move, pretend, write):
    """Store, move and write the item according to the arguments.
    """
    if not pretend:
        # Move the item if it's in the library.
        if move and lib.directory in util.ancestry(item.path):
            item.move(with_album=False)

        if write:
            item.try_write()
        item.store()


class MBSyncPlugin(BeetsPlugin):
    def __init__(self):
        super(MBSyncPlugin, self).__init__()

    def commands(self):
        cmd = ui.Subcommand('mbsync',
                            help=u'update metadata from musicbrainz')
        cmd.parser.add_option(
            u'-p', u'--pretend', action='store_true',
            help=u'show all changes but do nothing')
        cmd.parser.add_option(
            u'-m', u'--move', action='store_true', dest='move',
            help=u"move files in the library directory")
        cmd.parser.add_option(
            u'-M', u'--nomove', action='store_false', dest='move',
            help=u"don't move files in library")
        cmd.parser.add_option(
            u'-W', u'--nowrite', action='store_false',
            default=None, dest='write',
            help=u"don't write updated metadata to files")
        cmd.parser.add_format_option()
        cmd.func = self.func
        return [cmd]

    def func(self, lib, opts, args):
        """Command handler for the mbsync function.
        """
        move = ui.should_move(opts.move)
        pretend = opts.pretend
        write = ui.should_write(opts.write)
        query = ui.decargs(args)

        self.singletons(lib, query, move, pretend, write)
        self.albums(lib, query, move, pretend, write)

    def singletons(self, lib, query, move, pretend, write):
        """Retrieve and apply info from the autotagger for items matched by
        query.
        """
        for item in lib.items(query + [u'singleton:true']):
            item_formatted = format(item)
            if not item.mb_trackid:
                self._log.info(u'Skipping singleton with no mb_trackid: {0}',
                               item_formatted)
                continue

            # Get the MusicBrainz recording info.
            track_info = hooks.track_for_mbid(item.mb_trackid)
            if not track_info:
                self._log.info(u'Recording ID not found: {0} for track {0}',
                               item.mb_trackid,
                               item_formatted)
                continue

            # Apply.
            with lib.transaction():
                autotag.apply_item_metadata(item, track_info)
                apply_item_changes(lib, item, move, pretend, write)

    def albums(self, lib, query, move, pretend, write):
        """Retrieve and apply info from the autotagger for albums matched by
        query and their items.
        """
        # Process matching albums.
        for a in lib.albums(query):
            album_formatted = format(a)
            if not a.mb_albumid:
                self._log.info(u'Skipping album with no mb_albumid: {0}',
                               album_formatted)
                continue

            items = list(a.items())

            # Get the MusicBrainz album information.
            album_info = hooks.album_for_mbid(a.mb_albumid)
            if not album_info:
                self._log.info(u'Release ID {0} not found for album {1}',
                               a.mb_albumid,
                               album_formatted)
                continue

            # Map recording MBIDs to their information. Recordings can appear
            # multiple times on a release, so each MBID maps to a list of
            # TrackInfo objects.
            track_index = defaultdict(list)
            for track_info in album_info.tracks:
                track_index[track_info.track_id].append(track_info)

            # Construct a track mapping according to MBIDs. This should work
            # for albums that have missing or extra tracks. If there are
            # multiple copies of a recording, they are disambiguated using
            # their disc and track number.
            mapping = {}
            for item in items:
                candidates = track_index[item.mb_trackid]
                if len(candidates) == 1:
                    mapping[item] = candidates[0]
                else:
                    for c in candidates:
                        if (c.medium_index == item.track and
                                c.medium == item.disc):
                            mapping[item] = c
                            break

            # Apply.
            self._log.debug(u'applying changes to {}', album_formatted)
            with lib.transaction():
                autotag.apply_metadata(album_info, mapping)
                changed = False
                for item in items:
                    item_changed = ui.show_model_changes(item)
                    changed |= item_changed
                    if item_changed:
                        apply_item_changes(lib, item, move, pretend, write)

                if not changed:
                    # No change to any item.
                    continue

                if not pretend:
                    # Update album structure to reflect an item in it.
                    for key in library.Album.item_keys:
                        a[key] = items[0][key]
                    a.store()

                    # Move album art (and any inconsistent items).
                    if move and lib.directory in util.ancestry(items[0].path):
                        self._log.debug(u'moving album {0}', album_formatted)
                        a.move()
