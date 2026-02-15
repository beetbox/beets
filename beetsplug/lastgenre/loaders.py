# This file is part of beets.
# Copyright 2016, Adrian Sampson.
# Copyright 2026, J0J0 Todos.
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


"""Data file loaders for the lastgenre plugin."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from beets.ui import UserError

from .utils import make_tunelog

if TYPE_CHECKING:
    from confuse import ConfigView

    from beets.logging import Logger

    from .types import Blacklist, CanonTree, RawBlacklist, Whitelist


class DataFileLoader:
    """Loads genre-related data files for the lastgenre plugin."""

    def __init__(
        self,
        log: Logger,
        plugin_dir: Path,
        whitelist: Whitelist,
        c14n_branches: CanonTree,
        canonicalize: bool,
        blacklist: Blacklist,
    ):
        """Initialize with pre-loaded data.

        Use from_config() classmethod to construct from plugin config.
        """
        self._log = log
        self._tunelog = make_tunelog(log)
        self._plugin_dir = plugin_dir
        self.whitelist = whitelist
        self.c14n_branches = c14n_branches
        self.canonicalize = canonicalize
        self.blacklist = blacklist

    @classmethod
    def from_config(
        cls,
        config: ConfigView,
        log: Logger,
        plugin_dir: Path,
    ) -> DataFileLoader:
        """Create a DataFileLoader from plugin configuration.

        Reads config values and loads all data files during construction.
        """
        # Default paths
        default_whitelist = str(plugin_dir / "genres.txt")
        default_tree = str(plugin_dir / "genres-tree.yaml")

        # Load whitelist
        whitelist = cls._load_whitelist(
            log, config["whitelist"].get(), default_whitelist
        )

        # Load tree
        c14n_branches, canonicalize = cls._load_tree(
            log,
            config["canonical"].get(),
            default_tree,
            config["prefer_specific"].get(bool),
        )

        # Load blacklist
        blacklist = cls._load_blacklist(log, config["blacklist"].get())

        return cls(
            log, plugin_dir, whitelist, c14n_branches, canonicalize, blacklist
        )

    @staticmethod
    def _load_whitelist(
        log: Logger, config_value: str | bool | None, default_path: str
    ) -> Whitelist:
        """Load the whitelist from a text file.

        Returns set of valid genre names (lowercase).
        """
        whitelist = set()
        wl_filename = config_value
        if wl_filename in (True, "", None):  # Indicates the default whitelist.
            wl_filename = default_path
        if wl_filename and isinstance(wl_filename, str):
            log.debug("Loading whitelist {}", wl_filename)
            text = Path(wl_filename).expanduser().read_text(encoding="utf-8")
            for line in text.splitlines():
                if (line := line.strip().lower()) and not line.startswith("#"):
                    whitelist.add(line)

        return whitelist

    @staticmethod
    def _load_tree(
        log: Logger,
        config_value: str | bool | None,
        default_path: str,
        prefer_specific: bool,
    ) -> tuple[CanonTree, bool]:
        """Load the canonicalization tree from a YAML file.

        Returns tuple of (branches, canonicalize_enabled).
        """
        c14n_branches: CanonTree = []
        c14n_filename = config_value
        canonicalize = c14n_filename is not False
        # Default tree
        if c14n_filename in (True, "", None) or (
            # prefer_specific requires a tree, load default tree
            not canonicalize and prefer_specific
        ):
            c14n_filename = default_path
        # Read the tree
        if c14n_filename and isinstance(c14n_filename, str):
            log.debug("Loading canonicalization tree {}", c14n_filename)
            with Path(c14n_filename).expanduser().open(encoding="utf-8") as f:
                genres_tree = yaml.safe_load(f)
            DataFileLoader.flatten_tree(genres_tree, [], c14n_branches)
        return c14n_branches, canonicalize

    @staticmethod
    def flatten_tree(
        elem: dict[str, Any] | list[Any] | str,
        path: list[str],
        branches: CanonTree,
    ) -> None:
        """Flatten nested YAML structure into genre hierarchy branches.

        Recursively converts nested dicts/lists from YAML into a flat list
        of genre paths, where each path goes from general to specific genre.

        Args:
            elem: The YAML element to process (dict, list, or string leaf).
            path: Current path from root to this element (used in recursion).
            branches: OUTPUT PARAMETER - Empty list that will be populated
                     with genre paths. Gets mutated by this method.

        Example:
            branches = []
            flatten_tree({'rock': ['indie', 'punk']}, [], branches)
            # branches is now: [['rock', 'indie'], ['rock', 'punk']]
        """
        if not path:
            path = []

        if isinstance(elem, dict):
            for k, v in elem.items():
                DataFileLoader.flatten_tree(v, [*path, k], branches)
        elif isinstance(elem, list):
            for sub in elem:
                DataFileLoader.flatten_tree(sub, path, branches)
        else:
            branches.append([*path, str(elem)])

    @staticmethod
    def _load_blacklist(
        log: Logger, config_value: str | bool | None
    ) -> Blacklist:
        """Load the blacklist from a configured file path.

        For maximum compatibility with regex patterns, a custom format is used:
        - Each section starts with an artist name, followed by a colon.
        - Subsequent lines are indented (at least one space, typically 4 spaces) and
          contain a regex pattern to match a genre.
        - A '*' key for artist can be used to specify global forbidden genres.

        Returns a compiled blacklist dictionary mapping artist names to lists of
        case-insensitive regex patterns.

        Example blacklist file format:
            Artist Name:
                .*rock.*
                .*metal.*
            Another Artist Name:
                ^jazz$
            *:
                spoken word
                comedy

        Raises:
            UserError: if the file format is invalid.
        """
        blacklist_raw: RawBlacklist = defaultdict(list)
        bl_filename = config_value
        if not bl_filename or not isinstance(bl_filename, str):
            return {}

        tunelog = make_tunelog(log)
        log.debug("Loading blacklist file {0}", bl_filename)
        section = None
        with Path(bl_filename).expanduser().open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.lower()
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if not line.startswith(" "):
                    # Section header
                    if not line.rstrip().endswith(":"):
                        raise UserError(
                            f"Malformed blacklist section header "
                            f"at line {lineno}: {line}"
                        )
                    section = line.rstrip(":\r\n")
                else:
                    # Pattern line: must be indented (at least one space)
                    if section is None:
                        raise UserError(
                            f"Blacklist regex pattern line before any section header "
                            f"at line {lineno}: {line}"
                        )
                    blacklist_raw[section].append(line.strip())
        tunelog("Blacklist: {}", blacklist_raw)

        # Compile regex patterns
        return DataFileLoader._compile_blacklist_patterns(blacklist_raw)

    @staticmethod
    def _compile_blacklist_patterns(
        blacklist: RawBlacklist,
    ) -> Blacklist:
        """Compile blacklist patterns into regex objects.

        Tries regex compilation first, falls back to literal string matching. That way
        users can use regexes for flexible matching but also simple strings without
        worrying about regex syntax. All patterns are case-insensitive.
        """
        compiled_blacklist = defaultdict(list)
        for artist, patterns in blacklist.items():
            compiled_patterns = []
            for pattern in patterns:
                try:
                    compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
                except re.error:
                    escaped_pattern = re.escape(pattern)
                    compiled_patterns.append(
                        re.compile(escaped_pattern, re.IGNORECASE)
                    )
            compiled_blacklist[artist] = compiled_patterns
        return compiled_blacklist
