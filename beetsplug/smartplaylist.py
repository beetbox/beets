# This file is part of beets.
# Copyright 2016, Dang Mai <contact@dangmai.net>.
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

"""Generates smart playlists based on beets queries."""

from __future__ import annotations

import os
from collections import defaultdict
from functools import cached_property
from shlex import quote as shell_quote
from typing import TYPE_CHECKING, Any, TypeAlias
from urllib.parse import quote
from urllib.request import pathname2url

import confuse

from beets import plugins, ui
from beets.dbcore.query import ParsingError, Query, Sort
from beets.exceptions import UserError
from beets.library import Album, Item, parse_query_string
from beets.util import (
    bytestring_path,
    mkdirall,
    normpath,
    path_as_posix,
    sanitize_path,
    syspath,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from beets.library import Library

QueryAndSort = tuple[Query, Sort]
PlaylistQuery = Query | tuple[QueryAndSort, ...] | None
PlaylistQueryAndSort = tuple[PlaylistQuery, Sort | None]
PlaylistMatch: TypeAlias = tuple[
    str, PlaylistQueryAndSort, PlaylistQueryAndSort
]


class SmartPlaylistPlugin(plugins.BeetsPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.config.add(
            {
                "dest_regen": False,
                "relative_to": None,
                "playlist_dir": ".",
                "auto": True,
                "playlists": [],
                "uri_format": None,
                "fields": [],
                "forward_slash": False,
                "prefix": "",
                "urlencode": False,
                "format": "$artist - $title",
                "output": "m3u",
                "pretend": False,
            }
        )

        self.config["prefix"].redact = True  # May contain username/password.
        self._matched_playlists: set[PlaylistMatch] = set()
        self._unmatched_playlists: set[PlaylistMatch] = set()
        # validate output format
        self.config["output"].get(confuse.Choice(["m3u", "extm3u"]))

        if self.config["auto"]:
            self.register_listener("database_change", self.db_change)

    @cached_property
    def prefix(self) -> bytes:
        return bytestring_path(self.config["prefix"].as_str())

    @cached_property
    def relative_to(self) -> bytes | None:
        if relative_to := self.config["relative_to"].get():
            return normpath(relative_to)

        return None

    @cached_property
    def dest_regen(self) -> bool:
        return self.config["dest_regen"].get(bool)

    @cached_property
    def forward_slash(self) -> bool:
        return self.config["forward_slash"].get(bool)

    @cached_property
    def urlencode(self) -> bool:
        return self.config["urlencode"].get(bool)

    @cached_property
    def uri_format(self) -> str | None:
        return self.config["uri_format"].get()

    def commands(self) -> list[ui.Subcommand]:
        spl_update = ui.Subcommand(
            "splupdate",
            help="update the smart playlists. Playlist names may be "
            "passed as arguments.",
        )
        spl_update.parser.add_option(
            "-p",
            "--pretend",
            action="store_true",
            help="display query results but don't write playlist files.",
        )
        spl_update.parser.add_option(
            "-f",
            "--format",
            type="string",
            default=self.config["format"].get(),
            help="print per-track log lines with custom format",
        )
        spl_update.parser.add_option(
            "-d",
            "--playlist-dir",
            dest="playlist_dir",
            metavar="PATH",
            type="string",
            default=self.config["playlist_dir"].get(),
            help="directory to write the generated playlist files to.",
        )
        spl_update.parser.add_option(
            "--dest-regen",
            action="store_true",
            dest="dest_regen",
            default=self.config["dest_regen"].get(bool),
            help="regenerate the destination path as 'move' or 'convert' "
            "commands would do.",
        )
        spl_update.parser.add_option(
            "--relative-to",
            dest="relative_to",
            metavar="PATH",
            type="string",
            default=self.config["relative_to"].get(),
            help="generate playlist item paths relative to this path.",
        )
        spl_update.parser.add_option(
            "--prefix",
            type="string",
            default=self.config["prefix"].get(),
            help="prepend string to every path in the playlist file.",
        )
        spl_update.parser.add_option(
            "--forward-slash",
            action="store_true",
            dest="forward_slash",
            default=self.config["forward_slash"].get(bool),
            help="force forward slash in paths within playlists.",
        )
        spl_update.parser.add_option(
            "--urlencode",
            action="store_true",
            default=self.config["urlencode"].get(bool),
            help="URL-encode all paths.",
        )
        spl_update.parser.add_option(
            "--uri-format",
            dest="uri_format",
            type="string",
            default=self.config["uri_format"].get(),
            help="playlist item URI template, e.g. http://beets:8337/item/$id/file.",
        )
        spl_update.parser.add_option(
            "--output",
            type="choice",
            choices=["m3u", "extm3u"],
            default=self.config["output"].get(),
            help="specify the playlist format: m3u|extm3u.",
        )
        spl_update.func = self.update_cmd
        return [spl_update]

    def update_cmd(self, lib: Library, opts: Any, args: list[str]) -> None:
        self.build_queries()
        if args:
            args_set = set(args)
            for a in list(args_set):
                if not a.endswith(".m3u"):
                    args_set.add(f"{a}.m3u")

            playlists = {
                (name, q, a_q)
                for name, q, a_q in self._unmatched_playlists
                if name in args_set
            }
            if not playlists:
                unmatched = [name for name, _, _ in self._unmatched_playlists]
                unmatched.sort()
                quoted_names = " ".join(shell_quote(name) for name in unmatched)
                raise UserError(
                    f"No playlist matching any of {quoted_names} found"
                )

            self._matched_playlists = playlists
            self._unmatched_playlists -= playlists
        else:
            self._matched_playlists = self._unmatched_playlists

        self.config.set(vars(opts))
        self.update_playlists(lib)

    def _parse_one_query(
        self, playlist: dict[str, Any], key: str, model_cls: type
    ) -> tuple[PlaylistQuery, Sort | None]:
        qs = playlist.get(key)
        if qs is None:
            return None, None
        if isinstance(qs, str):
            return parse_query_string(qs, model_cls)
        if len(qs) == 1:
            return parse_query_string(qs[0], model_cls)

        queries_and_sorts: tuple[QueryAndSort, ...] = tuple(
            parse_query_string(q, model_cls) for q in qs
        )
        return queries_and_sorts, None

    def build_queries(self) -> None:
        """
        Instantiate queries for the playlists.

        Each playlist has 2 queries: one for items, one for albums, each with a
        sort. We must also remember its name. _unmatched_playlists is a set of
        tuples (name, (q, q_sort), (album_q, album_q_sort)).

        sort may be any sort, or NullSort, or None. None and NullSort are
        equivalent and both eval to False.
        More precisely
        - it will be NullSort when a playlist query ('query' or 'album_query')
          is a single item or a list with 1 element
        - it will be None when there are multiple items in a query
        """
        self._unmatched_playlists = set()
        self._matched_playlists = set()

        for playlist in self.config["playlists"].get(list):
            if "name" not in playlist:
                self._log.warning("playlist configuration is missing name")
                continue

            try:
                q_match = self._parse_one_query(playlist, "query", Item)
                a_match = self._parse_one_query(playlist, "album_query", Album)
            except ParsingError as exc:
                self._log.warning(
                    "invalid query in playlist {}: {}", playlist["name"], exc
                )
                continue

            self._unmatched_playlists.add((playlist["name"], q_match, a_match))

    def _matches_query(self, model: Item | Album, query: PlaylistQuery) -> bool:
        if not query:
            return False
        if isinstance(query, (list, tuple)):
            return any(q.match(model) for q, _ in query)
        return query.match(model)

    def matches(
        self,
        model: Item | Album,
        query: PlaylistQuery,
        album_query: PlaylistQuery,
    ) -> bool:
        if isinstance(model, Album):
            return self._matches_query(model, album_query)
        if isinstance(model, Item):
            return self._matches_query(model, query)
        return False

    def db_change(self, lib: Library, model: Item | Album) -> None:
        if self._unmatched_playlists is None:
            self.build_queries()

        for playlist in self._unmatched_playlists:
            n, (q, _), (a_q, _) = playlist
            if self.matches(model, q, a_q):
                self._log.debug("{} will be updated because of {}", n, model)
                self._matched_playlists.add(playlist)
                self.register_listener("cli_exit", self.update_playlists)

        self._unmatched_playlists -= self._matched_playlists

    @staticmethod
    def get_queries(
        query: PlaylistQueryAndSort,
    ) -> list[tuple[Query, Sort | None]]:
        """Normalize a playlist query into a flat list of query-sort pairs.

        Handles both compound (list/tuple of pairs) and single query inputs,
        returning an empty list when no query is present.
        """
        q, sort = query

        if isinstance(q, (list, tuple)):
            return list(q)
        if q:
            return [(q, sort)]

        return []

    @classmethod
    def get_playlist_items(
        cls,
        lib: Library,
        item_q: PlaylistQueryAndSort,
        album_q: PlaylistQueryAndSort,
    ) -> Iterator[Item]:
        """Collect unique items matching the playlist's item and album queries.

        Queries both tracks directly and albums (expanding them to their
        tracks), then merges the results into a deduplicated list preserving
        insertion order.
        """
        items: list[Item] = []

        for q, sort in cls.get_queries(item_q):
            items.extend(lib.items(q, sort))

        albums: list[Album] = []
        for q, sort in cls.get_queries(album_q):
            albums.extend(lib.albums(q, sort))

        seen_album_ids = set()
        for album in albums:
            if album.id not in seen_album_ids:
                seen_album_ids.add(album.id)
                items.extend(album.items())

        seen_ids = set()
        for item in items:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                yield item

    def get_item_uri(self, item: Item) -> bytes:
        item_uri = item.path
        if uri_format := self.uri_format:
            return uri_format.replace("$id", str(item.id)).encode("utf-8")

        if self.dest_regen:
            item_uri = item.destination()
        if self.relative_to:
            item_uri = os.path.relpath(item_uri, self.relative_to)
        if self.forward_slash:
            item_uri = path_as_posix(item_uri)
        if self.urlencode:
            item_uri = bytestring_path(pathname2url(os.fsdecode(item_uri)))

        return self.prefix + item_uri

    def write_playlist(
        self, path: bytes, is_extm3u: bool, entries: list[PlaylistItem]
    ) -> None:
        """Write a playlist file with the given entries."""
        mkdirall(path)
        with open(syspath(path), "wb") as f:
            keys = []
            if is_extm3u:
                keys = self.config["fields"].get(list)
                f.write(b"#EXTM3U\n")
            for entry in entries:
                f.write(entry.get_comment(is_extm3u, keys))

    def update_playlists(self, lib: Library) -> None:
        playlist_count = len(self._matched_playlists)
        self._log.info("Updating {} smart playlists...", playlist_count)

        playlist_dir = bytestring_path(
            self.config["playlist_dir"].as_filename()
        )

        # Maps playlist filenames to lists of track entries and URI sets used
        # to deduplicate output lines.
        m3us: dict[str, list[PlaylistItem]] = defaultdict(list)
        m3u_uris_by_name: dict[str, set[bytes]] = defaultdict(set)

        for playlist in self._matched_playlists:
            name, item_q, album_q = playlist
            items = self.get_playlist_items(lib, item_q, album_q)

            # As we allow tags in the m3u names, we'll need to iterate through
            # the items and generate the correct m3u file names.
            matched_items: list[Item] = []
            for item in items:
                m3u_name = item.evaluate_template(name, True)
                m3u_name = sanitize_path(m3u_name, lib.replacements)
                item_uri = self.get_item_uri(item)

                if item_uri not in m3u_uris_by_name[m3u_name]:
                    m3u_uris_by_name[m3u_name].add(item_uri)
                    m3us[m3u_name].append(PlaylistItem(item, item_uri))
                    matched_items.append(item)

            self._log.info(
                "Creating playlist {}: {} tracks.", name, len(matched_items)
            )
            for item in matched_items:
                self._log.debug(
                    item.evaluate_template(self.config["format"].as_str())
                )

        if self.config["pretend"].get():
            self._log.info("{} playlists would be updated", playlist_count)
        else:
            # Write all of the accumulated track lists to files.
            is_extm3u = self.config["output"].get() == "extm3u"
            for m3u, entries in m3us.items():
                m3u_path = normpath(
                    os.path.join(playlist_dir, bytestring_path(m3u))
                )
                self.write_playlist(m3u_path, is_extm3u, entries)

            # Send an event when playlists were updated.
            plugins.send("smartplaylist_update")
            self._log.info("{} playlists updated", playlist_count)


class PlaylistItem:
    def __init__(self, item: Item, uri: bytes) -> None:
        self.item = item
        self.uri = uri

    def get_comment(self, is_extm3u: bool, fields: list[str]) -> bytes:
        comment = ""
        if is_extm3u:
            attr = [(k, self.item[k]) for k in fields]
            al = [
                f' {k}="{quote("; ".join(v) if isinstance(v, list) else str(v), safe="/:")}"'  # noqa: E501
                for k, v in attr
            ]
            attrs = "".join(al)
            comment = (
                f"#EXTINF:{int(self.item.length)}{attrs},"
                f"{self.item.artist} - {self.item.title}\n"
            )

        return comment.encode("utf-8") + self.uri + b"\n"
