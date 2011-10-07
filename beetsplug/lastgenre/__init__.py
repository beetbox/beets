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

Uses a provided whitelist file to determine which tags are valid genres.
The genre whitelist can be specified like so in .beetsconfig:

    [lastgenre]
    whitelist=/path/to/genres.txt

The included (default) genre list was produced by scraping Wikipedia.
The scraper script used is available here:
https://gist.github.com/1241307
"""
from __future__ import with_statement

import logging
import pylast
import os

from beets import plugins
from beets import ui
from beets.util import normpath

log = logging.getLogger('beets')
LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)
DEFAULT_WHITELIST = os.path.join(os.path.dirname(__file__), 'genres.txt')

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
    """Given a tag list, returns a genre. Returns the first tag that is
    present in the genre whitelist or None if no tag is suitable. 
    """
    if not tags:
        return None
    elif not options['whitelist']:
        return tags[0].title()
    
    for tag in tags:
        if tag.lower() in options['whitelist']:
            return tag.title()
    
    return None

options = {
    'whitelist': None,
}
class LastGenrePlugin(plugins.BeetsPlugin):
    def configure(self, config):
        wl_filename = ui.config_val(config, 'lastgenre', 'whitelist', None)
        if not wl_filename:
            # No filename specified. Instead, use the whitelist that's included
            # with the plugin (inside the package).
            wl_filename = DEFAULT_WHITELIST
        wl_filename = normpath(wl_filename)

        # Read the whitelist file.
        whitelist = set()
        with open(wl_filename) as f:
            for line in f:
                line = line.decode('utf8').strip().lower()
                if line:
                    whitelist.add(line)
        options['whitelist'] = whitelist
        
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

