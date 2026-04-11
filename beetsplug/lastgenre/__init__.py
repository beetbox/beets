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
import re
from collections import defaultdict
from functools import singledispatchmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import confuse
import yaml

from beets import config, library, plugins, ui
from beets.library import Album, Item
from beets.util import plurality, unique_list
from beetsplug.lastgenre.utils import drop_ignored_genres, is_ignored

from .client import LastFmClient

if TYPE_CHECKING:
    import optparse
    from collections.abc import Iterable

    from beets.importer import ImportSession, ImportTask
    from beets.library import LibModel

    from .utils import GenreIgnorePatterns

    Whitelist = set[str]
    """Set of valid genre names (lowercase). Empty set means all genres allowed."""

    CanonTree = list[list[str]]
    """Genre hierarchy as list of paths from general to specific.
    Example: [['electronic', 'house'], ['electronic', 'techno']]"""


# Canonicalization tree processing.


def flatten_tree(
    elem: dict[Any, Any] | list[Any] | str,
    path: list[str],
    branches: CanonTree,
) -> None:
    """Flatten nested lists/dictionaries into lists of strings
    (branches).
    """
    if not path:
        path = []

    if isinstance(elem, dict):
        for k, v in elem.items():
            flatten_tree(v, [*path, k], branches)
    elif isinstance(elem, list):
        for sub in elem:
            flatten_tree(sub, path, branches)
    else:
        branches.append([*path, str(elem)])


def find_parents(candidate: str, branches: CanonTree) -> list[str]:
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


def get_depth(tag: str, branches: CanonTree) -> int | None:
    """Find the depth of a tag in the genres tree."""
    for branch in branches:
        if tag in branch:
            return branch.index(tag)
    return None


def sort_by_depth(tags: list[str], branches: CanonTree) -> list[str]:
    """Given a list of tags, sort the tags by their depths in the genre tree."""
    depth_tag_pairs = [(get_depth(t, branches), t) for t in tags]
    depth_tag_pairs = [e for e in depth_tag_pairs if e[0] is not None]
    depth_tag_pairs.sort(reverse=True)
    return [p[1] for p in depth_tag_pairs]


# Main plugin logic.

WHITELIST = os.path.join(os.path.dirname(__file__), "genres.txt")
C14N_TREE = os.path.join(os.path.dirname(__file__), "genres-tree.yaml")


