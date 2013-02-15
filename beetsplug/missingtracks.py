# This file is not part of beets.
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

'''list or download missing items
'''
import os
import logging
import tempfile

import grooveshark

from beets import config
from beets.autotag import hooks
from beets.library import Item
from beets.mediafile import MediaFile
from beets.plugins import BeetsPlugin
from beets.ui import decargs, print_obj, Subcommand
from beets.util import mkdirall

plugin = 'missingtracks'
log = logging.getLogger('beets')
client = grooveshark.Client()
client.init()


def _missing(album, lib=None):
    '''Query MusicBrainz to determine items missing from `album`,
     caching them in `lib` to avoid further queries.
    '''
    item_paths = filter(None, map(lambda i: i.path, album.items()))
    item_mbids = map(lambda x: x.mb_trackid,
                     filter(lambda i: i.path is not None, album.items()))

    if len(item_paths) < album.tracktotal:
        # check for cached items (in library but with no associated file)
        missing = [i for i in album.items() if not i.path]
        if missing:
            for item in missing:
                log.debug('{0}: {1} is missing (cache hit)'
                          .format(plugin, item.title.encode('utf-8')))
                yield item
            return

        # fetch and cache missing items
        # items are stored in library without path field
        # this might break something, like the web plugin
        album_info = hooks._album_for_id(album.mb_albumid)
        for track_info in album_info.tracks:
            if track_info.track_id not in item_mbids:
                item = _item(track_info, album_info, album.id)
                log.debug('{0}: {1} is missing (caching)'
                          .format(plugin, item.title.encode('utf-8')))
                if lib:
                    lib.add(item)
                yield item


def _matches(songs, albums, artists):
    '''Given iterators of pygrooveshark `songs`, `albums`, and
    `artists`, return an iterator of any `song`s spanning a transitive
    closure over all three collections.
    '''
    # naive algorithm with O(n*m*p). must profile to check whether problematic
    # TODO: index everything in some data structure for O(n+m+p)
    for artist in artists:
        for album in albums:
            for song in songs:
                song_from_album = song.album.id == album.id
                song_from_artist = song.artist.id == artist.id
                album_from_artist = album.artist.id == artist.id
                if song_from_album and song_from_artist and album_from_artist:
                    log.debug('{0}: found {1}'.format(plugin,
                                                      unicode(song.name)))
                    yield song


def _item(track_info, album_info, album_id):
    '''Build and return `item` from `track_info` and `album info`
    objects. `item` is missing what fields cannot be obtained from
    MusicBrainz alone (encoder, rg_track_gain, rg_track_peak,
    rg_album_gain, rg_album_peak, original_year, original_month,
    original_day, length, bitrate, format, samplerate, bitdepth,
    channels, mtime.)
    '''
    t = track_info
    a = album_info

    return Item({'album_id': album_id,
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
                 'year':               a.year})


def _candidates(item):
    '''Given a track `item`, query grooveshark for matching songs,
    albums, and artists, and yield any matching `song`s.
    '''
    # the 3 calls are necessary because grooveshark's API does not
    # offer, to my knowledge, an advanced query syntax, so we query for
    # all 3 fields, and then try to filter songs with `_matches`
    songs = list(client.search(item.title, type=client.SONGS))
    albums = list(client.search(item.album, type=client.ALBUMS))
    artists = list(client.search(item.albumartist, type=client.ARTISTS))

    log.debug('{0}: got {1} potential songs'.format(plugin, len(songs)))
    log.debug('{0}: got {1} potential albums'.format(plugin, len(albums)))
    log.debug('{0}: got {1} potential artists'.format(plugin, len(artists)))

    for song in _matches(songs, albums, artists):
        yield song


def _download(song, directory=None):
    '''Download `song` to `directory`. Return `path`.
    '''
    if not directory:
        directory = tempfile.mkdtemp()
    path = os.path.join(directory, song.id)
    mkdirall(path)

    data = song.stream.data
    size = song.stream.size
    read = 0
    buff = 512 * 1024
    with open(path, 'wb') as f:
        while True:
            chunk = data.read(buff)
            if not chunk:
                break
            nbytes = len(chunk)
            read += nbytes
            f.write(chunk)
            log.debug('{0}: wrote {1}/{2} bytes to {3}'
                      .format(plugin, nbytes, buff, path))

        log.debug('{0}: wrote {1}/{2} bytes to {3}'
                  .format(plugin, read, size, path))

    return path


def _update(item, path):
    '''Update metadata to `item` based on MediaFile(`path`). Return
    modified `item`.
    '''
    mf = MediaFile(path)

    newpath = "{0}.{1}".format(path, mf.type)
    os.rename(path, newpath)
    log.debug('{0}: renamed {1} to {2}'.format(plugin,
                                               path,
                                               newpath))

    item.path = newpath
    item.bitdepth = mf.bitdepth
    item.bitrate = mf.bitrate
    item.channels = mf.channels
    item.encoder = mf.encoder
    item.format = mf.format
    item.length = mf.length
    item.original_day = mf.original_day
    item.original_month = mf.original_month
    item.original_year = mf.original_year
    item.rg_album_gain = mf.rg_album_gain
    item.rg_album_peak = mf.rg_album_peak
    item.rg_track_gain = mf.rg_track_gain
    item.rg_track_peak = mf.rg_track_peak
    item.samplerate = mf.samplerate

    return item


class MissingTracksPlugin(BeetsPlugin):
    '''Fetch tracks missing from albums from grooveshark.
    '''
    def __init__(self):
        super(MissingTracksPlugin, self).__init__()

        self.config.add({'download': False,
                         'move': False,
                         'format': None,
                         'tmpdir': None})

        self._command = Subcommand('missing',
                                   help=__doc__,
                                   aliases=['miss'])

        self._command.parser.add_option('-d', '--download', dest='download',
                                        action='store_true',
                                        help='download missing songs')

        self._command.parser.add_option('-m', '--move', dest='move',
                                        action='store_true',
                                        help='move new items to library')

        self._command.parser.add_option('-f', '--format', dest='format',
                                        action='store', type='string',
                                        help='print with custom FORMAT',
                                        metavar='FORMAT')

        self._command.parser.add_option('-t', '--tmpdir', dest='tmpdir',
                                        action='store', type='string',
                                        help='temp DIR to save songs',
                                        metavar='DIR')

    def commands(self):
        def _miss(lib, opts, args):
            self.config.set_args(opts)
            download = self.config['download'].get(bool)
            move = self.config['move'].get(bool)
            fmt = self.config['format'].get()
            tmpdir = self.config['tmpdir'].get()
            write = config['import']['write'].get(bool)

            for album in lib.albums(decargs(args)):
                for item in _missing(album, lib):
                    print_obj(item, lib, fmt=fmt)

                    if download:
                        for s in _candidates(item):
                            tmp = _download(s, tmpdir)
                            item = _update(item, tmp)
                            if move:
                                lib.move(item)
                                log.debug('{0}: moved item to {1}'
                                          .format(plugin, item.path))
                            if write:
                                item.write()
                                log.debug('{0}: wrote tags to {1}'
                                          .format(plugin, item.path))

        self._command.func = _miss
        return [self._command]
