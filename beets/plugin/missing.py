# This file is part of beets.
# Copyright 2013, Pedro Silva.
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

"""List missing tracks.
"""
import logging

from beets.autotag import hooks
from beets.library import Item
from beets.plugins import BeetsPlugin
from beets.ui import decargs, print_obj, Subcommand

PLUGIN = 'missing'
log = logging.getLogger('beets')


def _missing_count(album):
    """Return number of missing items in `album`.
    """
    return (album.tracktotal or 0) - len(album.items())


def _missing(album):
    """Query MusicBrainz to determine items missing from `album`.
    """
    item_mbids = map(lambda x: x.mb_trackid, album.items())

    if len([i for i in album.items()]) < album.tracktotal:
        # fetch missing items
        # TODO: Implement caching that without breaking other stuff
        album_info = hooks.album_for_mbid(album.mb_albumid)
        for track_info in getattr(album_info, 'tracks', []):
            if track_info.track_id not in item_mbids:
                item = _item(track_info, album_info, album.id)
                log.debug('{0}: track {1} in album {2}'
                          .format(PLUGIN,
                                  track_info.track_id,
                                  album_info.album_id))
                yield item


def _item(track_info, album_info, album_id):
    """Build and return `item` from `track_info` and `album info`
    objects. `item` is missing what fields cannot be obtained from
    MusicBrainz alone (encoder, rg_track_gain, rg_track_peak,
    rg_album_gain, rg_album_peak, original_year, original_month,
    original_day, length, bitrate, format, samplerate, bitdepth,
    channels, mtime.)
    """
    t = track_info
    a = album_info

    return Item(**{
        'album_id':           album_id,
        'album':              a.album,
        'albumartist':        a.artist,
        'albumartist_credit': a.artist_credit,
        'albumartist_sort':   a.artist_sort,
        'albumdisambig':      a.albumdisambig,
        'albumstatus':        a.albumstatus,
        'albumtype':          a.albumtype,
        'artist':             t.artist,
        'artist_credit':      t.artist_credit,
        'artist_sort':        t.artist_sort,
        'asin':               a.asin,
        'catalognum':         a.catalognum,
        'comp':               a.va,
        'country':            a.country,
        'day':                a.day,
        'disc':               t.medium,
        'disctitle':          t.disctitle,
        'disctotal':          a.mediums,
        'label':              a.label,
        'language':           a.language,
        'length':             t.length,
        'mb_albumid':         a.album_id,
        'mb_artistid':        t.artist_id,
        'mb_releasegroupid':  a.releasegroup_id,
        'mb_trackid':         t.track_id,
        'media':              a.media,
        'month':              a.month,
        'script':             a.script,
        'title':              t.title,
        'track':              t.index,
        'tracktotal':         len(a.tracks),
        'year':               a.year,
    })


class MissingPlugin(BeetsPlugin):
    """List missing tracks
    """
    def __init__(self):
        super(MissingPlugin, self).__init__()

        self.config.add({
            'format': None,
            'count': False,
            'total': False,
        })

        self.album_template_fields['missing'] = _missing_count

        self._command = Subcommand('missing',
                                   help=__doc__,
                                   aliases=['miss'])

        self._command.parser.add_option('-f', '--format', dest='format',
                                        action='store', type='string',
                                        help='print with custom FORMAT',
                                        metavar='FORMAT')

        self._command.parser.add_option('-c', '--count', dest='count',
                                        action='store_true',
                                        help='count missing tracks per album')

        self._command.parser.add_option('-t', '--total', dest='total',
                                        action='store_true',
                                        help='count total of missing tracks')

    def commands(self):
        def _miss(lib, opts, args):
            self.config.set_args(opts)
            fmt = self.config['format'].get()
            count = self.config['count'].get()
            total = self.config['total'].get()

            albums = lib.albums(decargs(args))
            if total:
                print(sum([_missing_count(a) for a in albums]))
                return

            # Default format string for count mode.
            if count and not fmt:
                fmt = '$albumartist - $album: $missing'

            for album in albums:
                if count:
                    missing = _missing_count(album)
                    if missing:
                        print_obj(album, lib, fmt=fmt)

                else:
                    for item in _missing(album):
                        print_obj(item, lib, fmt=fmt)

        self._command.func = _miss
        return [self._command]
