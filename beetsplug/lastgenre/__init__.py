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

from __future__ import annotations

import os
import traceback
from functools import singledispatchmethod
from pathlib import Path
from typing import TYPE_CHECKING

import pylast
import yaml

from beets import config, library, plugins, ui
from beets.library import Album, Item
from beets.util import plurality, unique_list

if TYPE_CHECKING:
    from beets.library import LibModel

LASTFM = pylast.LastFMNetwork(api_key=plugins.LASTFM_KEY)

PYLAST_EXCEPTIONS = (
    pylast.WSError,
    pylast.MalformedResponseError,
    pylast.NetworkError,
)


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
                "force": False,
                "keep_existing": False,
                "auto": True,
                "separator": ", ",
                "prefer_specific": False,
                "title_case": True,
                "pretend": False,
            }
        )
        self.setup()

    def setup(self):
        """Setup plugin from config options"""
        if self.config["auto"]:
            self.import_stages = [self.imported]

        self._genre_cache = {}
        self.whitelist = self._load_whitelist()
        self.c14n_branches, self.canonicalize = self._load_c14n_tree()

    def _load_whitelist(self) -> set[str]:
        """Load the whitelist from a text file.

        Default whitelist is used if config is True, empty string or set to "nothing".
        """
        whitelist = set()
        wl_filename = self.config["whitelist"].get()
        if wl_filename in (True, "", None):  # Indicates the default whitelist.
            wl_filename = WHITELIST
        if wl_filename:
            self._log.debug("Loading whitelist {}", wl_filename)
            text = Path(wl_filename).expanduser().read_text(encoding="utf-8")
            for line in text.splitlines():
                if (line := line.strip().lower()) and not line.startswith("#"):
                    whitelist.add(line)

        return whitelist

    def _load_c14n_tree(self) -> tuple[list[list[str]], bool]:
        """Load the canonicalization tree from a YAML file.

        Default tree is used if config is True, empty string, set to "nothing"
        or if prefer_specific is enabled.
        """
        c14n_branches: list[list[str]] = []
        c14n_filename = self.config["canonical"].get()
        canonicalize = c14n_filename is not False
        # Default tree
        if c14n_filename in (True, "", None) or (
            # prefer_specific requires a tree, load default tree
            not canonicalize and self.config["prefer_specific"].get()
        ):
            c14n_filename = C14N_TREE
        # Read the tree
        if c14n_filename:
            self._log.debug("Loading canonicalization tree {}", c14n_filename)
            with Path(c14n_filename).expanduser().open(encoding="utf-8") as f:
                genres_tree = yaml.safe_load(f)
            flatten_tree(genres_tree, [], c14n_branches)
        return c14n_branches, canonicalize

    def _tunelog(self, msg, *args, **kwargs):
        """Log tuning messages at DEBUG level when verbosity level is high enough."""
        if config["verbose"].as_number() >= 3:
            self._log.debug(msg, *args, **kwargs)

    @property
    def sources(self) -> tuple[str, ...]:
        """A tuple of allowed genre sources. May contain 'track',
        'album', or 'artist.'
        """
        source = self.config["source"].as_choice(("track", "album", "artist"))
        if source == "track":
            return "track", "album", "artist"
        if source == "album":
            return "album", "artist"
        if source == "artist":
            return ("artist",)
        return tuple()

    # More canonicalization and general helpers.

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

    def _resolve_genres(self, tags: list[str]) -> list[str]:
        """Canonicalize, sort and filter a list of genres.

        - Returns an empty list if the input tags list is empty.
        - If canonicalization is enabled, it extends the list by incorporating
          parent genres from the canonicalization tree. When a whitelist is set,
          only parent tags that pass a validity check (_is_valid) are included;
          otherwise, it adds the oldest ancestor. Adding parent tags is stopped
          when the count of tags reaches the configured limit (count).
        - The tags list is then deduplicated to ensure only unique genres are
          retained.
        - If the 'prefer_specific' configuration is enabled, the list is sorted
          by the specificity (depth in the canonicalization tree) of the genres.
        - Finally applies whitelist filtering to ensure that only valid
          genres are kept. (This may result in no genres at all being retained).
        - Returns the filtered list of genres, limited to the configured count.
        """
        if not tags:
            return []

        count = self.config["count"].get(int)

        # Canonicalization (if enabled)
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
        valid_tags = [t for t in tags if self._is_valid(t)]
        return valid_tags[:count]

    def fetch_genre(self, lastfm_obj):
        """Return the genre for a pylast entity or None if no suitable genre
        can be found. Ex. 'Electronic, House, Dance'
        """
        min_weight = self.config["min_weight"].get(int)
        return self._tags_for(lastfm_obj, min_weight)

    def _is_valid(self, genre: str) -> bool:
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

        Before the lookup, each argument has the "-" Unicode character replaced
        with its rough ASCII equivalents in order to return better results from
        the Last.fm database.
        """
        # Shortcut if we're missing metadata.
        if any(not s for s in args):
            return []

        key = f"{entity}.{'-'.join(str(a) for a in args)}"
        if key not in self._genre_cache:
            args = [a.replace("\u2010", "-") for a in args]
            self._genre_cache[key] = self.fetch_genre(method(*args))

        genre = self._genre_cache[key]
        self._tunelog("last.fm (unfiltered) {} tags: {}", entity, genre)
        return genre

    def fetch_album_genre(self, obj):
        """Return raw album genres from Last.fm for this Item or Album."""
        return self._last_lookup(
            "album", LASTFM.get_album, obj.albumartist, obj.album
        )

    def fetch_album_artist_genre(self, obj):
        """Return raw album artist genres from Last.fm for this Item or Album."""
        return self._last_lookup("artist", LASTFM.get_artist, obj.albumartist)

    def fetch_artist_genre(self, item):
        """Returns raw track artist genres from Last.fm for this Item."""
        return self._last_lookup("artist", LASTFM.get_artist, item.artist)

    def fetch_track_genre(self, obj):
        """Returns raw track genres from Last.fm for this Item."""
        return self._last_lookup(
            "track", LASTFM.get_track, obj.artist, obj.title
        )

    # Main processing: _get_genre() and helpers.

    def _format_and_stringify(self, tags: list[str]) -> str:
        """Format to title_case if configured and return as delimited string."""
        if self.config["title_case"]:
            formatted = [tag.title() for tag in tags]
        else:
            formatted = tags

        return self.config["separator"].as_str().join(formatted)

    def _get_existing_genres(self, obj: LibModel) -> list[str]:
        """Return a list of genres for this Item or Album. Empty string genres
        are removed."""
        separator = self.config["separator"].get()
        if isinstance(obj, library.Item):
            item_genre = obj.get("genre", with_album=False).split(separator)
        else:
            item_genre = obj.get("genre").split(separator)

        # Filter out empty strings
        return [g for g in item_genre if g]

    def _combine_resolve_and_log(
        self, old: list[str], new: list[str]
    ) -> list[str]:
        """Combine old and new genres and process via _resolve_genres."""
        self._log.debug("raw last.fm tags: {}", new)
        self._log.debug("existing genres taken into account: {}", old)
        combined = old + new
        return self._resolve_genres(combined)

    def _get_genre(self, obj: LibModel) -> tuple[str | None, ...]:
        """Get the final genre string for an Album or Item object.

        `self.sources` specifies allowed genre sources. Starting with the first
        source in this tuple, the following stages run through until a genre is
        found or no options are left:
            - track (for Items only)
            - album
            - artist, albumartist or "most popular track genre" (for VA-albums)
            - original fallback
            - configured fallback
            - None

        A `(genre, label)` pair is returned, where `label` is a string used for
        logging. For example, "keep + artist, whitelist" indicates that existing
        genres were combined with new last.fm genres and whitelist filtering was
        applied, while "artist, any" means only new last.fm genres are included
        and the whitelist feature was disabled.
        """

        def _try_resolve_stage(stage_label: str, keep_genres, new_genres):
            """Try to resolve genres for a given stage and log the result."""
            resolved_genres = self._combine_resolve_and_log(
                keep_genres, new_genres
            )
            if resolved_genres:
                suffix = "whitelist" if self.whitelist else "any"
                label = f"{stage_label}, {suffix}"
                if keep_genres:
                    label = f"keep + {label}"
                return self._format_and_stringify(resolved_genres), label
            return None

        keep_genres = []
        new_genres = []
        genres = self._get_existing_genres(obj)

        if genres and not self.config["force"]:
            # Without force pre-populated tags are returned as-is.
            label = "keep any, no-force"
            if isinstance(obj, library.Item):
                return obj.get("genre", with_album=False), label
            return obj.get("genre"), label

        if self.config["force"]:
            # Force doesn't keep any unless keep_existing is set.
            # Whitelist validation is handled in _resolve_genres.
            if self.config["keep_existing"]:
                keep_genres = [g.lower() for g in genres]

        # Run through stages: track, album, artist,
        # album artist, or most popular track genre.
        if isinstance(obj, library.Item) and "track" in self.sources:
            if new_genres := self.fetch_track_genre(obj):
                if result := _try_resolve_stage(
                    "track", keep_genres, new_genres
                ):
                    return result

        if "album" in self.sources:
            if new_genres := self.fetch_album_genre(obj):
                if result := _try_resolve_stage(
                    "album", keep_genres, new_genres
                ):
                    return result

        if "artist" in self.sources:
            new_genres = []
            if isinstance(obj, library.Item):
                new_genres = self.fetch_artist_genre(obj)
                stage_label = "artist"
            elif obj.albumartist != config["va_name"].as_str():
                new_genres = self.fetch_album_artist_genre(obj)
                stage_label = "album artist"
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
                    stage_label = "most popular track"
                    self._log.debug(
                        'Most popular track genre "{}" ({}) for VA album.',
                        most_popular,
                        rank,
                    )

            if new_genres:
                if result := _try_resolve_stage(
                    stage_label, keep_genres, new_genres
                ):
                    return result

        # Nothing found, leave original if configured and valid.
        if obj.genre and self.config["keep_existing"]:
            if not self.whitelist or self._is_valid(obj.genre.lower()):
                return obj.genre, "original fallback"

        # Return fallback string.
        if fallback := self.config["fallback"].get():
            return fallback, "fallback"

        # No fallback configured.
        return None, "fallback unconfigured"

    # Beets plugin hooks and CLI.

    def _fetch_and_log_genre(self, obj: LibModel) -> None:
        """Fetch genre and log it."""
        self._log.info(str(obj))
        obj.genre, label = self._get_genre(obj)
        self._log.debug("Resolved ({}): {}", label, obj.genre)

        ui.show_model_changes(obj, fields=["genre"], print_obj=False)

    @singledispatchmethod
    def _process(self, obj: LibModel, write: bool) -> None:
        """Process an object, dispatching to the appropriate method."""
        raise NotImplementedError

    @_process.register
    def _process_track(self, obj: Item, write: bool) -> None:
        """Process a single track/item."""
        self._fetch_and_log_genre(obj)
        if not self.config["pretend"]:
            obj.try_sync(write=write, move=False)

    @_process.register
    def _process_album(self, obj: Album, write: bool) -> None:
        """Process an entire album."""
        self._fetch_and_log_genre(obj)
        if "track" in self.sources:
            for item in obj.items():
                self._process(item, write)

        if not self.config["pretend"]:
            obj.try_sync(
                write=write, move=False, inherit="track" not in self.sources
            )

    def commands(self):
        lastgenre_cmd = ui.Subcommand("lastgenre", help="fetch genres")
        lastgenre_cmd.parser.add_option(
            "-p",
            "--pretend",
            action="store_true",
            help="show actions but do nothing",
        )
        lastgenre_cmd.parser.add_option(
            "-f",
            "--force",
            dest="force",
            action="store_true",
            help="modify existing genres",
        )
        lastgenre_cmd.parser.add_option(
            "-F",
            "--no-force",
            dest="force",
            action="store_false",
            help="don't modify existing genres",
        )
        lastgenre_cmd.parser.add_option(
            "-k",
            "--keep-existing",
            dest="keep_existing",
            action="store_true",
            help="combine with existing genres when modifying",
        )
        lastgenre_cmd.parser.add_option(
            "-K",
            "--no-keep-existing",
            dest="keep_existing",
            action="store_false",
            help="don't combine with existing genres when modifying",
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
            help="match albums instead of items (default)",
        )
        lastgenre_cmd.parser.set_defaults(album=True)

        def lastgenre_func(lib, opts, args):
            self.config.set_args(opts)

            method = lib.albums if opts.album else lib.items
            for obj in method(args):
                self._process(obj, write=ui.should_write())

        lastgenre_cmd.func = lastgenre_func
        return [lastgenre_cmd]

    def imported(self, session, task):
        self._process(task.album if task.is_album else task.item, write=False)

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
            self._log.debug("last.fm error: {}", exc)
            return []
        except Exception as exc:
            # Isolate bugs in pylast.
            self._log.debug("{}", traceback.format_exc())
            self._log.error("error in pylast library: {}", exc)
            return []

        # Filter by weight (optionally).
        if min_weight:
            res = [el for el in res if (int(el.weight or 0)) >= min_weight]

        # Get strings from tags.
        res = [el.item.get_name().lower() for el in res]

        return res
