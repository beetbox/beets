# This file is not part of beets.
# Copyright 2013, Pedro.
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

"""Fetch tracks missing from albums from grooveshark.
"""
import grooveshark

from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.autotag import hooks

client = grooveshark.Client()
client.init()

def _missing(album):
    """Fetch and return items missing from album"""
    item_mbids = map(lambda i: i.mb_trackid, album.items())
    item_total = len(item_mbids)

    if item_total < album.tracktotal:
        album_info = hooks._album_for_id(album.mb_albumid)

        for track_info in album_info.tracks:
            if track_info.track_id not in item_mbids:
                yield track_info


def _match(songs, albums, artists):
    songs_dict = map(lambda x: x.export(), songs)
    albums_dict = map(lambda x: x.export(), albums)
    artists_dict = map(lambda x: x.export(), artists)

    for artist in artists_dict:
        for album in albums_dict:
            for song in songs_dict:
                album_match = song['album_id'] == album['id']
                artist_match = album['artist_id'] == artist['id']
                if album_match and artist_match:
                    yield grooveshark.Song.from_export(song,
                                                       client.connection)


def _download(track_info, album):
    album_info = hooks._album_for_id(album.mb_albumid)
    songs = client.search(track_info.title, type=client.SONGS)
    albums = client.search(album_info.album, type=client.ALBUMS)
    artists = client.search(track_info.artist, type=client.ARTISTS)

    for song in (_match(songs, albums, artists)):
        with open("/tmp/%s.mp3" % unicode(song), 'wb') as f:
            f.write(song.stream.data.read())
            return song


class GroovesharkPlugin(BeetsPlugin):
    """Fetch tracks missing from albums from grooveshark.
    """
    def __init__(self):
        super(GroovesharkPlugin, self).__init__()
        self._command = Subcommand('fetchgroove',
                                   help=__doc__,
                                   aliases=['fetch'])

    def commands(self):
        def _fetch(lib, opts, args):
            for album in lib.albums():
                print [_download(i, album) for i in _missing(album)]

        self._command.func = _fetch
        return [self._command]
