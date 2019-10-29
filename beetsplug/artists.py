# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2019, Guilherme Danno.
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

import re
import musicbrainzngs

musicbrainzngs.set_useragent('beets plugin', '0.0.1', '')

MBID_REGEX = r"(\d|\w){8}-(\d|\w){4}-(\d|\w){4}-(\d|\w){4}-(\d|\w){12}"


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

def get_credit(data):
    return getattr(data, 'artist-credit', [])[0::2]

def get_release(mb_album_id):
    rels = ['artists', 'recordings', 'artist-credits']
    r = musicbrainzngs.get_release_by_id(mb_album_id, rels)

    return r['release']

class MBArtistsPlugin(BeetsPlugin):
    def __init__(self):
        super(MBArtistsPlugin, self).__init__()

        self.config.add({
            'auto': True,
            'force': True,
            'mbid_separator': '/',
            'artist': {
                'separator': '; ',
            }
        })

        # if self.config['auto']:
        #     self.import_stages = [self.imported]

    def commands(self):
        def func(lib, opts, args):
            """
            Command handler for the mbsync function.
            """
            move = ui.should_move(opts.move)
            pretend = opts.pretend
            write = ui.should_write(opts.write)
            query = ui.decargs(args)

            self.albums(lib, query, move, pretend, write)

        cmd = ui.Subcommand('artists',
            help=u'Multiple artists from MusicBrainz')
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
        cmd.func = func
        return [cmd]
    def is_mb_release(self, a):
        if not a.mb_albumid:
            self._log.info(u'Skipping album with no mb_albumid: {0}', format(a))
            return False

        if not re.match(MBID_REGEX, a.mb_albumid):
            self._log.info(u'Skipping album with invalid mb_albumid: {0}', format(a))
            return False

        return True

    def imported(self, session, task):
        for item in task.imported_items():
            self.update_data(item)
            item.store()

    def update_data(self, a):
        if not self.is_mb_release(a):
            return False

        r = get_release(a.mb_albumid)
        SEP = self.config['artist']['separator'].get(str)
        a.albumartist = SEP.join(a['artist']['name'] for a in r['artist-credit'][0::2])
        mappings = defaultdict(list)

        for medium in r['medium-list']:
            for track in medium['track-list']:
                mappings[track['id']].append({
                    'disc': medium['position'],
                    'track': track['number'],
                    'mb_artistid': '/'.join(a['artist']['id'] for a in track['artist-credit'][0::2]),
                    'artist': SEP.join(a['artist']['name'] for a in track['artist-credit'][0::2]),
                })
        print(f'mappings: {mappings}', a['mb_releasetrackid'])
        if mappings[a['mb_releasetrackid']]:
            choices = mappings[a['mb_releasetrackid']]
            if len(choices) == 1:
                a['artist'] = choices[0]['artist']
                a['mb_artistid'] = choices[0]['mb_artistid']
                ui.show_model_changes(a)
                a.store()

    def albums(self, lib, query, move, pretend, write):
        """Retrieve and apply info from the autotagger for albums matched by
        query and their items.
        """
        # Process matching albums.
        for a in lib.albums(query):
            if not self.is_mb_release(a):
                continue

            # Get the MusicBrainz album information.
            album_info = hooks.album_for_mbid(a.mb_albumid)
            if not album_info:
                self._log.info(u'Release ID {0} not found for album {1}',
                               a.mb_albumid,
                               format(a))
                continue

            rels = ['artists', 'recordings', 'artist-credits']
            r = musicbrainzngs.get_release_by_id(a.mb_albumid, rels)
            SEP = self.config['artist']['separator'].get(str)
            a.albumartist = SEP.join(a['artist']['name'] for a in r['release']['artist-credit'][0::2])

            mappings = defaultdict(list)

            for medium in r['release']['medium-list']:
                for track in medium['track-list']:
                    mappings[track['id']].append({
                        'disc': medium['position'],
                        'track': track['number'],
                        'mb_artistid': self.config['mbid_separator'].get().join(a['artist']['id'] for a in track['artist-credit'][0::2]),
                        'artist': SEP.join(a['artist']['name'] for a in track['artist-credit'][0::2]),
                    })

            items = list(a.items())
            for item in items:
                if mappings[item.mb_releasetrackid]:
                    choices = mappings[item.mb_releasetrackid]
                    if len(choices) == 1:
                        item['artist'] = choices[0]['artist']
                        item['mb_artistid'] = choices[0]['mb_artistid']
                        ui.show_model_changes(item)
                        item.store()
                    else:
                        print(item)
                        print(choices)
                        print()


            a.store()

