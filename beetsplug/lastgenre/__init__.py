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
import logging
import pylast
import os

from beets import plugins
from beets import ui
from beets.util import normpath
from beets.ui import commands

log = logging.getLogger('beets')

LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)
DEFAULT_WHITELIST = os.path.join(os.path.dirname(__file__), 'genres.txt')
C14N_TREE = os.path.join(os.path.dirname(__file__), 'genres-tree.yaml')

PYLAST_EXCEPTIONS = (
    pylast.WSError,
    pylast.MalformedResponseError,
    pylast.NetworkError,
)

def _tags_for(obj):
    """Given a pylast entity (album or track), returns a list of
    tag names for that entity. Returns an empty list if the entity is
    not found or another error occurs.
    """
    try:
        res = obj.get_top_tags()
    except PYLAST_EXCEPTIONS as exc:
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

    if options.get('c14n'):
        # Use the canonicalization tree.
        for tag in tags:
            genre = find_allowed(find_parents(tag, options['branches']))
            if genre:
                return genre
    else:
        # Just use the flat whitelist.
        return find_allowed(tags)

def flatten_tree(elem, path, branches):
    """Flatten nested lists/dictionaries into lists of strings
    (branches).
    """
    if not path:
        path = []

    if isinstance(elem, dict):
        for (k, v) in elem.items():
            flatten_tree(v, path + [k], branches)
    elif isinstance(elem, list):
        for sub in elem:
            flatten_tree(sub, path, branches)
    else:
        branches.append(path + [unicode(elem)])

def find_parents(candidate, branches):
    """Find parents genre of a given genre, ordered from the closest to
    the further parent.
    """
    for branch in branches:
        try:
            idx = branch.index(candidate.lower())
            return list(reversed(branch[:idx+1]))
        except ValueError:
            continue
    return [candidate]

def find_allowed(genres):
    """Returns the first genre that is present in the genre whitelist or
    None if no genre is suitable.
    """
    for genre in list(genres):
        if genre.lower() in options['whitelist']:
            return genre.title()
    return None

options = {
    'whitelist': None,
    'branches': None,
    'c14n': False,
}
fallback_str = None
class LastGenrePlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(LastGenrePlugin, self).__init__()
        self.import_stages = [self.imported]

    def configure(self, config):
        global fallback_str

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

        # Read the genres tree for canonicalization if enabled.
        c14n_filename = ui.config_val(config, 'lastgenre', 'canonical', None)
        if c14n_filename is not None:
            c14n_filename = c14n_filename.strip()
            if not c14n_filename:
                c14n_filename = C14N_TREE
            c14n_filename = normpath(c14n_filename)

            from yaml import load
            genres_tree = load(open(c14n_filename, 'r'))
            branches = []
            flatten_tree(genres_tree, [], branches)
            options['branches'] = branches
            options['c14n'] = True

        fallback_str = ui.config_val(config, 'lastgenre', 'fallback_str', None)

    def commands(self):
        lastgenre_cmd = ui.Subcommand('lastgenre', help='fetch genres')
        def lastgenre_func(lib, config, opts, args):
            # The "write to files" option corresponds to the
            # import_write config value.
            write = ui.config_val(config, 'beets', 'import_write',
                                  commands.DEFAULT_IMPORT_WRITE, bool)
            for album in lib.albums(ui.decargs(args)):
                tags = []    
                lastfm_obj = LASTFM.get_album(album.albumartist, album.album)
                if album.genre:
                    tags.append(album.genre)

                tags.extend(_tags_for(lastfm_obj))
                genre = _tags_to_genre(tags)

                if not genre and fallback_str != None:
                    genre = fallback_str
                    log.debug(u'no last.fm genre found: fallback to %s' % genre)

                if genre is not None:
                    log.debug(u'adding last.fm album genre: %s' % genre)
                    album.genre = genre
                    if write:
                        for item in album.items():
                            item.write()
        lastgenre_cmd.func = lastgenre_func
        return [lastgenre_cmd]

    def imported(self, config, task):
        tags = []
        if task.is_album:
            album = config.lib.get_album(task.album_id)
            lastfm_obj = LASTFM.get_album(album.albumartist, album.album)
            if album.genre:
                tags.append(album.genre)
        else:
            item = task.item
            lastfm_obj = LASTFM.get_track(item.artist, item.title)
            if item.genre:
                tags.append(item.genre)

        tags.extend(_tags_for(lastfm_obj))
        genre = _tags_to_genre(tags)
        
        if not genre and fallback_str != None:
            genre = fallback_str
            log.debug(u'no last.fm genre found: fallback to %s' % genre)

        if genre is not None:
            log.debug(u'adding last.fm album genre: %s' % genre)

            if task.is_album:
                album = config.lib.get_album(task.album_id)
                album.genre = genre
            else:
                item.genre = genre
                config.lib.store(item)
