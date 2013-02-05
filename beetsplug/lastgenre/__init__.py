# This file is part of beets.
# Copyright 2013, Adrian Sampson.
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
import yaml

from beets import plugins
from beets import ui
from beets.util import normpath
from beets import config
from beets import library

log = logging.getLogger('beets')

LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)
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

def is_allowed(genre):
    """Returns True if the genre is present in the genre whitelist or
    False if not.
    """
    if genre is None:
        return False
    if genre.lower() in options['whitelist']:
        return True
    return False

def find_allowed(genres):
    """Returns the first genre that is present in the genre whitelist or
    None if no genre is suitable.
    """
    for genre in list(genres):
        if is_allowed(genre):
            return genre.title()
    return None

def fetch_genre(lastfm_obj):
    """Returns the genre for this lastfm_obj.
    """
    return _tags_to_genre(_tags_for(lastfm_obj))

def fetch_album_genre(obj):
    """Returns the album genre for this obj.  Either performs a lookup in
    lastfm or returns the cached value.
    """
    lookup = u'album.{0}-{1}'.format(obj.albumartist, obj.album)
    if not cache.has_key(lookup):
        cache[lookup] = \
              fetch_genre(LASTFM.get_album(obj.albumartist, obj.album))
    return cache[lookup]

def fetch_album_artist_genre(obj):
    """Returns the album artists genre for this obj.  Either performs a lookup
    in lastfm or returns the cached value.
    """
    lookup = u'artist.${0}'.format(obj.albumartist)
    if not cache.has_key(lookup):
        cache[lookup] = \
              fetch_genre(LASTFM.get_artist(obj.albumartist))
    return cache[lookup]

def fetch_artist_genre(obj):
    """Returns the track artists genre for this obj.  Either performs a lookup
    in lastfm or returns the cached value.
    """
    lookup = u'artist.${0}'.format(obj.artist)
    if not cache.has_key(lookup):
        cache[lookup] = fetch_genre(LASTFM.get_artist(obj.artist))
    return cache[lookup]

def fetch_track_genre(obj):
    """Returns the track genre for this obj.  Either performs a lookup in
    lastfm or returns the cached value.  """
    lookup = u'track.{0}-{1}'.format(obj.artist, obj.title)
    if not cache.has_key(lookup):
        cache[lookup] = fetch_genre(LASTFM.get_track(obj.artist, obj.title))
    return cache[lookup]

