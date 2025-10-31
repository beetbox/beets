# This file is part of beets.
# Copyright 2025, Jacob Danell.
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

"""
Save all skipped songs to a text file for later review.
This plugin uses the Spotify plugin (if available) to try to find
the Spotify links for the skipped songs.
"""

import os
from typing import TYPE_CHECKING, Optional

from beets import plugins
from beets.importer import Action
from beets.plugins import BeetsPlugin

if TYPE_CHECKING:
    from beets.metadata_plugins import SearchFilter
    from beets.plugins import ImportSession, ImportTask

__author__ = "jacob@emberlight.se"
__version__ = "1.0"


def summary(task: "ImportTask"):
    """Given an ImportTask, produce a short string identifying the
    object.
    """
    if task.is_album:
        return f"{task.cur_artist} - {task.cur_album}"
    else:
        item = task.item  # type: ignore[attr-defined]
        return f"{item.artist} - {item.title}"


class SaveSkippedSongsPlugin(BeetsPlugin):
    def __init__(self):
        """Initialize the plugin and read configuration."""
        super().__init__()
        self.config.add(
            {
                "spotify": True,
                "path": "skipped_songs.txt",
            }
        )
        self.register_listener("import_task_choice", self.log_skipped_song)

    def log_skipped_song(self, task: "ImportTask", session: "ImportSession"):
        if task.choice_flag == Action.SKIP:
            # If spotify integration is enabled, try to match with Spotify
            link = None
            if self.config["spotify"].get(bool):
                link = self._match_with_spotify(task, session)

            result = f"{summary(task)}{' (' + link + ')' if link else ''}"
            self._log.info(f"Skipped: {result}")
            path = self.config["path"].get(str)
            if path:
                path = os.path.abspath(path)
                try:
                    # Read existing lines (if file exists) and avoid duplicates.
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            existing = {
                                line.rstrip("\n").strip().lower()
                                for line in f
                            }
                    except FileNotFoundError:
                        existing = set()

                    normalized_result = result.strip().lower()
                    if normalized_result not in existing:
                        with open(path, "a", encoding="utf-8") as f:
                            f.write(f"{result}\n")
                    else:
                        self._log.debug(f"Song already recorded in {path}")
                except OSError as exc:
                    # Don't crash import; just log the I/O problem.
                    self._log.debug(
                        f"Could not write skipped song to {path}: {exc}"
                    )

    def _match_with_spotify(
        self, task: "ImportTask", session: "ImportSession"
    ) -> Optional[str]:
        """Try to match the skipped track/album with Spotify by directly
        calling the Spotify API search.
        """
        try:
            # Try to get the spotify plugin if it's already loaded
            spotify_plugin = None
            for plugin in plugins.find_plugins():
                if plugin.name == "spotify":
                    spotify_plugin = plugin
                    break

            # If not loaded, try to load it dynamically
            if not spotify_plugin:
                try:
                    from beetsplug.spotify import SpotifyPlugin

                    spotify_plugin = SpotifyPlugin()
                    self._log.debug("Loaded Spotify plugin dynamically")
                except ImportError as e:
                    self._log.debug(f"Could not import Spotify plugin: {e}")
                    return
                except Exception as e:
                    self._log.debug(f"Could not initialize Spotify plugin: {e}")
                    return

            # Build search parameters based on the task
            query_filters: SearchFilter = {}
            if task.is_album:
                query_string = task.cur_album or ""
                if task.cur_artist:
                    query_filters["artist"] = task.cur_artist
                search_type = "album"
            else:
                # For singleton imports
                item = task.item  # type: ignore[attr-defined]
                query_string = item.title or ""
                if item.artist:
                    query_filters["artist"] = item.artist
                if item.album:
                    query_filters["album"] = item.album
                search_type = "track"

            self._log.info(
                f"Searching Spotify for: {query_string} ({query_filters})"
            )

            # Call the Spotify API directly via the plugin's search method
            results = spotify_plugin._search_api(  # type: ignore[attr-defined]
                query_type=search_type,  # type: ignore[arg-type]
                query_string=query_string,
                filters=query_filters,
            )

            if results:
                self._log.info(f"Found {len(results)} Spotify match(es)!")
                self._log.info("Returning first Spotify match link")
                return results[0].get("external_urls", {}).get("spotify", "")
            else:
                self._log.info("No Spotify matches found")

        except AttributeError as e:
            self._log.debug(f"Spotify plugin method not available: {e}")
        except Exception as e:
            self._log.debug(f"Error searching Spotify: {e}")
        return
