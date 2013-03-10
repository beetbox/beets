"""Adds Discogs album search support to the
autotagger. Requires the discogs-client library.
"""
import string

from time import strptime

from beetsplug.abstract_search import AbstractSearchPlugin
from beets.autotag import hooks

import discogs_client
from discogs_client import Artist, Release, Search, DiscogsAPIError

discogs_client.user_agent = 'curl/7.28.0'

# Plugin structure and autotagging logic.

class DiscogsPlugin(AbstractSearchPlugin):
    def __init__(self):
        super(DiscogsPlugin, self).__init__()

    def _search(self, artist, album):
        super(DiscogsPlugin, self)._search(artist, album)
        try:
            albums = Search(artist + ' ' + album).results()[0:5]
            return filter(lambda album: isinstance(album, Release), albums)
        except DiscogsAPIError as e:
            if str(e).startswith('404'):
                return []
            else:
                raise e

    def _album_info(self, album):
        return hooks.AlbumInfo(
            album.title,
            None,
            self._artists_names(album.artists),
            None,
            map(self._track_info, album.tracklist)
        )

    def _track_info(self, track):
        disk_number, position = self._position(track['position'])

        return hooks.TrackInfo(
            track['title'],
            None,
            self._artists_names(track['artists']),
            None,
            self._duration(track['duration']),
            position,
            disk_number
        )

    def _artists_names(self, artists):
        filtered = filter(lambda artist: isinstance(artist, Artist), artists)
        names =  map(lambda artist: artist.name, filtered)

        return ' and '.join(names)

    def _position(self, position):
        try:
            original = position
            """Convert track position from u'1', u'2' or u'A', u'B' to 1, 2 etc"""
            position = position.encode('ascii').lower()         # Convert from unicode to lovercase ascii

            if not len(position):
                return 0, 0

            first    = position[0]

            if string.ascii_lowercase.find(first) != -1:
                number = ord(first) - 96

                if len(position) == 1:
                    replace = '%i'  % number                    # Letter is track number
                else:
                    replace = '%i-' % number                    # Letter is vinyl side

                position = position.replace(first, replace)

            if position.find('-') == -1:
                position = '1-' + position                      # If no disk number, set to 1

            result = map(int, position.split('-'))

            if len(result) == 2:
                return result
            else:
                return 0, 0
        except ValueError:
            return 0, 0

    def _duration(self, duration):
        try:
            duration = strptime(duration.encode('ascii'), '%M:%S')
        except ValueError:
            return 0
        else:
            return duration.tm_min * 60 + duration.tm_sec