options = {
    'whitelist': None,
    'branches': None,
    'c14n': False,
}
# simple cache to speed up artist and album lookups track or album mode.  it's
# probably not required to cache track lookups, but...
cache = {}
class LastGenrePlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(LastGenrePlugin, self).__init__()
        self.import_stages = [self.imported]

        self.config.add({
            'whitelist': os.path.join(os.path.dirname(__file__), 'genres.txt'),
            'fallback': None,
            'canonical': None,
            'source': 'album',
            'force': False,
        })

        # Read the whitelist file.
        wl_filename = self.config['whitelist'].as_filename()
        whitelist = set()
        with open(wl_filename) as f:
            for line in f:
                line = line.decode('utf8').strip().lower()
                if line:
                    whitelist.add(line)
        options['whitelist'] = whitelist

        # Read the genres tree for canonicalization if enabled.
        c14n_filename = self.config['canonical'].get()
        if c14n_filename is not None:
            c14n_filename = c14n_filename.strip()
            if not c14n_filename:
                c14n_filename = C14N_TREE
            c14n_filename = normpath(c14n_filename)

            genres_tree = yaml.load(open(c14n_filename, 'r'))
            branches = []
            flatten_tree(genres_tree, [], branches)
            options['branches'] = branches
            options['c14n'] = True

    def _set_sources(self, source):
        """Prepare our internal represantation of valid sources we can use.
        """
        self.sources = []
        if source == 'track':
            self.sources.extend(['track', 'album', 'artist'])
        elif source == 'album':
            self.sources.extend(['album', 'artist'])
        elif source == 'artist':
            self.sources.extend(['artist'])

    def _get_album_genre(self, album, force, fallback_str):
        """Return the best candidate for album genre based on sources (see
        _set_sources).
        Going down from album -> artist -> original -> fallback -> None.
        """
        if not force and is_allowed(album.genre):
            return [album.genre, 'keep']
        result = None
        # no track lookup for album genre
        if 'album' in self.sources:
            result = fetch_album_genre(album)
            if result:
                return [result, 'album']
        if 'artist' in self.sources:
            # no artist lookup for Various Artists
            if not album.albumartist == 'Various Artists':
                result = fetch_album_artist_genre(album)
            if result:
                return [result, 'artist']
        if is_allowed(album.genre):
            return [album.genre, 'original']
        if fallback_str:
            return [fallback_str, 'fallback']
        return [None, None]


    def _get_item_genre(self, item, force, fallback_str):
        """Return the best candidate for item genre based on sources (see
        _set_sources).
        Going down from track -> album -> artist -> original -> fallback ->
        None.
        """
        if not force:
            if is_allowed(item.genre):
                return [item.genre, 'keep']
        result = None
        if 'track' in self.sources:
            result = fetch_track_genre(item)
            if result:
                return [result, 'track']
        if 'album' in self.sources:
            if item.album:
                result = fetch_album_genre(item)
            if result:
                return [result, 'album']
        if 'artist' in self.sources:
            result = fetch_artist_genre(item)
            if result:
                return [result, 'artist']
        if is_allowed(item.genre):
            return [item.genre, 'original']
        if fallback_str:
            return [fallback_str, 'fallback']
        return [None, None]

    def commands(self):
        lastgenre_cmd = ui.Subcommand('lastgenre', help='fetch genres')
        lastgenre_cmd.parser.add_option('-f', '--force', dest='force',
                              action='store_true',
                              default=self.config['force'].get(bool),
                              help='re-download genre when already present')
        lastgenre_cmd.parser.add_option('-v', '--verbose', dest='verbose',
                              action='store_true',
                              default=False,
                              help='be more verbose')
        lastgenre_cmd.parser.add_option('-s', '--source', dest='source',
                              type='string',
                              default=self.config['source'].get(),
                              help='set source, one of: artist / album / track')
        def lastgenre_func(lib, opts, args):
            # The "write to files" option corresponds to the
            # import_write config value.
            write = config['import']['write'].get(bool)
            force = opts.force
            self._set_sources(opts.source)
            fallback_str = self.config['fallback'].get()
            for album in lib.albums(ui.decargs(args)):
                album.genre, src = self._get_album_genre(album, force, fallback_str)
                if opts.verbose:
                    log.info(u'LastGenre: Album({0} - {1}) > {2}({3})'.format(
                        album.albumartist, album.album, album.genre, src))
                for item in album.items():
                    item.genre, src = self._get_item_genre(item, force,
                          fallback_str)
                    lib.store(item)
                    if opts.verbose:
                        log.info(u'LastGenre: Item({0} - {1}) > {2}({3})'.format(
                            item.artist, item.title, item.genre, src))
                    if write:
                        item.write()

        lastgenre_cmd.func = lastgenre_func
        return [lastgenre_cmd]

    def imported(self, session, task):
        self._set_sources(self.config['source'].get())
        tags = []
        fallback_str = self.config['fallback'].get()
        if task.is_album:
            album = session.lib.get_album(task.album_id)
            album.genre, src = self._get_album_genre(album, True, fallback_str)
            log.debug(u'added last.fm album genre ({0}): {1}'.format(
                  src, album.genre))
            for item in album.items():
                item.genre, src = self._get_item_genre(item, True, fallback_str)
                log.debug(u'added last.fm item genre ({0}): {1}'.format(
                      src, item.genre))
        else:
            item = task.item
            item.genre, src = self._get_item_genre(item, True, fallback_str)
            log.debug(u'added last.fm item genre ({0}): {1}'.format(
                  src, item.genre))
            session.lib.store(item)
