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

"""Determine which tracks are missing from the library, and either list
them or download and import them using the fetch and miss commands.
"""
import logging

import grooveshark

from beets.autotag import hooks
from beets.library import Item
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand

log = logging.getLogger("beets")
client = grooveshark.Client()
client.init()


def _missing(album, lib=None):
    """Fetch from Musicbrainz and return any (track, album) info missing
    from album.
    """
    item_paths = map(lambda i: i.path, album.items())
    item_mbids = map(lambda i: i.mb_trackid, album.items())
    item_total = len(filter(None, item_paths))

    if item_total < album.tracktotal:
        missing = [i for i in album.items() if not i.path]
        if missing:
            for item in missing:
                log.info("{0} is missing but cached".format(item.id))
                yield item
            return

        album_info = hooks._album_for_id(album.mb_albumid)
        for track_info in album_info.tracks:
            if track_info.track_id not in item_mbids:
                item = _item(track_info, album_info, album.id)
                log.warn("{0} is missing and uncached".format(item.id))
                if lib:
                    lib.add(item)
                yield item


def _matches(songs, albums, artists):
    """Given iterators of pygrooveshark songs, albums, and artists,
    return an iterator of any songs spanning a transitive closure over
    all three collections.
    """
    ### FIXME: the commented stuff uses an internal dictionary, and
    ### provides more matches, for example for tracks prefixed by
    ### numbers, etc.  The currently uncommented method appears to only
    ### do exact string matches.  Have to understand why.

    # songs_dict = map(lambda x: x.export(), songs)
    # albums_dict = map(lambda x: x.export(), albums)
    # artists_dict = map(lambda x: x.export(), artists)
    # for artist in artists_dict:
    #     for album in albums_dict:
    #         for song in songs_dict:
    #             song_from_album = song['album_id'] == album['id']
    #             song_from_artist = song['artist_id'] == artist['id']
    #             album_from_artist = album['artist_id'] == artist['id']
    #             if song_from_album and song_from_artist and album_from_artist:
    #                yield grooveshark.Song.from_export(song, client.connection)

    for artist in artists:
        for album in albums:
            for song in songs:
                song_from_album = song.album.id == album.id
                song_from_artist = song.artist.id == artist.id
                album_from_artist = album.artist.id == artist.id
                if song_from_album and song_from_artist and album_from_artist:
                    yield song


def _item(track_info, album_info, album_id):
    """Build a library Item from track and album info objects.
    """
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
    """Given a track item, query grooveshark for matching songs, albums,
    and artists, and yield any matching songs.
    """
    songs = client.search(item.title, type=client.SONGS)
    albums = client.search(item.album, type=client.ALBUMS)
    artists = client.search(item.albumartist, type=client.ARTISTS)

    for song in _matches(songs, albums, artists):
        yield song


def _download(song):
    """Download and return song.
    """
    return song.stream.data.read()


class GroovesharkPlugin(BeetsPlugin):
    """Fetch tracks missing from albums from grooveshark.
    """
    def __init__(self):
        super(GroovesharkPlugin, self).__init__()
        self._commands = [Subcommand('fetchgroove',
                                     help=__doc__,
                                     aliases=['fetch']),
                          Subcommand('missing',
                                     help=__doc__,
                                     aliases=['miss'])]

    def commands(self):
        def _fetch(lib, opts, args):
            for album in lib.albums():
                for item in _missing(album, lib):
                    print [unicode(i.name) for i in _candidates(item)]

        def _miss(lib, opts, args):
            for album in lib.albums():
                for item in _missing(album, lib):
                    print "%s - %s - %s" % (item.albumartist,
                                            item.album, item.title)

        self._commands[0].func = _fetch
        self._commands[1].func = _miss
        return self._commands
