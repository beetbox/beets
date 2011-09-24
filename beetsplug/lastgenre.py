# This file is part of beets.
# Copyright 2011, Adrian Sampson.
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

"""Gets genres for imported music based on Last.fm tags.
"""

import logging
import pylast

from beets import plugins, ui

log = logging.getLogger('beets')
LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)
WEIGHT_THRESH = 50

def _tags_for(obj):
    """Given a pylast entity (album or track), returns a list of
    tag names for that entity. Returns an empty list if the entity is
    not found or another error occurs.
    """
    try:
        res = obj.get_top_tags()
    except pylast.WSError, exc:
        log.debug(u'last.fm error: %s' % unicode(exc))
        return []

    tags = []
    for el in res:
        if isinstance(el, pylast.TopItem):
            el = el.item
        tags.append(el.get_name())
    log.debug(u'last.fm tags: %s' % unicode(tags))
    return tags

def _tags_to_genre(tags):
    """Given a tag list, returns a genre. Returns the first tag that is present
    in genres white list or None if no tag is suitable. 
    """
    if not tags:
        return None
    elif not options['genres_whitelist']:
        return tags[0].title()
    
    for tag in tags :
        if tag.lower() in options['genres_whitelist'] :
            return tag.title()
    
    return None

options = {
    'genres_whitelist': None,
}
class LastGenrePlugin(plugins.BeetsPlugin):
    def configure(self, config):
        genres_whitelist = ui.config_val(config, 'lastgenre',
                                         'genres_whitelist', None)
        options['genres_whitelist'] = genres_whitelist.lower().split(',')
        
@LastGenrePlugin.listen('album_imported')
def album_imported(lib, album):
    tags = _tags_for(LASTFM.get_album(album.albumartist, album.album))
    genre = _tags_to_genre(tags)
    if genre:
        log.debug(u'adding last.fm album genre: %s' % genre)
        album.genre = genre
        lib.save()

@LastGenrePlugin.listen('item_imported')
def item_imported(lib, item):
    tags = _tags_for(LASTFM.get_track(item.artist, item.title))

    genre = _tags_to_genre(tags)
    if genre:
        log.debug(u'adding last.fm item genre: %s' % genre)
        item.genre = genre
        lib.save()

