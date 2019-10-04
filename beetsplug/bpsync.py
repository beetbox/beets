# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2019, Rahul Ahuja.
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

from .beatport import BeatportPlugin


class BPSyncPlugin(BeetsPlugin):
    def __init__(self):
        super(BPSyncPlugin, self).__init__()
        self.beatport_plugin = BeatportPlugin()
        self.beatport_plugin.setup()

    def commands(self):
        cmd = ui.Subcommand('bpsync', help=u'update metadata from Beatport')
        cmd.parser.add_option(
            u'-p',
            u'--pretend',
            action='store_true',
            help=u'show all changes but do nothing',
        )
        cmd.parser.add_option(
            u'-m',
            u'--move',
            action='store_true',
            dest='move',
            help=u"move files in the library directory",
        )
        cmd.parser.add_option(
            u'-M',
            u'--nomove',
            action='store_false',
            dest='move',
            help=u"don't move files in library",
        )
        cmd.parser.add_option(
            u'-W',
            u'--nowrite',
            action='store_false',
            default=None,
            dest='write',
            help=u"don't write updated metadata to files",
        )
        cmd.parser.add_format_option()
        cmd.func = self.func
        return [cmd]

    def func(self, lib, opts, args):
        """Command handler for the bpsync function.
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
            if not item.mb_trackid:
                self._log.info(
                    u'Skipping singleton with no mb_trackid: {}', item
                )
                continue

            if not self.is_beatport_track(item):
                self._log.info(
                    u'Skipping non-{} singleton: {}',
                    self.beatport_plugin.data_source,
                    item,
                )
                continue

            # Apply.
            track_info = self.beatport_plugin.track_for_id(item.mb_trackid)
            with lib.transaction():
                autotag.apply_item_metadata(item, track_info)
                library.apply_item_changes(lib, item, move, pretend, write)

    @staticmethod
    def is_beatport_track(track):
        return (
            track.get('data_source') == BeatportPlugin.data_source
            and track.mb_trackid.isnumeric()
        )

    def get_album_tracks(self, album):
        if not album.mb_albumid:
            self._log.info(u'Skipping album with no mb_albumid: {}', album)
            return False
        if not album.mb_albumid.isnumeric():
            self._log.info(
                u'Skipping album with invalid {} ID: {}',
                self.beatport_plugin.data_source,
                album,
            )
            return False
        tracks = list(album.items())
        if album.get('data_source') == self.beatport_plugin.data_source:
            return tracks
        if not all(self.is_beatport_track(track) for track in tracks):
            self._log.info(
                u'Skipping non-{} release: {}',
                self.beatport_plugin.data_source,
                album,
            )
            return False
        return tracks

    def albums(self, lib, query, move, pretend, write):
        """Retrieve and apply info from the autotagger for albums matched by
        query and their items.
        """
        # Process matching albums.
        for album in lib.albums(query):
            # Do we have a valid Beatport album?
            items = self.get_album_tracks(album)
            if not items:
                continue

            # Get the Beatport album information.
            album_info = self.beatport_plugin.album_for_id(album.mb_albumid)
            if not album_info:
                self._log.info(
                    u'Release ID {} not found for album {}',
                    album.mb_albumid,
                    album,
                )
                continue

            beatport_track_id_to_info = {
                track.track_id: track for track in album_info.tracks
            }
            library_track_id_to_item = {
                int(item.mb_trackid): item for item in items
            }
            item_to_info_mapping = {
                library_track_id_to_item[track_id]: track_info
                for track_id, track_info in beatport_track_id_to_info.items()
            }

            self._log.info(u'applying changes to {}', album)
            with lib.transaction():
                autotag.apply_metadata(album_info, item_to_info_mapping)
                changed = False
                # Find any changed item to apply Beatport changes to album.
                any_changed_item = items[0]
                for item in items:
                    item_changed = ui.show_model_changes(item)
                    changed |= item_changed
                    if item_changed:
                        any_changed_item = item
                        library.apply_item_changes(
                            lib, item, move, pretend, write
                        )

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
                        self._log.debug(u'moving album {}', album)
                        album.move()
