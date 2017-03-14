# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017, Sergio Soto.
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

"""Genertes artist.nfo and album.nfo after the import process
These are used by Kodi and other platforms to save the MBID
and other details.
For singletons, it generates one .nfo for each track.
"""

from __future__ import absolute_import, division, print_function

import os
from beets.plugins import BeetsPlugin

LINK_ALBUM = 'https://musicbrainz.org/release/{0}'
LINK_ARTIST = 'https://musicbrainz.org/artist/{0}'
LINK_TRACK = 'https://musicbrainz.org/recording/{0}'


class KodiNfo(BeetsPlugin):
    def __init__(self):
        super(KodiNfo, self).__init__()
        self.register_listener('album_imported', self.make_album_nfo)
        self.register_listener('item_imported', self.make_item_nfo)

    def make_album_nfo(self, lib, album):
        album_path = os.path.join(album.path, 'album.nfo')
        artist_path = os.path.join(album.path, os.pardir, 'artist.nfo')
        if not os.path.isfile(album_path):
            with open(album_path, 'w') as f:
                f.write(LINK_ALBUM.format(album.mb_albumid))
        if not os.path.isfile(artist_path):
            with open(artist_path, 'w') as f:
                f.write(LINK_ARTIST.format(album.mb_albumartistid))

    def make_item_nfo(self, lib, item):
        track_file = item.title + '.nfo'
        track_path = os.path.join(item.path, track_file)
        with open(track_path, 'w') as f:
            f.write(LINK_TRACK.format(item.mb_trackid))
