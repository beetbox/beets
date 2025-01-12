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


"""Gets genres for imported music based on Last.fm tags.

Uses a provided whitelist file to determine which tags are valid genres.
The included (default) genre list was originally produced by scraping Wikipedia
and has been edited to remove some questionable entries.
The scraper script used is available here:
https://gist.github.com/1241307
"""

import codecs
import os
import traceback

import pylast
import yaml

from beets import config, library, plugins, ui
from beets.util import normpath, plurality, unique_list

LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)

PYLAST_EXCEPTIONS = (
    pylast.WSError,
    pylast.MalformedResponseError,
    pylast.NetworkError,
)

REPLACE = {
    "\u2010": "-",
}


# Canonicalization tree processing.


def flatten_tree(elem, path, branches):
    """Flatten nested lists/dictionaries into lists of strings
    (branches).
    """
    if not path:
        path = []

    if isinstance(elem, dict):
        for k, v in elem.items():
            flatten_tree(v, path + [k], branches)
    elif isinstance(elem, list):
        for sub in elem:
            flatten_tree(sub, path, branches)
    else:
        branches.append(path + [str(elem)])


def find_parents(candidate, branches):
    """Find parents genre of a given genre, ordered from the closest to
    the further parent.
    """
    for branch in branches:
        try:
            idx = branch.index(candidate.lower())
            return list(reversed(branch[: idx + 1]))
        except ValueError:
            continue
    return [candidate]


# Main plugin logic.

WHITELIST = os.path.join(os.path.dirname(__file__), "genres.txt")
C14N_TREE = os.path.join(os.path.dirname(__file__), "genres-tree.yaml")


