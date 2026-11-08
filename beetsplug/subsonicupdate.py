"""Updates Subsonic library on Beets import
Your Beets configuration file should contain
a "subsonic" section like the following:
    subsonic:
        url: https://mydomain.com:443/subsonic
        user: username
        pass: password
        auth: token
For older Subsonic versions, token authentication
is not supported, use password instead:
    subsonic:
        url: https://mydomain.com:443/subsonic
        user: username
        pass: password
        auth: pass
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar, Protocol

from unidecode import unidecode

from beets import ui
from beets.dbcore import types
from beets.exceptions import UserError
from beets.plugins import BeetsPlugin
from beetsplug._utils.subsonic import SubsonicClient, SubsonicError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from beets.library import Item, LibModel, Library
    from beetsplug._typing import JSONDict

__author__ = "https://github.com/maffo999"

SEARCH_COUNT = 25


def _search_text(value: Any) -> str:
    text = unidecode(str(value or "")).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split()) or text.strip()


def _equivalent(left: Any, right: Any) -> bool:
    return _search_text(left) == _search_text(right)


def _unique(values: Iterable[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        value = value.strip()
        key = value.casefold()
        if value and key not in seen:
            result.append(value)
            seen.add(key)
    return result


class SubsonicUpdateCLIOpts(Protocol):
    """Options for the `subsonicupdate` command, of which there are none."""


class SubsonicUpdate(BeetsPlugin):
    item_types: ClassVar[dict[str, types.Type]] = {"subsonic_id": types.STRING}

    def __init__(self) -> None:
        super().__init__("subsonic")
        # Set default configuration values
        self.config.add(
            {
                "user": "admin",
                "pass": "admin",
                "url": "http://localhost:4040",
                "auth": "token",
                "auto": True,
            }
        )
        self.config["user"].redact = True
        self.config["pass"].redact = True

        if self.config["auto"].get(bool):
            self.register_listener("database_change", self.db_change)
            self.register_listener("smartplaylist_update", self.spl_update)

    def db_change(self, lib: Library, model: LibModel) -> None:
        self.register_listener("cli_exit", self.start_scan)

    def spl_update(self) -> None:
        self.register_listener("cli_exit", self.start_scan)

    def _client(self) -> SubsonicClient:
        url = self.config["url"].as_str()
        # @deprecated("Use url config option instead")
        if not url:
            host = self.config["host"].as_str()
            port = self.config["port"].get(int)
            context_path = self.config["contextpath"].as_str()
            if context_path == "/":
                context_path = ""
            url = f"http://{host}:{port}{context_path}"

        return SubsonicClient(
            base_url=url,
            username=self.config["user"].as_str(),
            password=self.config["pass"].as_str(),
            auth=self.config["auth"].as_str(),
        )

    def start_scan(self, lib: Library) -> None:
        try:
            count = self._client().start_scan()
        except SubsonicError as exc:
            self._log.error("Subsonic scan failed: {}", exc)
        else:
            self._log.info("Updating Subsonic; scanning {} tracks", count)

    def commands(self) -> list[ui.Subcommand]:
        subsonicupdate_cmd = ui.Subcommand(
            "subsonicupdate", help="Update the Subsonic library"
        )

        def func(
            lib: Library, opts: SubsonicUpdateCLIOpts, args: list[str]
        ) -> None:
            if args:
                raise UserError(
                    "the 'subsonicupdate' command does not take arguments"
                )
            self.start_scan(lib)

        subsonicupdate_cmd.func = func

        set_favorite_cmd = ui.Subcommand(
            "subsonic-set-favorite",
            help="mark queried tracks as Subsonic favourites",
        )

        def set_favorite_func(lib: Library, _: Any, args: list[str]) -> None:
            items = lib.items(args)
            if not args and not ui.input_yn(
                f"Mark all {len(items)} tracks as Subsonic favourites (y/n)?",
                True,
            ):
                return
            try:
                self.set_favorite(items)
            except SubsonicError as exc:
                raise UserError(f"Subsonic request failed: {exc}") from exc

        set_favorite_cmd.func = set_favorite_func

        return [subsonicupdate_cmd, set_favorite_cmd]

    def set_favorite(self, items: Iterable[Item]) -> None:
        """Set favourites on the Subsonic server for all resolvable items."""
        client = self._client()
        starred_ids = client.starred_song_ids()
        items_by_id = self._unstarred_items_by_id(client, items, starred_ids)
        if items_by_id:
            client.star_songs(items_by_id)
            # Servers such as Navidrome silently skip unknown IDs, so check
            # what was actually starred to catch stale stored IDs.
            starred_ids = client.starred_song_ids()

        stale_items = [
            item
            for song_id in items_by_id.keys() - starred_ids
            for item in items_by_id[song_id]
        ]
        for item in stale_items:
            self._log.warning(
                "Subsonic did not star {0.artist} - {0.title} ({0.subsonic_id})"
                ", searching for it again",
                item,
            )
            del item["subsonic_id"]
            item.store()

        # Search results come from the server, so these IDs are known to exist
        retried = self._unstarred_items_by_id(client, stale_items, starred_ids)
        client.star_songs(retried)

        # Show one item per song, so duplicates in the library are listed once
        marked = [
            song_items[0]
            for song_id, song_items in items_by_id.items()
            if song_id in starred_ids
        ] + [song_items[0] for song_items in retried.values()]
        for item in marked:
            ui.print_(format(item))
        ui.print_(f"Marked {len(marked)} new tracks as Subsonic favourites.")

    def _unstarred_items_by_id(
        self,
        client: SubsonicClient,
        items: Iterable[Item],
        starred_ids: set[str],
    ) -> dict[str, list[Item]]:
        items = list(items)
        # Report progress roughly every tenth of the way
        step = max(1, len(items) // 10)
        items_by_id: dict[str, list[Item]] = {}
        for index, item in enumerate(items, 1):
            song_id = self._song_id(client, item)
            if song_id and song_id not in starred_ids:
                items_by_id.setdefault(song_id, []).append(item)
            if index % step == 0 or index == len(items):
                self._log.info("Processed {}/{} tracks", index, len(items))
        return items_by_id

    def _song_id(self, client: SubsonicClient, item: Item) -> str | None:
        if song_id := item.get("subsonic_id"):
            return str(song_id)

        queries = self._queries(item)
        if not queries:
            self._log.warning("Skipping item with no searchable metadata")
            return None

        songs_by_id = {}
        for query in queries:
            for song in client.search_songs(query, SEARCH_COUNT):
                songs_by_id[str(song["id"])] = song
            matches = self._best_matches(item, songs_by_id.values())
            if len(matches) == 1:
                item.subsonic_id = matches[0]
                item.store()
                return matches[0]
            if len(matches) > 1:
                self._log.warning(
                    "Skipping ambiguous match for {0.artist} - {0.title}", item
                )
                return None

        self._log.warning("No Subsonic match for {0.artist} - {0.title}", item)
        return None

    @staticmethod
    def _queries(item: Item) -> list[str]:
        artist = item.get("artist")
        album = item.get("album")
        title = item.get("title")
        exact = [
            " ".join(value for value in [artist, album, title] if value),
            " ".join(value for value in [artist, title] if value),
            str(title or ""),
            str(artist or ""),
        ]
        folded = [_search_text(query) for query in exact]
        return _unique([*exact, *folded])

    @staticmethod
    def _best_matches(item: Item, songs: Iterable[JSONDict]) -> list[str]:
        scored = [
            (score, str(song["id"]))
            for song in songs
            if (score := SubsonicUpdate._match_score(item, song)) is not None
        ]
        if not scored:
            return []

        best_score = max(score for score, _ in scored)
        return [song_id for score, song_id in scored if score == best_score]

    @staticmethod
    def _match_score(item: Item, song: JSONDict) -> int | None:
        # Beets and the server usually read the same files, so the tags should
        # agree exactly. Anything looser risks starring a live or remix version.
        if not (
            _equivalent(item.title, song.get("title"))
            and _equivalent(item.artist, song.get("artist"))
        ):
            return None

        score = 0
        if item.album and _equivalent(item.album, song.get("album")):
            score += 1
        if item.track and item.track == song.get("track"):
            score += 1
        return score
