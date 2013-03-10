"""Abstract plugin for new search
service support for the autotagger.
"""
global str

import logging
import abc

from os.path import dirname, basename

from beets.plugins import BeetsPlugin
from beets.autotag import match

log = logging.getLogger('beets')

# Plugin structure and autotagging logic.

class AbstractSearchPlugin(BeetsPlugin):
    name = ''

    def __init__(self):
        self.name = self.__class__.__name__
        super(AbstractSearchPlugin, self).__init__()

    def candidates(self, items):
        try:
            artist, album = self._metadata_from_items(items)
            albums = self._search(artist, album)

            return map(self._album_info, albums)
        except BaseException as e:
            log.error(self.name + ' search error: ' + str(e))
            return []

    @abc.abstractmethod
    def _search(self, artist, album):
        log.debug(self.name + ' search for: ' + artist + ' - ' + album)
        return []

    @abc.abstractmethod
    def _album_info(self, album):
        pass

    def _metadata_from_items(self, items):
        artist, album, artist_consensus = match.current_metadata(items)

        va_likely = ((not artist_consensus) or
                     (artist.lower() in match.VA_ARTISTS) or
                     any(item.comp for item in items))

        if va_likely:
            return u'', album
        else:
            return artist, album
