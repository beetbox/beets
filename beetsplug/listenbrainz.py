"""Adds Listenbrainz support to Beets."""

from __future__ import annotations

import datetime
import time
from collections import Counter
from typing import TYPE_CHECKING, ClassVar

import requests

from beets import config, ui
from beets.dbcore import types
from beets.plugins import BeetsPlugin

from ._utils.musicbrainz import MusicBrainzAPIMixin
from ._utils.playcount import update_play_counts
from ._utils.requests import TimeoutAndRetrySession

if TYPE_CHECKING:
    from ._utils.playcount import Track


class ListenBrainzPlugin(MusicBrainzAPIMixin, BeetsPlugin):
    """A Beets plugin for interacting with ListenBrainz."""

    ROOT = "http://api.listenbrainz.org/1/"

    item_types: ClassVar[dict[str, types.Type]] = {
        "listenbrainz_play_count": types.INTEGER
    }

    def __init__(self):
        """Initialize the plugin."""
        super().__init__()
        self.token = self.config["token"].get()
        self.username = self.config["username"].get()
        self.session = TimeoutAndRetrySession()
        self.AUTH_HEADER = {"Authorization": f"Token {self.token}"}
        config["listenbrainz"]["token"].redact = True

    def commands(self):
        """Add beet UI commands to interact with ListenBrainz."""
        lbupdate_cmd = ui.Subcommand(
            "lbimport", help="Import ListenBrainz history"
        )
        lbupdate_cmd.parser.add_option(
            "--max",
            dest="max_listens",
            type="int",
            default=None,
            help="maximum number of listens to fetch (default: all)",
        )

        def func(lib, opts, args):
            self._lbupdate(lib, self._log, max_listens=opts.max_listens)

        lbupdate_cmd.func = func
        return [lbupdate_cmd]

    def _lbupdate(self, lib, log, max_listens=None):
        """Obtain play counts from ListenBrainz."""
        listens = self.get_listens(max_total=max_listens)
        if listens is None:
            log.error("Failed to fetch listens from ListenBrainz.")
            return
        if not listens:
            log.info("No listens found.")
            return
        log.info("Found {} listens", len(listens))
        tracks = self._aggregate_listens(self.get_tracks_from_listens(listens))
        log.info("Aggregated into {} unique tracks", len(tracks))
        found, unknown = update_play_counts(lib, tracks, log, "listenbrainz")
        log.info("... done!")
        log.info("{} unknown play-counts", unknown)
        log.info("{} play-counts imported", found)

    @staticmethod
    def _aggregate_listens(tracks: list[Track]) -> list[Track]:
        """Aggregate individual listen events into per-track play counts.

        ListenBrainz returns individual listen events (each with playcount=1).
        We aggregate them by track identity so each unique track gets its total
        count, making the import idempotent.
        """
        _agg_key = str | tuple[str, str, str]
        play_counts: Counter[_agg_key] = Counter()
        track_info: dict[_agg_key, Track] = {}
        for t in tracks:
            mbid = t.get("mbid") or ""
            artist = t["artist"]
            name = t["name"]
            album = t.get("album") or ""

            key: _agg_key = mbid if mbid else (artist, name, album)
            play_counts[key] += 1
            if key not in track_info:
                track_info[key] = t

        return [
            {**info, "playcount": play_counts[key]}
            for key, info in track_info.items()
        ]

    def _make_request(self, url, params=None):
        """Makes a request to the ListenBrainz API.

        Respects the X-RateLimit-* headers returned by the server: if the
        remaining quota drops to zero, sleeps until the window resets before
        returning, so the next call is guaranteed a fresh quota.
        """
        try:
            response = self.session.get(
                url=url,
                headers=self.AUTH_HEADER,
                timeout=10,
                params=params,
            )
            response.raise_for_status()
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset_in = response.headers.get("X-RateLimit-Reset-In")
            if remaining is not None and int(remaining) == 0 and reset_in:
                self._log.debug(
                    "ListenBrainz rate limit reached; sleeping {}s", reset_in
                )
                time.sleep(int(reset_in) + 1)
            return response.json()
        except requests.exceptions.RequestException as e:
            self._log.debug("Invalid Search Error: {}", e)
            return None

    def get_listens(self, min_ts=None, max_ts=None, count=None, max_total=None):
        """Gets the listen history of a given user.

        Paginates through all available listens using the max_ts parameter.

        Args:
            min_ts: History before this timestamp will not be returned.
                    DO NOT USE WITH max_ts.
            max_ts: History after this timestamp will not be returned.
                    DO NOT USE WITH min_ts.
            count: How many listens to return per page (max 1000).
            max_total: Stop after fetching this many listens in total.

        Returns:
            A list of listen info dictionaries, or None on API failure.
        """
        if min_ts is not None and max_ts is not None:
            raise ValueError("min_ts and max_ts are mutually exclusive.")

        per_page = min(count or 1000, 1000)
        url = f"{self.ROOT}/user/{self.username}/listens"
        all_listens = []

        while True:
            if max_total is not None:
                remaining_needed = max_total - len(all_listens)
                if remaining_needed <= 0:
                    break
                page_size = min(per_page, remaining_needed)
            else:
                page_size = per_page

            params = {"count": page_size}
            if max_ts is not None:
                params["max_ts"] = max_ts
            if min_ts is not None:
                params["min_ts"] = min_ts

            response = self._make_request(url, params)
            if response is None:
                if not all_listens:
                    return None
                break

            listens = response["payload"]["listens"]
            if not listens:
                break

            all_listens.extend(listens)
            self._log.info("Fetched {} listens so far...", len(all_listens))

            # If we got fewer than requested, we've reached the end
            if len(listens) < page_size:
                break

            # Paginate using the oldest listen's timestamp.
            # Subtract 1 to avoid re-fetching listens at the boundary.
            new_max_ts = listens[-1]["listened_at"] - 1
            if max_ts is not None and new_max_ts >= max_ts:
                break
            max_ts = new_max_ts

        return all_listens

    def get_tracks_from_listens(self, listens) -> list[Track]:
        """Returns a list of tracks from a list of listens."""
        tracks: list[Track] = []
        for track in listens:
            if track["track_metadata"].get("release_name") is None:
                continue
            mbid_mapping = track["track_metadata"].get("mbid_mapping", {})
            mbid = mbid_mapping.get("recording_mbid")
            tracks.append(
                {
                    "album": (
                        track["track_metadata"].get("release_name") or ""
                    ).strip(),
                    "name": (
                        track["track_metadata"].get("track_name") or ""
                    ).strip(),
                    "artist": (
                        track["track_metadata"].get("artist_name") or ""
                    ).strip(),
                    "mbid": mbid,
                    "playcount": 1,
                }
            )
        return tracks

    def get_mb_recording_id(self, track) -> str | None:
        """Returns the MusicBrainz recording ID for a track."""
        results = self.mb_api.search(
            "recording",
            {
                "": track["track_metadata"].get("track_name"),
                "release": track["track_metadata"].get("release_name"),
            },
        )
        return next((r["id"] for r in results), None)

    def get_playlists_createdfor(self, username):
        """Returns a list of playlists created by a user."""
        url = f"{self.ROOT}/user/{username}/playlists/createdfor"
        return self._make_request(url)

    def get_listenbrainz_playlists(self):
        resp = self.get_playlists_createdfor(self.username)
        playlists = resp.get("playlists")
        listenbrainz_playlists = []

        for playlist in playlists:
            playlist_info = playlist.get("playlist")
            if playlist_info.get("creator") == "listenbrainz":
                title = playlist_info.get("title")
                self._log.debug("Playlist title: {}", title)
                playlist_type = (
                    "Exploration" if "Exploration" in title else "Jams"
                )
                if "week of" in title:
                    date_str = title.split("week of ")[1].split(" ")[0]
                    date = datetime.datetime.strptime(
                        date_str, "%Y-%m-%d"
                    ).date()
                else:
                    continue
                identifier = playlist_info.get("identifier")
                id = identifier.split("/")[-1]
                listenbrainz_playlists.append(
                    {"type": playlist_type, "date": date, "identifier": id}
                )
        listenbrainz_playlists = sorted(
            listenbrainz_playlists, key=lambda x: x["type"]
        )
        listenbrainz_playlists = sorted(
            listenbrainz_playlists, key=lambda x: x["date"], reverse=True
        )
        for playlist in listenbrainz_playlists:
            self._log.debug("Playlist: {0[type]} - {0[date]}", playlist)
        return listenbrainz_playlists

    def get_playlist(self, identifier):
        """Returns a playlist."""
        url = f"{self.ROOT}/playlist/{identifier}"
        return self._make_request(url)

    def get_tracks_from_playlist(self, playlist):
        """This function returns a list of tracks in the playlist."""
        tracks = []
        for track in playlist.get("playlist").get("track"):
            identifier = track.get("identifier")
            if isinstance(identifier, list):
                identifier = identifier[0]

            tracks.append(
                {
                    "artist": track.get("creator", "Unknown artist"),
                    "identifier": identifier.split("/")[-1],
                    "title": track.get("title"),
                }
            )
        return self.get_track_info(tracks)

    def get_track_info(self, tracks):
        track_info = []
        for track in tracks:
            identifier = track.get("identifier")
            recording = self.mb_api.get_recording(
                identifier, includes=["releases", "artist-credits"]
            )
            title = recording.get("title")
            artist_credit = recording.get("artist-credit", [])
            if artist_credit:
                artist = artist_credit[0].get("artist", {}).get("name")
            else:
                artist = None
            releases = recording.get("releases", [])
            if releases:
                album = releases[0].get("title")
                date = releases[0].get("date")
                year = date.split("-")[0] if date else None
            else:
                album = None
                year = None
            track_info.append(
                {
                    "identifier": identifier,
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "year": year,
                }
            )
        return track_info

    def get_weekly_playlist(self, playlist_type, most_recent=True):
        # Fetch all playlists
        playlists = self.get_listenbrainz_playlists()
        # Filter playlists by type
        filtered_playlists = [
            p for p in playlists if p["type"] == playlist_type
        ]
        # Sort playlists by date in descending order
        sorted_playlists = sorted(
            filtered_playlists, key=lambda x: x["date"], reverse=True
        )
        # Select the most recent or older playlist based on the most_recent flag
        selected_playlist = (
            sorted_playlists[0] if most_recent else sorted_playlists[1]
        )
        self._log.debug(
            f"Selected playlist: {selected_playlist['type']} "
            f"- {selected_playlist['date']}"
        )
        # Fetch and return tracks from the selected playlist
        playlist = self.get_playlist(selected_playlist.get("identifier"))
        return self.get_tracks_from_playlist(playlist)
