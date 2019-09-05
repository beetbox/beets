# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Facilities for automatically determining files' correct metadata.
"""

from __future__ import division, absolute_import, print_function

import re
from abc import abstractmethod, abstractproperty

from beets import logging
from beets import config
from beets.plugins import BeetsPlugin

# Parts of external interface.
from .hooks import (
    AlbumInfo,
    TrackInfo,
    AlbumMatch,
    TrackMatch,
    Distance,
)  # noqa
from .match import tag_item, tag_album, Proposal  # noqa
from .match import Recommendation  # noqa

# Global logger.
log = logging.getLogger('beets')


# Additional utilities for the main interface.


def apply_item_metadata(item, track_info):
    """Set an item's metadata from its matched TrackInfo object.
    """
    item.artist = track_info.artist
    item.artist_sort = track_info.artist_sort
    item.artist_credit = track_info.artist_credit
    item.title = track_info.title
    item.mb_trackid = track_info.track_id
    item.mb_releasetrackid = track_info.release_track_id
    if track_info.artist_id:
        item.mb_artistid = track_info.artist_id
    if track_info.data_source:
        item.data_source = track_info.data_source

    if track_info.lyricist is not None:
        item.lyricist = track_info.lyricist
    if track_info.composer is not None:
        item.composer = track_info.composer
    if track_info.composer_sort is not None:
        item.composer_sort = track_info.composer_sort
    if track_info.arranger is not None:
        item.arranger = track_info.arranger
    if track_info.work is not None:
        item.work = track_info.work
    if track_info.mb_workid is not None:
        item.mb_workid = track_info.mb_workid
    if track_info.work_disambig is not None:
        item.work_disambig = track_info.work_disambig

    # At the moment, the other metadata is left intact (including album
    # and track number). Perhaps these should be emptied?


def apply_metadata(album_info, mapping):
    """Set the items' metadata to match an AlbumInfo object using a
    mapping from Items to TrackInfo objects.
    """
    for item, track_info in mapping.items():
        # Artist or artist credit.
        if config['artist_credit']:
            item.artist = (
                track_info.artist_credit
                or track_info.artist
                or album_info.artist_credit
                or album_info.artist
            )
            item.albumartist = album_info.artist_credit or album_info.artist
        else:
            item.artist = track_info.artist or album_info.artist
            item.albumartist = album_info.artist

        # Album.
        item.album = album_info.album

        # Artist sort and credit names.
        item.artist_sort = track_info.artist_sort or album_info.artist_sort
        item.artist_credit = (
            track_info.artist_credit or album_info.artist_credit
        )
        item.albumartist_sort = album_info.artist_sort
        item.albumartist_credit = album_info.artist_credit

        # Release date.
        for prefix in '', 'original_':
            if config['original_date'] and not prefix:
                # Ignore specific release date.
                continue

            for suffix in 'year', 'month', 'day':
                key = prefix + suffix
                value = getattr(album_info, key) or 0

                # If we don't even have a year, apply nothing.
                if suffix == 'year' and not value:
                    break

                # Otherwise, set the fetched value (or 0 for the month
                # and day if not available).
                item[key] = value

                # If we're using original release date for both fields,
                # also set item.year = info.original_year, etc.
                if config['original_date']:
                    item[suffix] = value

        # Title.
        item.title = track_info.title

        if config['per_disc_numbering']:
            # We want to let the track number be zero, but if the medium index
            # is not provided we need to fall back to the overall index.
            if track_info.medium_index is not None:
                item.track = track_info.medium_index
            else:
                item.track = track_info.index
            item.tracktotal = track_info.medium_total or len(album_info.tracks)
        else:
            item.track = track_info.index
            item.tracktotal = len(album_info.tracks)

        # Disc and disc count.
        item.disc = track_info.medium
        item.disctotal = album_info.mediums

        # MusicBrainz IDs.
        item.mb_trackid = track_info.track_id
        item.mb_releasetrackid = track_info.release_track_id
        item.mb_albumid = album_info.album_id
        if track_info.artist_id:
            item.mb_artistid = track_info.artist_id
        else:
            item.mb_artistid = album_info.artist_id
        item.mb_albumartistid = album_info.artist_id
        item.mb_releasegroupid = album_info.releasegroup_id

        # Compilation flag.
        item.comp = album_info.va

        # Track alt.
        item.track_alt = track_info.track_alt

        # Miscellaneous/nullable metadata.
        misc_fields = {
            'album': (
                'albumtype',
                'label',
                'asin',
                'catalognum',
                'script',
                'language',
                'country',
                'style',
                'genre',
                'discogs_albumid',
                'albumstatus',
                'albumdisambig',
                'releasegroupdisambig',
                'data_source',
            ),
            'track': (
                'disctitle',
                'lyricist',
                'media',
                'composer',
                'composer_sort',
                'arranger',
                'work',
                'mb_workid',
                'work_disambig',
            ),
        }

        # Don't overwrite fields with empty values unless the
        # field is explicitly allowed to be overwritten
        for field in misc_fields['album']:
            clobber = field in config['overwrite_null']['album'].as_str_seq()
            value = getattr(album_info, field)
            if value is None and not clobber:
                continue
            item[field] = value

        for field in misc_fields['track']:
            clobber = field in config['overwrite_null']['track'].as_str_seq()
            value = getattr(track_info, field)
            if value is None and not clobber:
                continue
            item[field] = value


def album_distance(config, data_source, album_info):
    """Returns the ``data_source`` weight and the maximum source weight
    for albums.
    """
    dist = Distance()
    if album_info.data_source == data_source:
        dist.add('source', config['source_weight'].as_number())
    return dist


def track_distance(config, data_source, track_info):
    """Returns the ``data_source`` weight and the maximum source weight
    for individual tracks.
    """
    dist = Distance()
    if track_info.data_source == data_source:
        dist.add('source', config['source_weight'].as_number())
    return dist


class APIAutotaggerPlugin(BeetsPlugin):
    def __init__(self):
        super(APIAutotaggerPlugin, self).__init__()
        self.config.add({'source_weight': 0.5})

    @abstractproperty
    def id_regex(self):
        raise NotImplementedError

    @abstractproperty
    def data_source(self):
        raise NotImplementedError

    @abstractproperty
    def search_url(self):
        raise NotImplementedError

    @abstractproperty
    def album_url(self):
        raise NotImplementedError

    @abstractproperty
    def track_url(self):
        raise NotImplementedError

    @abstractmethod
    def _search_api(self, query_type, filters, keywords=''):
        raise NotImplementedError

    @abstractmethod
    def album_for_id(self, album_id):
        raise NotImplementedError

    @abstractmethod
    def track_for_id(self, track_id=None, track_data=None):
        raise NotImplementedError

    @staticmethod
    def get_artist(artists, id_key='id', name_key='name'):
        """Returns an artist string (all artists) and an artist_id (the main
        artist) for a list of artist object dicts.

        :param artists: Iterable of artist dicts returned by API.
        :type artists: list[dict]
        :param id_key: Key corresponding to ``artist_id`` value.
        :type id_key: str
        :param name_key: Keys corresponding to values to concatenate for ``artist``.
        :type name_key: str
        :return: Normalized artist string.
        :rtype: str
        """
        artist_id = None
        artist_names = []
        for artist in artists:
            if not artist_id:
                artist_id = artist[id_key]
            name = artist[name_key]
            # Move articles to the front.
            name = re.sub(r'^(.*?), (a|an|the)$', r'\2 \1', name, flags=re.I)
            artist_names.append(name)
        artist = ', '.join(artist_names).replace(' ,', ',') or None
        return artist, artist_id

    def _get_id(self, url_type, id_):
        """Parse an ID from its URL if necessary.

        :param url_type: Type of URL. Either 'album' or 'track'.
        :type url_type: str
        :param id_: Album/track ID or URL.
        :type id_: str
        :return: Album/track ID.
        :rtype: str
        """
        self._log.debug(
            u"Searching {} for {} '{}'", self.data_source, url_type, id_
        )
        match = re.search(
            self.id_regex['pattern'].format(url_type=url_type), str(id_)
        )
        id_ = match.group(self.id_regex['match_group'])
        return id_ if id_ else None

    def candidates(self, items, artist, album, va_likely):
        """Returns a list of AlbumInfo objects for Search API results
        matching an ``album`` and ``artist`` (if not various).

        :param items: List of items comprised by an album to be matched.
        :type items: list[beets.library.Item]
        :param artist: The artist of the album to be matched.
        :type artist: str
        :param album: The name of the album to be matched.
        :type album: str
        :param va_likely: True if the album to be matched likely has
            Various Artists.
        :type va_likely: bool
        :return: Candidate AlbumInfo objects.
        :rtype: list[beets.autotag.hooks.AlbumInfo]
        """
        query_filters = {'album': album}
        if not va_likely:
            query_filters['artist'] = artist
        albums = self._search_api(query_type='album', filters=query_filters)
        return [self.album_for_id(album_id=album['id']) for album in albums]

    def item_candidates(self, item, artist, title):
        """Returns a list of TrackInfo objects for Search API results
        matching ``title`` and ``artist``.

        :param item: Singleton item to be matched.
        :type item: beets.library.Item
        :param artist: The artist of the track to be matched.
        :type artist: str
        :param title: The title of the track to be matched.
        :type title: str
        :return: Candidate TrackInfo objects.
        :rtype: list[beets.autotag.hooks.TrackInfo]
        """
        tracks = self._search_api(
            query_type='track', keywords=title, filters={'artist': artist}
        )
        return [self.track_for_id(track_data=track) for track in tracks]

    def album_distance(self, items, album_info, mapping):
        return album_distance(
            data_source=self.data_source,
            album_info=album_info,
            config=self.config,
        )

    def track_distance(self, item, track_info):
        return track_distance(
            data_source=self.data_source,
            track_info=track_info,
            config=self.config,
        )
