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

from functools import singledispatchmethod
from pathlib import Path
from typing import TYPE_CHECKING

from beets import config, library, plugins, ui
from beets.library import Album, Item
from beets.util import plurality, unique_list

from .client import LastFmClient
from .loaders import DataFileLoader
from .processing import GenreProcessor
from .utils import make_tunelog

if TYPE_CHECKING:
    import optparse

    from beets.library import LibModel

    from .types import CanonTree


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
                "source": "album",
                "force": False,
                "keep_existing": False,
                "auto": True,
                "separator": ", ",
                "prefer_specific": False,
                "title_case": True,
                "pretend": False,
                "blacklist": False,
            }
        )
        self.setup()

    def setup(self) -> None:
        """Setup plugin from config options"""
        if self.config["auto"].get(bool):
            self.import_stages = [self.imported]

        self._tunelog = make_tunelog(self._log)

        loader = DataFileLoader.from_config(
            self.config, self._log, Path(__file__).parent
        )
        self.processor = GenreProcessor(loader.whitelist, loader.blacklist)
        self.c14n_branches = loader.c14n_branches
        self.canonicalize = loader.canonicalize

        self.client = LastFmClient(
            self._log, self.config["min_weight"].get(int), self.processor
        )

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

    # Canonicalization and filtering.

    def _get_depth(self, tag: str) -> int | None:
        """Find the depth of a tag in the genres tree."""
        depth = None
        for key, value in enumerate(self.c14n_branches):
            if tag in value:
                depth = value.index(tag)
                break
        return depth

    def _sort_by_depth(self, tags: list[str]) -> list[str]:
        """Given a list of tags, sort the tags by their depths in the
        genre tree.
        """
        depth_tag_pairs = [(self._get_depth(t), t) for t in tags]
        depth_tag_pairs = [e for e in depth_tag_pairs if e[0] is not None]
        depth_tag_pairs.sort(reverse=True)
        return [p[1] for p in depth_tag_pairs]

    @staticmethod
    def find_parents(candidate: str, branches: CanonTree) -> list[str]:
        """Find parent genres of a given genre, ordered from closest to furthest."""
        for branch in branches:
            try:
                idx = branch.index(candidate.lower())
                return list(reversed(branch[: idx + 1]))
            except ValueError:
                continue
        return [candidate]

    def _resolve_genres(
        self, tags: list[str], artist: str | None = None
    ) -> list[str]:
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
                if self.processor.whitelist:
                    parents = [
                        x
                        for x in self.find_parents(tag, self.c14n_branches)
                        if self.processor.is_valid(x)
                    ]
                else:
                    parents = [self.find_parents(tag, self.c14n_branches)[-1]]

                tags_all += parents
                # Stop if we have enough tags already, unless we need to find
                # the most specific tag (instead of the most popular).
                if (
                    not self.config["prefer_specific"].get(bool)
                    and len(tags_all) >= count
                ):
                    break
            tags = tags_all

        tags = unique_list(tags)

        # Sort the tags by specificity.
        if self.config["prefer_specific"].get(bool):
            tags = self._sort_by_depth(tags)

        # c14n only adds allowed genres but we may have had forbidden genres in
        # the original tags list
        valid_tags = [
            t
            for t in tags
            if self.processor.is_valid(t)
            and not self.processor.is_forbidden(t, artist=artist)
        ]
        return valid_tags[:count]

    # Main processing: _get_genre() and helpers.

    def _format_and_stringify(self, tags: list[str]) -> str:
        """Format to title_case if configured and return as delimited string."""
        if self.config["title_case"].get(bool):
            formatted = [tag.title() for tag in tags]
        else:
            formatted = tags

        return self.config["separator"].as_str().join(formatted)

    def _get_existing_genres(self, obj: LibModel) -> list[str]:
        """Return a list of genres for this Item or Album. Empty string genres
        are removed."""
        separator = self.config["separator"].as_str()
        if isinstance(obj, library.Item):
            item_genre = obj.get("genre", with_album=False).split(separator)
        else:
            item_genre = obj.get("genre").split(separator)

        # Filter out empty strings
        return [g for g in item_genre if g]

    def _combine_resolve_and_log(
        self, old: list[str], new: list[str], artist: str | None = None
    ) -> list[str]:
        """Combine old and new genres and process via _resolve_genres."""
        self._log.debug("raw last.fm tags: {}", new)
        self._log.debug("existing genres taken into account: {}", old)
        combined = old + new
        return self._resolve_genres(combined, artist=artist)

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

        def _try_resolve_stage(
            stage_label: str, keep_genres: list[str], new_genres: list[str]
        ) -> tuple[str, str] | None:
            """Try to resolve genres for a given stage and log the result."""
            artist = getattr(obj, "albumartist", None) or getattr(
                obj, "artist", None
            )
            resolved_genres = self._combine_resolve_and_log(
                keep_genres, new_genres, artist=artist
            )
            if resolved_genres:
                suffix = "whitelist" if self.processor.whitelist else "any"
                label = f"{stage_label}, {suffix}"
                if keep_genres:
                    label = f"keep + {label}"
                return self._format_and_stringify(resolved_genres), label
            return None

        keep_genres = []
        new_genres = []
        genres = self._get_existing_genres(obj)

        if genres and not self.config["force"].get(bool):
            # Without force pre-populated tags are returned as-is.
            label = "keep any, no-force"
            if isinstance(obj, library.Item):
                return obj.get("genre", with_album=False), label
            return obj.get("genre"), label

        if self.config["force"].get(bool):
            # Force doesn't keep any unless keep_existing is set.
            # Whitelist validation is handled in _resolve_genres.
            if self.config["keep_existing"]:
                keep_genres = [g.lower() for g in genres]

        # Run through stages: track, album, artist,
        # album artist, or most popular track genre.
        if isinstance(obj, library.Item) and "track" in self.sources:
            if new_genres := self.client.fetch_track_genre(
                obj.artist, obj.title
            ):
                if result := _try_resolve_stage(
                    "track", keep_genres, new_genres
                ):
                    return result

        if "album" in self.sources:
            if new_genres := self.client.fetch_album_genre(
                obj.albumartist, obj.album
            ):
                if result := _try_resolve_stage(
                    "album", keep_genres, new_genres
                ):
                    return result

        if "artist" in self.sources:
            new_genres = []
            if isinstance(obj, library.Item):
                new_genres = self.client.fetch_artist_genre(obj.artist)
                stage_label = "artist"
            elif obj.albumartist != config["va_name"].as_str():
                new_genres = self.client.fetch_artist_genre(obj.albumartist)
                stage_label = "album artist"
                if not new_genres:
                    self._tunelog(
                        'No album artist genre found for "{}", '
                        "trying multi-valued field...",
                        obj.albumartist,
                    )
                    for albumartist in obj.albumartists:
                        self._tunelog(
                            'Fetching artist genre for "{}"',
                            albumartist,
                        )
                        new_genres += self.client.fetch_artist_genre(
                            albumartist
                        )
                    if new_genres:
                        stage_label = "multi-valued album artist"
            else:
                # For "Various Artists", pick the most popular track genre.
                item_genres = []
                assert isinstance(obj, Album)  # Type narrowing for mypy
                for item in obj.items():
                    item_genre = None
                    if "track" in self.sources:
                        item_genre = self.client.fetch_track_genre(
                            item.artist, item.title
                        )
                    if not item_genre:
                        item_genre = self.client.fetch_artist_genre(item.artist)
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
        if obj.genre and self.config["keep_existing"].get(bool):
            if not self.processor.whitelist or self.processor.is_valid(
                obj.genre.lower()
            ):
                return obj.genre, "original fallback"
            # If the original genre doesn't match a whitelisted genre, check
            # if we can canonicalize it to find a matching, whitelisted genre!
            if result := _try_resolve_stage(
                "original fallback", keep_genres, []
            ):
                return result

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
        if not self.config["pretend"].get(bool):
            obj.try_sync(write=write, move=False)

    @_process.register
    def _process_album(self, obj: Album, write: bool) -> None:
        """Process an entire album."""
        self._fetch_and_log_genre(obj)
        if "track" in self.sources:
            for item in obj.items():
                self._process(item, write)

        if not self.config["pretend"].get(bool):
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

    def imported(
        self, session: library.Session, task: library.ImportTask
    ) -> None:
        self._process(task.album if task.is_album else task.item, write=False)