class LastGenrePlugin(plugins.BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()

        self.config.add(
            {
                "whitelist": True,
                "min_weight": 10,
                "count": 1,
                "fallback": None,
                "canonical": False,
                "cleanup_existing": False,
                "source": "album",
                "force": False,
                "keep_existing": False,
                "auto": True,
                "prefer_specific": False,
                "title_case": True,
                "pretend": False,
                "ignorelist": {},
            }
        )
        self.setup()

    def setup(self) -> None:
        """Setup plugin from config options"""
        if self.config["auto"]:
            self.import_stages = [self.imported]

        self.whitelist: Whitelist = self._load_whitelist()
        self.c14n_branches: CanonTree
        self.c14n_branches, self.canonicalize = self._load_c14n_tree()
        self.ignore_patterns: GenreIgnorePatterns = self._load_ignorelist()
        self.client = LastFmClient(
            self._log, self.config["min_weight"].get(int), self.ignore_patterns
        )

    def _load_whitelist(self) -> Whitelist:
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

    def _load_c14n_tree(self) -> tuple[CanonTree, bool]:
        """Load the canonicalization tree from a YAML file.

        Default tree is used if config is True, empty string, set to "nothing"
        or if prefer_specific is enabled.
        """
        c14n_branches: CanonTree = []
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

    def _load_ignorelist(self) -> GenreIgnorePatterns:
        r"""Load patterns from configuration and compile them.

        Mapping of artist names to regex or literal patterns. Use the
        quoted ``'*'`` key to define globally ignored genres::

            lastgenre:
                ignorelist:
                    '*':
                        - spoken word
                        - comedy
                    Artist Name:
                        - .*rock.*
                        - .*metal.*

        Matching is case-insensitive and full-match. Because patterns are
        parsed as plain YAML scalars, backslashes (e.g. ``\w``) should
        not be double-escaped. Quotes are primarily needed for special
        YAML characters (e.g., ``*`` or ``[``); prefer single-quotes.

        Raises:
            Several confuse.ConfigError's that tell the user about the expected
            format when the config is invalid.
        """
        if not self.config["ignorelist"].get():
            return {}

        raw_ignorelist = self.config["ignorelist"].get(
            confuse.MappingValues(confuse.Sequence(str))
        )

        compiled_ignorelist: GenreIgnorePatterns = defaultdict(list)
        for artist, patterns in raw_ignorelist.items():
            artist_patterns = []
            for pattern in patterns:
                try:
                    artist_patterns.append(re.compile(pattern, re.IGNORECASE))
                except re.error:
                    artist_patterns.append(
                        re.compile(re.escape(pattern), re.IGNORECASE)
                    )
            self._log.extra_debug(
                "ignore for {}: {}",
                artist,
                [p.pattern for p in artist_patterns],
            )

            compiled_ignorelist[artist] = artist_patterns

        return compiled_ignorelist

    @property
    def sources(self) -> tuple[str, ...]:
        """A tuple of allowed genre sources. May contain 'track',
        'album', or 'artist.'
        """
        return self.config["source"].as_choice(
            {
                "track": ("track", "album", "artist"),
                "album": ("album", "artist"),
                "artist": ("artist",),
            }
        )

    # Genre list processing.

    def _resolve_genres(
        self, tags: list[str], artist: str | None = None
    ) -> list[str]:
        """Canonicalize, sort and filter a list of genres.

        - Returns an empty list if the input tags list is empty.
        - If canonicalization is enabled, it extends the list by incorporating
          parent genres from the canonicalization tree. When a whitelist is set,
          only parent tags that pass the whitelist filter are included;
          otherwise, it adds the oldest ancestor. Adding parent tags is stopped
          when the count of tags reaches the configured limit (count).
        - The tags list is then deduplicated to ensure only unique genres are
          retained.
        - If the 'prefer_specific' configuration is enabled, the list is sorted
          by the specificity (depth in the canonicalization tree) of the genres.
        - Finally applies whitelist filtering to ensure that only valid
          genres are kept. (This may result in no genres at all being retained).
        - Ignorelist is applied at each stage: ignored input tags skip ancestry
          entirely, ignored ancestor tags are dropped, and ignored tags are
          removed in the final filter.
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
                # Skip ignored tags entirely — don't walk their ancestry.
                if is_ignored(self._log, self.ignore_patterns, tag, artist):
                    continue

                # Add parents that pass whitelist (and are not ignored, which
                # is checked in _filter_valid). With whitelist, we may include
                # multiple parents
                if self.whitelist:
                    parents = self._filter_valid(
                        find_parents(tag, self.c14n_branches),
                        artist=artist,
                    )
                else:
                    # No whitelist: take only the oldest ancestor, skipping it
                    # if it is in the ignorelist
                    oldest = find_parents(tag, self.c14n_branches)[-1]
                    parents = (
                        []
                        if is_ignored(
                            self._log, self.ignore_patterns, oldest, artist
                        )
                        else [oldest]
                    )

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
            tags = sort_by_depth(tags, self.c14n_branches)

        # Final filter: applies when c14n is disabled, or when c14n ran without
        # whitelist filtering in the loop (no-whitelist path).
        valid_tags = self._filter_valid(tags, artist=artist)
        return valid_tags[:count]

    def _filter_valid(
        self, genres: Iterable[str], artist: str | None = None
    ) -> list[str]:
        """Filter genres through whitelist and ignorelist.

        Drops empty/whitespace-only strings, then applies whitelist and
        ignorelist checks. Returns all genres if neither is configured.
        Whitelist is checked first for performance reasons (ignorelist regex
        matching is more expensive and for some call sites ignored genres were
        already filtered).
        """
        cleaned = [g for g in genres if g and g.strip()]
        if not self.whitelist and not self.ignore_patterns:
            return cleaned

        whitelisted = [
            g
            for g in cleaned
            if not self.whitelist or g.lower() in self.whitelist
        ]
        return drop_ignored_genres(
            self._log, self.ignore_patterns, whitelisted, artist
        )

    # Genre resolution pipeline.

    def _format_genres(self, tags: list[str]) -> list[str]:
        """Format to title case if configured."""
        if self.config["title_case"]:
            return [tag.title() for tag in tags]
        else:
            return tags

    def _artist_for_filter(self, obj: LibModel) -> str | None:
        """Return the representative artist for genre resolution and filtering."""
        return (
            obj.artist
            if isinstance(obj, library.Item)
            else obj.albumartist or obj.artist
        )

    def _get_existing_genres(self, obj: LibModel) -> list[str]:
        """Return a list of genres for this Item or Album."""
        if isinstance(obj, library.Item):
            genres_list = obj.get("genres", with_album=False)
        else:
            genres_list = obj.get("genres")

        return genres_list

    def _combine_resolve_and_log(
        self, old: list[str], new: list[str], artist: str | None = None
    ) -> list[str]:
        """Combine old and new genres and process via _resolve_genres."""
        self._log.debug("raw last.fm tags: {}", new)
        self._log.debug("existing genres taken into account: {}", old)
        combined = old + new
        return self._resolve_genres(combined, artist=artist)

    def _get_genre(self, obj: LibModel) -> tuple[list[str], str]:
        """Get the final genre list for an Album or Item object.

        `self.sources` specifies allowed genre sources. Starting with the first
        source in this tuple, the following stages run through until a genre is
        found or no options are left:
            - track (for Items only)
            - album
            - artist, albumartist or "most popular track genre" (for VA-albums)
            - original fallback
            - configured fallback
            - empty list

        A `(genres, label)` pair is returned, where `label` is a string used for
        logging. For example, "keep + artist, whitelist" indicates that existing
        genres were combined with new last.fm genres and whitelist filtering was
        applied, while "artist, any" means only new last.fm genres are included
        and the whitelist feature was disabled.
        """

        def _fallback_stage() -> tuple[list[str], str]:
            """Return the fallback genre and label."""
            if fallback := self.config["fallback"].get():
                return [fallback], "fallback"
            return [], "fallback unconfigured"

        def _try_resolve_stage(
            stage_label: str,
            keep_genres: list[str],
            new_genres: list[str],
            artist: str | None = None,
        ) -> tuple[list[str], str] | None:
            """Try to resolve genres for a given stage and log the result."""
            resolved_genres = self._combine_resolve_and_log(
                keep_genres, new_genres, artist=artist
            )
            if resolved_genres:
                suffix = "whitelist" if self.whitelist else "any"
                label = f"{stage_label}, {suffix}"
                if keep_genres:
                    label = f"keep + {label}"
                return self._format_genres(resolved_genres), label
            return None

        keep_genres = []
        new_genres = []
        genres = self._get_existing_genres(obj)

        if genres and not self.config["force"]:
            # Without force, but cleanup_existing enabled, we attempt
            # to canonicalize pre-populated tags before returning them.
            # If none are found, we use the fallback (if set).
            if self.config["cleanup_existing"]:
                keep_genres = [g.lower() for g in genres]
                if result := _try_resolve_stage(
                    "cleanup",
                    keep_genres,
                    [],
                    artist=self._artist_for_filter(obj),
                ):
                    return result

                return _fallback_stage()

            # If cleanup_existing is not set, the pre-populated tags are
            # returned as-is.
            return genres, "keep any, no-force"

        if self.config["force"]:
            # Force doesn't keep any unless keep_existing is set.
            # Whitelist validation is handled in _resolve_genres.
            if self.config["keep_existing"]:
                keep_genres = [g.lower() for g in genres]

        # Run through stages: track, album, artist,
        # album artist, or most popular track genre.
        if isinstance(obj, library.Item) and "track" in self.sources:
            if new_genres := self.client.fetch("track", obj):
                if result := _try_resolve_stage(
                    "track", keep_genres, new_genres, artist=obj.artist
                ):
                    return result

        if "album" in self.sources:
            if new_genres := self.client.fetch("album", obj):
                if result := _try_resolve_stage(
                    "album", keep_genres, new_genres, artist=obj.albumartist
                ):
                    return result

        if "artist" in self.sources:
            new_genres = []
            stage_artist: str | None = None
            if isinstance(obj, library.Item):
                new_genres = self.client.fetch("artist", obj)
                stage_label = "artist"
                stage_artist = obj.artist
            elif obj.albumartist != config["va_name"].as_str():
                new_genres = self.client.fetch("album_artist", obj)
                stage_label = "album artist"
                stage_artist = obj.albumartist
                if not new_genres:
                    self._log.extra_debug(
                        'No album artist genre found for "{}", '
                        "trying multi-valued field...",
                        obj.albumartist,
                    )
                    for albumartist in obj.albumartists:
                        self._log.extra_debug(
                            'Fetching artist genre for "{}"',
                            albumartist,
                        )
                        new_genres += self.client.fetch(
                            "album_artist", obj, albumartist
                        )
                    if new_genres:
                        stage_label = "multi-valued album artist"
                        stage_artist = (
                            None  # Already filtered per-artist in client
                        )
            else:
                # For "Various Artists", pick the most popular track genre.
                item_genres = []
                assert isinstance(obj, Album)  # Type narrowing for mypy
                for item in obj.items():
                    item_genre = None
                    if "track" in self.sources:
                        item_genre = self.client.fetch("track", item)
                    if not item_genre:
                        item_genre = self.client.fetch("artist", item)
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
                    stage_label, keep_genres, new_genres, artist=stage_artist
                ):
                    return result

        # Nothing found, leave original if configured and valid.
        if genres and self.config["keep_existing"].get():
            artist = self._artist_for_filter(obj)
            if valid_genres := self._filter_valid(genres, artist=artist):
                return valid_genres, "original fallback"
            # If the original genre doesn't match a whitelisted genre, check
            # if we can canonicalize it to find a matching, whitelisted genre!
            if result := _try_resolve_stage(
                "original fallback", keep_genres, [], artist=artist
            ):
                return result

        return _fallback_stage()

    # Beets plugin hooks and CLI.

    def _fetch_and_log_genre(self, obj: LibModel) -> None:
        """Fetch genre and log it."""
        self._log.info(str(obj))
        obj.genres, label = self._get_genre(obj)
        self._log.debug("Resolved ({}): {}", label, obj.genres)

        ui.show_model_changes(obj, fields=["genres"], print_obj=False)

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

    def commands(self) -> list[ui.Subcommand]:
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

        def lastgenre_func(
            lib: library.Library, opts: optparse.Values, args: list[str]
        ) -> None:
            self.config.set_args(opts)

            method = lib.albums if opts.album else lib.items
            for obj in method(args):
                self._process(obj, write=ui.should_write())

        lastgenre_cmd.func = lastgenre_func
        return [lastgenre_cmd]

    def imported(self, _: ImportSession, task: ImportTask) -> None:
        self._process(task.album if task.is_album else task.item, write=False)  # type: ignore[attr-defined]
