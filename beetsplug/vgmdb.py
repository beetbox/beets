# This file is part of beets.
# Copyright 2021, Eldarock.
# Copyright 2022, JojoXD.
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

"""Adds VGMdb search support to Beets
"""

from beets.autotag.hooks import AlbumInfo, TrackInfo, Distance, item_candidates
from beets.dbcore.types import Id
from beets.plugins import BeetsPlugin
import json
import requests
import re


class VGMdbPlugin(BeetsPlugin):

    def __init__(self):
        super().__init__()
        self.config.add({
            'source_weight': 1.0,
            'lang-priority': ['en', 'ja-latn', 'ja'],
            'prefer_original': True  # Only for Attack on Titan soundtracks
        })
        self._log.debug('Querying VGMdb')
        self.source_weight = self.config['source_weight'].as_number()
        self.lang = self.config['lang-priority'].as_str_seq()
        self.prefer_original = self.config['prefer_original'].get(bool)

    def lang_select(self, d):
        """Returns the value matching lang-priority or the firt one if not found
        """
        if not isinstance(d, dict): return d
        for lang in self.lang:
            if lang in d:
                return d[lang]
        return list(d.values())[0]

    def lang_select_tracks(self, d):
        """Same as above for tracks
        """
        match = {'en': ['English',
                        'English (from furigana)',
                        'English (NA localization + Additional Translations)',
                        'English (EU localisation + Additional Translations)'],
                 'ja-latn': ['Romaji'],
                 'ja': ['Japanese', 'Japanese (furigana)']
                 }

        if not isinstance(d, dict): return d
        if self.prefer_original and 'Original' in d: return d['Original']
        for lang in self.lang:
            if lang in match:
                for language in match[lang]:
                    if language in d:
                        return d[language]
        return list(d.values())[0]

    def album_distance(self, items, album_info, mapping):
        """Returns the album distance.
        """
        dist = Distance()
        if album_info.data_source == 'VGMdb':
            dist.add('source', self.source_weight)
        return dist

    def candidates(self, items, artist, album, va_likely, extra_tags=None):
        """Returns a list of AlbumInfo objects for VGMdb search results
        matching an album and artist (if not various).
        """
        if va_likely:
            query = album
        else:
            query = '%s %s' % (artist, album)
        try:
            ret = self.get_albums(query, va_likely)
            for x in ret:
               self._debug('Found album: %s ; id: %s ; artist: %s' % (x.album, x.album_id, x.artist))
            return ret
        except:
            self._log.debug('VGMdb Search Error: (query: %s)' % query)
            return []

    def album_for_id(self, album_id):
        """Fetches an album by its VGMdb ID and returns an AlbumInfo object
        or None if the album is not found.
        """
        self._log.debug('Querying VGMdb for release %s' % str(album_id))

        # Get from VGMdb
        r = requests.get('http://vgmdb.info/album/%s?format=json' % str(album_id))

        # Decode Response's content
        try:
            item = r.json()
        except requests.JSONDecodeError:
            self._log.debug('VGMdb JSON Decode Error: (id: %s)' % album_id)
            return None

        return self.get_album_info(item, False)

    def get_albums(self, query, va_likely):
        """Returns a list of AlbumInfo objects for a VGMdb search query.
        """
        # Strip non-word characters from query. Things like "!" and "-" can
        # cause a query to return no results, even if they match the artist or
        # album title. Use `re.UNICODE` flag to avoid stripping non-english
        # word characters.
        query = re.sub(r'(?u)\W+', ' ', query)
        # Strip medium information from query, Things like "CD1" and "disk 1"
        # can also negate an otherwise positive result.
        query = re.sub(r'(?i)\b(CD|disc)\s*\d+', '', query)

        # Query VGMdb
        r = requests.get('http://vgmdb.info/search/albums/%s?format=json' % query)
        albums = []

        # Decode Response's content
        try:
            items = r.json()
        except:
            self._log.debug('VGMdb JSON Decode Error: (query: %s)' % query)
            return albums

        # Break up and get search results
        for item in items["results"]["albums"]:
            album_id = str(self.decode(item["link"][6:]))
            albums.append(self.album_for_id(album_id))
            if len(albums) >= 5:
                break
        self._log.debug('get_albums Querying VGMdb for release %s' % str(query))
        return albums

    # TODO(JojoXD): Check why this is needed
    def decode(self, val, codec='utf8'):
        """Ensure that all string are coded to Unicode.
        """
        if isinstance(val, str):
            b = val.encode()
            return b.decode(codec, 'ignore')

    def get_album_info(self, item, va_likely):
        """Convert json data into a format beets can read
        """

        album_name = self.lang_select(item["names"])

        album_id = item["link"][6:]
        country = None
        catalognum = item["catalog"]

        # Get Artist information
        # if "performers" in item and len(item["performers"]) > 0:
        #    artist_type = "performers"
        # else:
        #    artist_type = "composers"
        artist_type = "composers"
        artist_credit_list = []
        for artist_credit in item[artist_type]:
            artist_credit_list.append(artist_credit['names']['en'])

        arrangers_list = []
        for arranger in item['arrangers']:
            arrangers_list.append(artist_credit['names']['en'])

        games = []
        for game in item['products']:
            games.append(game['names']['en'])

        artist = self.lang_select(item[artist_type][0]["names"])
        if "link" in item[artist_type][0]:
            artist_id = item[artist_type][0]["link"][7:]
        else:
            artist_id = None

        # Get Track metadata
        Tracks = []
        total_index = 0
        for disc_index, disc in enumerate(item["discs"]):
            for track_index, track in enumerate(disc["tracks"]):
                total_index += 1

                title = self.lang_select_tracks(track["names"])
                title_alt = ','.join(list(track["names"].values()))

                index = total_index

                if track["track_length"] == "Unknown":
                    length = 0
                else:
                    length = track["track_length"].split(":")
                    length = (float(length[0]) * 60) + float(length[1])

                media = item["media_format"]
                medium = disc_index
                medium_index = track_index
                new_track = TrackInfo(
                    title,
                    title_alt=title_alt,
                    track_id=int(index),
                    length=float(length),
                    index=int(index),
                    arranger=arrangers_list,
                    medium=int(medium),
                    medium_index=int(medium_index),
                    medium_total=item["discs"].count
                )
                Tracks.append(new_track)

        # Format Album release date
        release_date = item["release_date"].split("-")
        year = release_date[0]
        month = release_date[1]
        day = release_date[2]

        mediums = len(item["discs"])
        media = item["media_format"]
        if (len(games) == 1):
            game = games[0]
        else:
            game = 'Compilations'

        data_url = item["vgmdb_link"]

        return AlbumInfo(album=album_name,
                         vgmdb_album_id=int(album_id),
                         album_id=int(album_id),
                         artist=artist,
                         vgmdb_artist_id=self.decode(artist_id),
                         artist_id=self.decode(artist_id),
                         artist_credit=artist_credit_list,
                         tracks=Tracks,
                         asin=None,
                         albumtype=None,
                         va=False,
                         year=int(year),
                         month=int(month),
                         day=int(day),
                         vgmdb_game=game,
                         mediums=int(mediums),
                         media=self.decode(media),
                         data_source=self.decode('VGMdb'),
                         data_url=self.decode(data_url),
                         country=self.decode(country),
                         catalognum=self.decode(catalognum)
                         )
