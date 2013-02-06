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


# Core genre identification routine.

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

def _is_allowed(genre):
    """Determine whether the genre is present in the whitelist,
    returning a boolean.
    """
    if genre is None:
        return False
    if genre.lower() in options['whitelist']:
        return True
    return False

def _find_allowed(genres):
    """Return the first string in the sequence `genres` that is present
    in the genre whitelist or None if no genre is suitable.
    """
    for genre in list(genres):
        if _is_allowed(genre):
            return genre.title()  # Title case.
    return None

def _strings_to_genre(tags):
    """Given a list of strings, return a genre. Returns the first string
    that is present in the genre whitelist (or the canonicalization
    tree) or None if no tag is suitable.
    """
    if not tags:
        return None
    elif not options['whitelist']:
        return tags[0].title()

    if options.get('c14n'):
        # Use the canonicalization tree.
        for tag in tags:
            return _find_allowed(find_parents(tag, options['branches']))
    else:
        # Just use the flat whitelist.
        return _find_allowed(tags)

def fetch_genre(lastfm_obj):
    """Return the genre for a pylast entity or None if no suitable genre
    can be found.
    """
    return _strings_to_genre(_tags_for(lastfm_obj))


# Canonicalization tree processing.

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


# Cached entity lookups.

_genre_cache = {}

def _cached_lookup(entity, method, *args):
    """Get a genre based on the named entity using the callable `method`
    whose arguments are given in the sequence `args`. The genre lookup
    is cached based on the entity name and the arguments.
    """
    # Shortcut if we're missing metadata.
    if any(not s for s in args):
        return None

    key = u'{0}.{1}'.format(entity, u'-'.join(unicode(a) for a in args))
    if key in _genre_cache:
        return _genre_cache[key]
    else:
        genre = fetch_genre(method(*args))
        _genre_cache[key] = genre
        return genre

def fetch_album_genre(obj):
    """Return the album genre for this Item or Album.
    """
    return _cached_lookup(u'album', LASTFM.get_album, obj.albumartist,
                          obj.album)

def fetch_album_artist_genre(obj):
    """Return the album artist genre for this Item or Album.
    """
    return _cached_lookup(u'artist', LASTFM.get_artist, obj.albumartist)

def fetch_artist_genre(item):
    """Returns the track artist genre for this Item.
    """
    return _cached_lookup(u'artist', LASTFM.get_artist, item.artist)

def fetch_track_genre(obj):
    """Returns the track genre for this Item.
    """
    return _cached_lookup(u'track', LASTFM.get_track, obj.artist, obj.title)


# Main plugin logic.

options = {
    'whitelist': None,
    'branches': None,
    'c14n': False,
}
class LastGenrePlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(LastGenrePlugin, self).__init__()

        self.config.add({
            'whitelist': os.path.join(os.path.dirname(__file__), 'genres.txt'),
            'fallback': None,
            'canonical': None,
            'source': 'album',
            'force': False,
            'auto': True,
        })

        if self.config['auto']:
            self.import_stages = [self.imported]

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

    @property
    def sources(self):
        """A tuple of allowed genre sources. May contain 'track',
        'album', or 'artist.'
        """
        source = self.config['source'].as_choice(('track', 'album', 'artist'))
        if source == 'track':
            return 'track', 'album', 'artist'
        elif source == 'album':
            return 'album', 'artist'
        elif source == 'artist':
            return 'artist',

    def _get_genre(self, obj):
        """Get the genre string for an Album or Item object based on
        self.sources. Return a `(genre, source)` pair. The
        prioritization order is:
            - track (for Items only)
            - album
            - artist
            - original
            - fallback
            - None
        """
        # Shortcut to existing genre if not forcing.
        if not self.config['force'] and _is_allowed(obj.genre):
            return obj.genre, 'keep'

        # Track genre (for Items only).
        if isinstance(obj, library.Item):
            if 'track' in self.sources:
                result = fetch_track_genre(obj)
                if result:
                    return result, 'track'

        # Album genre.
        if 'album' in self.sources:
            result = fetch_album_genre(obj)
            if result:
                return result, 'album'

        # Artist (or album artist) genre.
        if 'artist' in self.sources:
            result = None
            if isinstance(obj, library.Item):
                result = fetch_artist_genre(obj)
            elif obj.albumartist != 'Various Artists':
                result = fetch_album_artist_genre(obj)
            else:
                # For 'Various Artists' pick the most used common tag as
                # album_tag
                artist_genres = {}
                for item in obj.items():
                    tmp_genre = None
                    if 'track' in self.sources:
                        tmp_genre = fetch_track_genre(item)
                    if not tmp_genre:
                        tmp_genre = fetch_artist_genre(item)
                    if tmp_genre:
                        artist_genres[tmp_genre] = \
                            artist_genres.get(tmp_genre, 0) + 1
                if len(artist_genres) > 0:
                    result = filter(lambda k:artist_genres[k] ==
                        max(artist_genres.values()), artist_genres)[0]

            if result:
                return result, 'artist'

        # Filter the existing genre.
        result = _strings_to_genre([obj.genre])
        if result:
            return result, 'original'

        # Fallback string.
        fallback = self.config['fallback'].get()
        if fallback:
            return fallback, 'fallback'

        return None, None

    def commands(self):
        lastgenre_cmd = ui.Subcommand('lastgenre', help='fetch genres')
        lastgenre_cmd.parser.add_option('-f', '--force', dest='force',
                              action='store_true',
                              help='re-download genre when already present')
        lastgenre_cmd.parser.add_option('-s', '--source', dest='source',
                              type='string',
                              help='genre source: artist, album, or track')
        def lastgenre_func(lib, opts, args):
            write = config['import']['write'].get(bool)
            self.config.set_args(opts)

            for album in lib.albums(ui.decargs(args)):
                album.genre, src = self._get_genre(album)
                log.info(u'genre for album {0} - {1} ({2}): {3}'.format(
                    album.albumartist, album.album, src, album.genre
                ))

                for item in album.items():
                    if 'track' in self.sources:
                        # Fetch track genre only if source is 'track'
                        item.genre, src = self._get_genre(item)
                        lib.store(item)
                        log.info(u'genre for track {0} - {1} ({2}): {3}'.format(
                            item.artist, item.title, src, item.genre
                        ))
                    if write:
                        item.write()

        lastgenre_cmd.func = lastgenre_func
        return [lastgenre_cmd]

    def imported(self, session, task):
        """Event hook called when an import task finishes."""
        # Always force a "real" lookup during import.
        if not self.config['force']:
            self.config['force'] = True

        if task.is_album:
            album = session.lib.get_album(task.album_id)
            album.genre, src = self._get_genre(album)
            log.debug(u'added last.fm album genre ({0}): {1}'.format(
                  src, album.genre))
            for item in album.items():
                if 'track' in self.sources:
                    item.genre, src = self._get_genre(item)
                    log.debug(u'added last.fm item genre ({0}): {1}'.format(
                          src, item.genre))
                    session.lib.store(item)

        else:
            item = task.item
            item.genre, src = self._get_genre(item)
            log.debug(u'added last.fm item genre ({0}): {1}'.format(
                  src, item.genre))
            session.lib.store(item)
