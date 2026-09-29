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
from functools import cached_property, singledispatchmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import confuse
import yaml

from beets import config, library, plugins, ui
from beets.library import Album, Item
from beets.util import plurality, unique_list
from beetsplug.lastgenre.utils import is_ignored, normalize_genre

from .client import LastFmClient

if TYPE_CHECKING:
    from collections.abc import Iterable

    from beets.importer import ImportSession, ImportTask
    from beets.library import LibModel

    from .utils import AliasPatternWithReplacement, IgnorePatternsByArtist

    Whitelist = set[str]
    """Set of valid genre names (lowercase). Empty set means all genres allowed."""

    CanonTree = list[list[str]]
    #: Genre hierarchy as list of paths from general to specific.
    #: Example: [['electronic', 'house'], ['electronic', 'techno']]

    GenresWithLabel = tuple[list[str], str]
    #: A pair of ``(genre list, label)`` returned by a genre resolution stage.
    #: The label is used for logging and describes the source and filtering applied.


class LastGenreCLIOpts(Protocol):
    album: bool


# Canonicalization tree processing.


def flatten_tree(
    elem: dict[Any, Any] | list[Any] | str, path: list[str], branches: CanonTree
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
ALIASES_FILE = os.path.join(os.path.dirname(__file__), "aliases.yaml")


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
                "aliases": True,
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
        self.ignore_patterns: IgnorePatternsByArtist = self._load_ignorelist()
        self.alias_patterns: list[AliasPatternWithReplacement] = (
            self._load_aliases()
        )
        self.client = LastFmClient(
            self._log,
            self.config["min_weight"].get(int),
            self.ignore_patterns,
            self.alias_patterns,
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

    def _load_ignorelist(self) -> IgnorePatternsByArtist:
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

        compiled_ignorelist: IgnorePatternsByArtist = defaultdict(list)
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

            compiled_ignorelist[artist.lower()] = artist_patterns

        return compiled_ignorelist

    def _load_aliases(self) -> list[AliasPatternWithReplacement]:
        """Load the genre alias table from the beets config.

        ``lastgenre.aliases`` is a tri-state option:

        - ``yes`` (default): load the built-in aliases.
        - ``no``: disable alias normalization entirely.
        - mapping: an inline dict of canonical genre names to lists of regex
          patterns.

        The key (genre name) is used as a ``re.Match.expand()`` template,
        so ``\\1`` / ``\\g<N>`` back-references to capture groups are supported.

        Raises:
            confuse.ConfigTypeError: when the config value is not a bool or
            mapping, or when a mapping value is not a list.
            re.error: when a pattern is not valid regex syntax.
        """
        aliases_config = self.config["aliases"].get()
        if aliases_config is False:
            return []

        # Define view with either built-in or user-configured
        aliases_view = confuse.Configuration(
            self.config["aliases"].name, read=False
        )
        if aliases_config in (True, "", None):
            self._log.debug("Loading built-in aliases")
            with Path(ALIASES_FILE).open(encoding="utf-8") as f:
                aliases_view.set(yaml.safe_load(f))
        elif not isinstance(aliases_config, dict):
            raise confuse.ConfigTypeError(
                f"{self.config['aliases'].name} must be a dict or bool."
            )
        else:
            aliases_view.set(aliases_config)

        # Parse and compile. Raise for invalid regex!
        raw_aliases = aliases_view.get(
            confuse.MappingValues(confuse.Sequence(str))
        )
        compiled_aliases: list[AliasPatternWithReplacement] = []
        for canonical, patterns in raw_aliases.items():
            lower_canonical = canonical.lower()
            compiled_aliases.extend(
                (re.compile(p, re.IGNORECASE), lower_canonical)
                for p in patterns
            )

        self._log.debug("Loaded {} alias entries", len(compiled_aliases))
        return compiled_aliases

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
        - If aliases are configured, variant spellings are normalised first
          (e.g. 'hip-hop' → 'hip hop', 'dnb' → 'drum and bass').
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

        # Normalize variant spellings before any other processing.
        if self.alias_patterns:
            tags = [
                normalize_genre(self._log, self.alias_patterns, tag)
                for tag in tags
            ]

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
                        find_parents(tag, self.c14n_branches), artist=artist
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

        Strips leading/trailing whitespace and drops empty strings, then
        applies whitelist and ignorelist checks. Whitelist is checked first
        for performance reasons (ignorelist regex matching is more expensive
        and for some call sites ignored genres were already filtered).
        """
        non_blank = [s for g in genres if (s := g.strip())]
        return [
            g
            for g in non_blank
            if (not self.whitelist or g.lower() in self.whitelist)
            and not is_ignored(self._log, self.ignore_patterns, g, artist)
        ]

    # Genre resolution pipeline.

    def _format_genres(self, tags: list[str]) -> list[str]:
        """Format to title case if configured."""
        if self.config["title_case"]:
            return [tag.title() for tag in tags]
        return tags

    def _artist_for_filter(self, obj: LibModel) -> str | None:
        """Return the representative artist for genre resolution and filtering."""
        return (
            obj.artist
            if isinstance(obj, library.Item)
            else obj.albumartist or obj.get("artist")
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

    @cached_property
    def fallback(self) -> GenresWithLabel:
        """Return the configured fallback genre and label."""
        if fallback := self.config["fallback"].get():
            return [fallback], "fallback"
        return [], "fallback unconfigured"

    def _try_resolve_stage(
        self,
        stage_label: str,
        keep_genres: list[str],
        new_genres: list[str],
        artist: str | None = None,
    ) -> GenresWithLabel | None:
        """Try to resolve genres for a given stage and log the result.

        If any newly fetched genres and/or existing genres are resolved, return
        a tuple of the resolved genres and a label describing the source and
        filtering applied. Otherwise, return ``None``.
        """
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

    def _try_resolve_existing_genres(
        self, obj: LibModel, genres: list[str]
    ) -> GenresWithLabel | None:
        """Handle existing genres when not forcing.

        Clean up existing genres if enabled, or return them unchanged. Return
        ``None`` if cleanup is enabled but fails to resolve, leaving fallback
        handling to the caller.
        """
        if self.config["cleanup_existing"]:
            keep_genres = [g.lower() for g in genres]
            return self._try_resolve_stage(
                "cleanup", keep_genres, [], artist=self._artist_for_filter(obj)
            )

        return genres, "keep any, no-force"  # type: ignore

    def _try_resolve_original_fallback(
        self, obj: LibModel, genres: list[str], keep_genres: list[str]
    ) -> GenresWithLabel | None:
        """Attempt to fall back to existing original genres if configured.

        ``genres`` are the original unchanged values and are checked as-is
        first, then ``keep_genres`` are used for a lowercased canonicalization
        retry.
        """
        if genres and self.config["keep_existing"].get():
            artist = self._artist_for_filter(obj)
            if valid_genres := self._filter_valid(genres, artist=artist):
                return valid_genres, "original fallback"
            # If the original genre doesn't match a whitelisted genre, check
            # if we can canonicalize it to find a matching, whitelisted genre!
            if resolved := self._try_resolve_stage(
                "original fallback", keep_genres, [], artist=artist
            ):
                return resolved
        return None

    def _fetch_va_genres(self, album: Album) -> list[str]:
        """Fetch the most popular track or artist genre for a Various Artists album."""
        item_genres = []
        for item in album.items():
            item_genre = None
            if "track" in self.sources:
                item_genre = self.client.fetch("track", item)
            if not item_genre:
                item_genre = self.client.fetch("artist", item)
            if item_genre:
                item_genres += item_genre

        if item_genres:
            most_popular, rank = plurality(item_genres)
            self._log.debug(
                'Most popular track genre "{}" ({}) for VA album.',
                most_popular,
                rank,
            )
            return [most_popular]

        return []

    def _fetch_artist_stage(
        self, obj: LibModel
    ) -> tuple[str, list[str], str | None]:
        """Fetch artist genres for an Item or Album object.

        Return a tuple of ``(stage_label, genres, stage_artist)``.
        """
        if isinstance(obj, library.Item):
            return "artist", self.client.fetch("artist", obj), obj.artist

        if obj.albumartist != config["va_name"].as_str():
            new_genres = self.client.fetch("album_artist", obj)
            if new_genres:
                return "album artist", new_genres, obj.albumartist

            self._log.extra_debug(
                'No album artist genre found for "{}", '
                "trying multi-valued field...",
                obj.albumartist,
            )
            for albumartist in obj.albumartists:
                self._log.extra_debug(
                    'Fetching artist genre for "{}"', albumartist
                )
                new_genres += self.client.fetch(
                    "album_artist", obj, albumartist
                )
            if new_genres:
                # Already filtered per-artist in client
                return "multi-valued album artist", new_genres, None
            return "album artist", [], None

        # For "Various Artists", pick the most popular track genre.
        assert isinstance(obj, Album)  # Type narrowing for mypy
        if va_genres := self._fetch_va_genres(obj):
            return "most popular track", va_genres, None

        return "most popular track", [], None

    def _get_genre(self, obj: LibModel) -> GenresWithLabel:
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

        new_genres = []
        existing_genres = self._get_existing_genres(obj)

        if existing_genres and not self.config["force"]:
            if resolved := self._try_resolve_existing_genres(
                obj, existing_genres
            ):
                return resolved
            return self.fallback

        keep_genres = (
            [g.lower() for g in existing_genres]
            if self.config["keep_existing"] and self.config["force"]
            else []
        )

        # Run through stages: track, album, artist,
        # album artist, or most popular track genre.
        if isinstance(obj, library.Item) and "track" in self.sources:
            if new_genres := self.client.fetch("track", obj):
                if resolved := self._try_resolve_stage(
                    "track", keep_genres, new_genres, artist=obj.artist
                ):
                    return resolved

        if "album" in self.sources:
            if new_genres := self.client.fetch("album", obj):
                if resolved := self._try_resolve_stage(
                    "album", keep_genres, new_genres, artist=obj.albumartist
                ):
                    return resolved

        if "artist" in self.sources:
            stage_label, new_genres, stage_artist = self._fetch_artist_stage(
                obj
            )
            if new_genres:
                if resolved := self._try_resolve_stage(
                    stage_label, keep_genres, new_genres, artist=stage_artist
                ):
                    return resolved

        if resolved := self._try_resolve_original_fallback(
            obj, existing_genres, keep_genres
        ):
            return resolved

        return self.fallback

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
            lib: library.Library, opts: LastGenreCLIOpts, args: list[str]
        ) -> None:
            self.config.set_args(vars(opts))

            method = lib.albums if opts.album else lib.items
            for obj in method(args):
                self._process(obj, write=ui.should_write())

        lastgenre_cmd.func = lastgenre_func
        return [lastgenre_cmd]

    def imported(self, _: ImportSession, task: ImportTask) -> None:
        self._process(task.album if task.is_album else task.item, write=False)  # type: ignore[attr-defined]
