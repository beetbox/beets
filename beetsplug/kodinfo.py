
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

from beets.plugins import BeetsPlugin
from beets import library


class KodiNfo(BeetsPlugin):
  def __init__(self):
    super(KodiNfo, self).__init__()
    self.register_listener('album_imported', self.makeAlbumNfo)
    self.register_listener('item_imported', self.makeItemNfo)

  def makeAlbumNfo(self, lib, album):
    linkAlbum = 'https://musicbrainz.org/release/{0}'
    linkArtist = 'https://musicbrainz.org/artist/{0}'
    with open(album.path + '/album.nfo', 'w') as f:
		f.write(linkAlbum.format(album.mb_albumid))
    with open(album.path + '/../artist.nfo', 'w') as f:
        f.write(linkArtist.format(album.mb_albumartistid))

  def makeItemNfo(self, lib, item):
    link = 'https://musicbrainz.org/recording/{0}'
    with open(item.path + '/' + item.title + '.nfo/', 'w') as f:
		f.write(link.format(item.mb_trackid))