class LastGenrePlugin(plugins.BeetsPlugin):
    def __init__(self):
        super().__init__()

        self.config.add(
            {
                "whitelist": True,
                "min_weight": 10,
                "count": 1,
                "fallback": None,
                "canonical": False,
                "source": "album",
                "force": True,
                "keep_existing": True,
                "auto": True,
                "separator": ", ",
                "prefer_specific": False,
                "title_case": True,
            }
        )
        self.config_validation()
        self.setup()

    def config_validation(self) -> None:
        """Quits plugin when invalid configurations are detected."""
        keep_existing = self.config["keep_existing"].get()
        force = self.config["force"].get()

        if keep_existing and not force:
            raise ui.UserError(
                "Invalid lastgenre plugin configuration (enable force with "
                "keep_existing!)"
            )

    def setup(self):
        """Setup plugin from config options"""
        if self.config["auto"]:
            self.import_stages = [self.imported]

        self._genre_cache = {}

        # Read the whitelist file if enabled.
        self.whitelist = set()
        wl_filename = self.config["whitelist"].get()
        if wl_filename in (True, ""):  # Indicates the default whitelist.
            wl_filename = WHITELIST
        if wl_filename:
            wl_filename = normpath(wl_filename)
            with open(wl_filename, "rb") as f:
                for line in f:
                    line = line.decode("utf-8").strip().lower()
                    if line and not line.startswith("#"):
                        self.whitelist.add(line)

        # Read the genres tree for canonicalization if enabled.
        self.c14n_branches = []
        c14n_filename = self.config["canonical"].get()
        self.canonicalize = c14n_filename is not False

        # Default tree
        if c14n_filename in (True, ""):
            c14n_filename = C14N_TREE
        elif not self.canonicalize and self.config["prefer_specific"].get():
            # prefer_specific requires a tree, load default tree
            c14n_filename = C14N_TREE

        # Read the tree
        if c14n_filename:
            self._log.debug("Loading canonicalization tree {0}", c14n_filename)
            c14n_filename = normpath(c14n_filename)
            with codecs.open(c14n_filename, "r", encoding="utf-8") as f:
                genres_tree = yaml.safe_load(f)
            flatten_tree(genres_tree, [], self.c14n_branches)

    @property
    def sources(self):
        """A tuple of allowed genre sources. May contain 'track',
        'album', or 'artist.'
        """
        source = self.config["source"].as_choice(("track", "album", "artist"))
        if source == "track":
            return "track", "album", "artist"
        elif source == "album":
            return "album", "artist"
        elif source == "artist":
            return ("artist",)

    # More canonicalization and general helpers.

    def _to_delimited_genre_string(self, tags: list[str]) -> str:
        """Reduce tags list to configured count, format and return as delimited
        string."""
        separator = self.config["separator"].as_str()
        max_count = self.config["count"].get(int)

        genres = tags[:max_count]
        if self.config["title_case"]:
            genres = [g.title() for g in genres]

        return separator.join(genres)

    def _get_depth(self, tag):
        """Find the depth of a tag in the genres tree."""
        depth = None
        for key, value in enumerate(self.c14n_branches):
            if tag in value:
                depth = value.index(tag)
                break
        return depth

    def _sort_by_depth(self, tags):
        """Given a list of tags, sort the tags by their depths in the
        genre tree.
        """
        depth_tag_pairs = [(self._get_depth(t), t) for t in tags]
        depth_tag_pairs = [e for e in depth_tag_pairs if e[0] is not None]
        depth_tag_pairs.sort(reverse=True)
        return [p[1] for p in depth_tag_pairs]

    def _resolve_genres(self, tags) -> list:
        """Given a list of genre strings, filters, dedups, sorts and
        canonicalizes."""
        if not tags:
            return []

        count = self.config["count"].get(int)
        if self.canonicalize:
            # Extend the list to consider tags parents in the c14n tree
            tags_all = []
            for tag in tags:
                # Add parents that are in the whitelist, or add the oldest
                # ancestor if no whitelist
                if self.whitelist:
                    parents = [
                        x
                        for x in find_parents(tag, self.c14n_branches)
                        if self._is_valid(x)
                    ]
                else:
                    parents = [find_parents(tag, self.c14n_branches)[-1]]

                tags_all += parents
                # Stop if we have enough tags already, unless we need to find
                # the most specific tag (instead of the most popular).
                if (
                    not self.config["prefer_specific"]
                    and len(tags_all) >= count
                ):
                    break
            tags = tags_all

        tags = unique_list(tags)

        # Sort the tags by specificity.
        if self.config["prefer_specific"]:
            tags = self._sort_by_depth(tags)

        # c14n only adds allowed genres but we may have had forbidden genres in
        # the original tags list
        return [x for x in tags if self._is_valid(x)]

    def fetch_genre(self, lastfm_obj):
        """Return the genre for a pylast entity or None if no suitable genre
        can be found. Ex. 'Electronic, House, Dance'
        """
        min_weight = self.config["min_weight"].get(int)
        return self._tags_for(lastfm_obj, min_weight)

    def _is_valid(self, genre) -> bool:
        """Check if the genre is valid.

        Depending on the whitelist property, valid means a genre is in the
        whitelist or any genre is allowed.
        """
        if genre and (not self.whitelist or genre.lower() in self.whitelist):
            return True
        return False

    # Cached last.fm entity lookups.

    def _last_lookup(self, entity, method, *args):
        """Get a genre based on the named entity using the callable `method`
        whose arguments are given in the sequence `args`. The genre lookup
        is cached based on the entity name and the arguments.

        Before the lookup, each argument has some Unicode characters replaced
        with rough ASCII equivalents in order to return better results from the
        Last.fm database.
        """
        # Shortcut if we're missing metadata.
        if any(not s for s in args):
            return None

        key = f"{entity}.{'-'.join(str(a) for a in args)}"

        if key in self._genre_cache:
            return self._genre_cache[key]

        args_replaced = [
            "".join(arg.replace(k, v) for k, v in REPLACE.items())
            for arg in args
        ]
        self._genre_cache[key] = self.fetch_genre(method(*args_replaced))

        return self._genre_cache[key]

    def fetch_album_genre(self, obj):
        """Return the album genre for this Item or Album."""
        return self._last_lookup(
            "album", LASTFM.get_album, obj.albumartist, obj.album
        )

    def fetch_album_artist_genre(self, obj):
        """Return the album artist genre for this Item or Album."""
        return self._last_lookup("artist", LASTFM.get_artist, obj.albumartist)

    def fetch_artist_genre(self, item):
        """Returns the track artist genre for this Item."""
        return self._last_lookup("artist", LASTFM.get_artist, item.artist)

    def fetch_track_genre(self, obj):
        """Returns the track genre for this Item."""
        return self._last_lookup(
            "track", LASTFM.get_track, obj.artist, obj.title
        )

    # Main processing: _get_genre() and helpers.

    def _get_existing_genres(self, obj, separator):
        """Return a list of genres for this Item or Album."""
        if isinstance(obj, library.Item):
            item_genre = obj.get("genre", with_album=False).split(separator)
        else:
            item_genre = obj.get("genre").split(separator)

        if any(item_genre):
            return item_genre
        return []

    def _dedup_genres(self, genres, whitelist_only=False):
        """Return a list of deduplicated genres. Depending on the
        whitelist_only option, gives filtered or unfiltered results.
        Makes sure genres are handled all lower case."""
        if whitelist_only:
            return unique_list(
                [g.lower() for g in genres if self._is_valid(g)]
            )
        return unique_list([g.lower() for g in genres])

    def _combine_and_label_genres(
        self, new_genres: list, keep_genres: list, log_label: str
    ) -> tuple:
        """Combines genres and returns them with a logging label.

        Parameters:
            new_genres (list): The new genre result to process.
            keep_genres (list): Existing genres to combine with new ones
            log_label (str): A label (like "track", "album") we possibly
                combine with a prefix. For example resulting in something like
                "keep + track" or just "track".

        Returns:
            tuple: A tuple containing the combined genre string and the
            'logging label'.
        """
        self._log.debug(f"fetched last.fm tags: {new_genres}")
        combined = keep_genres + new_genres
        resolved = self._resolve_genres(combined)
        reduced = self._to_delimited_genre_string(resolved)

        if new_genres and keep_genres:
            return reduced, f"keep + {log_label}"
        if new_genres:
            return reduced, log_label
        return None, log_label

    def _get_genre(self, obj):
        """Get the final genre string for an Album or Item object

        `self.sources` specifies allowed genre sources, prioritized as follows:
            - track (for Items only)
            - album
            - artist
            - original
            - fallback
            - None

        Parameters:
            obj: Either an Album or Item object.

         Returns:
             tuple: A `(genre, label)` pair, where `label` is a string used for
                logging that describes the result. For example, "keep + artist"
                indicates that existing genres were combined with new last.fm
                genres, while "artist" means only new last.fm genres are
                included.
        """

        separator = self.config["separator"].get()
        keep_genres = []

        genres = self._get_existing_genres(obj, separator)
        if genres and not self.config["force"]:
            # Without force we don't touch pre-populated tags and return early
            # with the original contents. We deduplicate and format back to
            # string though.
            keep_genres = self._dedup_genres(genres)
            return separator.join(keep_genres), "keep"

        if self.config["force"]:
            # Simply forcing doesn't keep any.
            keep_genres = []
            # Remember existing genres if required. Whitelist validation is
            # handled later in _resolve_genres.
            if self.config["keep_existing"]:
                keep_genres = [g.lower() for g in genres]

        # Track genre (for Items only).
        if isinstance(obj, library.Item) and "track" in self.sources:
            if new_genres := self.fetch_track_genre(obj):
                return self._combine_and_label_genres(
                    new_genres, keep_genres, "track"
                )

        # Album genre.
        if "album" in self.sources:
            if new_genres := self.fetch_album_genre(obj):
                return self._combine_and_label_genres(
                    new_genres, keep_genres, "album"
                )

        # Artist (or album artist) genre.
        if "artist" in self.sources:
            new_genres = None
            if isinstance(obj, library.Item):
                new_genres = self.fetch_artist_genre(obj)
            elif obj.albumartist != config["va_name"].as_str():
                new_genres = self.fetch_album_artist_genre(obj)
            else:
                # For "Various Artists", pick the most popular track genre.
                item_genres = []
                for item in obj.items():
                    item_genre = None
                    if "track" in self.sources:
                        item_genre = self.fetch_track_genre(item)
                    if not item_genre:
                        item_genre = self.fetch_artist_genre(item)
                    if item_genre:
                        item_genres += item_genre
                if item_genres:
                    most_popular, rank = plurality(item_genres)
                    new_genres = [most_popular]
                    self._log.debug(
                        'Most popular track genre "{}" ({}) for VA album.',
                        most_popular,
                        rank,
                    )

            if new_genres:
                return self._combine_and_label_genres(
                    new_genres, keep_genres, "artist"
                )

        # Didn't find anything, leave original
        if obj.genre:
            return obj.genre, "original fallback"

        # No original, return fallback string
        if fallback := self.config["fallback"].get():
            return fallback, "fallback"

        # No fallback configured
        return None, None

    # Beets plugin hooks and CLI.

    def commands(self):
        lastgenre_cmd = ui.Subcommand("lastgenre", help="fetch genres")
        lastgenre_cmd.parser.add_option(
            "-f",
            "--force",
            dest="force",
            action="store_true",
            help="re-download genre when already present",
        )
        lastgenre_cmd.parser.add_option(
            "-k",
            "--keep-existing",
            dest="keep_existing",
            action="store_true",
            help="keep already present genres",
        )
        lastgenre_cmd.parser.add_option(
            "-K",
            "--keep-none",
            dest="keep_existing",
            action="store_false",
            help="don't keep already present genres",
        )
        lastgenre_cmd.parser.add_option(
            "-s",
            "--source",
            dest="source",
            type="string",
            help="genre source: artist, album, or track",
        )
        lastgenre_cmd.parser.add_option(
            "-A",
            "--items",
            action="store_false",
            dest="album",
            help="match items instead of albums",
        )
        lastgenre_cmd.parser.add_option(
            "-a",
            "--albums",
            action="store_true",
            dest="album",
            help="match albums instead of items",
        )
        lastgenre_cmd.parser.set_defaults(album=True)

        def lastgenre_func(lib, opts, args):
            write = ui.should_write()
            self.config.set_args(opts)

            if opts.album:
                # Fetch genres for whole albums
                for album in lib.albums(ui.decargs(args)):
                    album.genre, src = self._get_genre(album)
                    self._log.info(
                        'genre for album "{0.album}" ({1}): {0.genre}',
                        album,
                        src,
                    )
                    if "track" in self.sources:
                        album.store(inherit=False)
                    else:
                        album.store()

                    for item in album.items():
                        # If we're using track-level sources, also look up each
                        # track on the album.
                        if "track" in self.sources:
                            item.genre, src = self._get_genre(item)
                            item.store()
                            self._log.info(
                                'genre for track "{0.title}" ({1}): {0.genre}',
                                item,
                                src,
                            )

                        if write:
                            item.try_write()
            else:
                # Just query singletons, i.e. items that are not part of
                # an album
                for item in lib.items(ui.decargs(args)):
                    item.genre, src = self._get_genre(item)
                    item.store()
                    self._log.info(
                        "genre for track {0.title} ({1}): {0.genre}", item, src
                    )

        lastgenre_cmd.func = lastgenre_func
        return [lastgenre_cmd]

    def imported(self, session, task):
        """Event hook called when an import task finishes."""
        if task.is_album:
            album = task.album
            album.genre, src = self._get_genre(album)
            self._log.debug(
                'genre for album "{0.album}" ({1}): {0.genre}', album, src
            )

            # If we're using track-level sources, store the album genre only,
            # then also look up individual track genres.
            if "track" in self.sources:
                album.store(inherit=False)
                for item in album.items():
                    item.genre, src = self._get_genre(item)
                    self._log.debug(
                        'genre for track "{0.title}" ({1}): {0.genre}',
                        item,
                        src,
                    )
                    item.store()
            # Store the album genre and inherit to tracks.
            else:
                album.store()

        else:
            item = task.item
            item.genre, src = self._get_genre(item)
            self._log.debug(
                'genre for track "{0.title}" ({1}): {0.genre}',
                item,
                src,
            )
            item.store()

    def _tags_for(self, obj, min_weight=None):
        """Core genre identification routine.

        Given a pylast entity (album or track), return a list of
        tag names for that entity. Return an empty list if the entity is
        not found or another error occurs.

        If `min_weight` is specified, tags are filtered by weight.
        """
        # Work around an inconsistency in pylast where
        # Album.get_top_tags() does not return TopItem instances.
        # https://github.com/pylast/pylast/issues/86
        if isinstance(obj, pylast.Album):
            obj = super(pylast.Album, obj)

        try:
            res = obj.get_top_tags()
        except PYLAST_EXCEPTIONS as exc:
            self._log.debug("last.fm error: {0}", exc)
            return []
        except Exception as exc:
            # Isolate bugs in pylast.
            self._log.debug("{}", traceback.format_exc())
            self._log.error("error in pylast library: {0}", exc)
            return []

        # Filter by weight (optionally).
        if min_weight:
            res = [el for el in res if (int(el.weight or 0)) >= min_weight]

        # Get strings from tags.
        res = [el.item.get_name().lower() for el in res]

        return res
