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

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from confuse import ConfigView

    from beets.logging import Logger

    from .types import CanonTree, Whitelist


class DataFileLoader:
    """Loads genre-related data files for the lastgenre plugin."""

    def __init__(
        self,
        log: Logger,
        plugin_dir: Path,
        whitelist: Whitelist,
        c14n_branches: CanonTree,
        canonicalize: bool,
    ):
        """Initialize with pre-loaded data.

        Use from_config() classmethod to construct from plugin config.
        """
        self._log = log
        self._plugin_dir = plugin_dir
        self.whitelist = whitelist
        self.c14n_branches = c14n_branches
        self.canonicalize = canonicalize

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

        return cls(log, plugin_dir, whitelist, c14n_branches, canonicalize)

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
