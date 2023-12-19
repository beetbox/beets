"""
Adds Listenbrainz support to Beets.
"""

import requests
import datetime
from beets import config, ui
from beets.plugins import BeetsPlugin
import musicbrainzngs


class ListenBrainzPlugin(BeetsPlugin):
    data_source = "ListenBrainz"
    ROOT = "http://api.listenbrainz.org/1/"

    def __init__(self):
        super().__init__()
        self.token = self.config["token"].get()
        self.username = self.config["username"].get()
        self.AUTH_HEADER = {"Authorization": f"Token {self.token}"}
        config["listenbrainz"]["token"].redact = True

    def commands(self):
        """Add beet UI commands to interact with ListenBrainz."""
        lbupdate_cmd = ui.Subcommand(
            "lbimport", help=f"Import {self.data_source} history"
        )

        def func(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self._lbupdate(items, ui.should_write())

        lbupdate_cmd.func = func
        return [lbupdate_cmd]

    def _lbupdate(self, items, write):
        """Obtain view count from Listenbrainz."""
        ls = self.get_listens()
        self._log.info(f"Found {len(ls)} listens")

    def _make_request(self, url):
        try:
            response = requests.get(
                url=url,
                headers=self.AUTH_HEADER,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._log.debug(f"Invalid Search Error: {e}")
            return None

    def get_listens(self, min_ts=None, max_ts=None, count=None):
        """Gets the listen history of a given user.

        Args:
            username: User to get listen history of.
            min_ts: History before this timestamp will not be returned.
                    DO NOT USE WITH max_ts.
            max_ts: History after this timestamp will not be returned.
                    DO NOT USE WITH min_ts.
            count: How many listens to return. If not specified,
                uses a default from the server.

        Returns:
            A list of listen info dictionaries if there's an OK status.

        Raises:
            An HTTPError if there's a failure.
            A ValueError if the JSON in the response is invalid.
            An IndexError if the JSON is not structured as expected.
        """
        response = self._make_request(
            url="http://{0}/1/user/{1}/listens".format(
                self.ROOT, self.username
            ),
        )

        if response is not None:
            return response["payload"]["listens"]
        else:
            return None

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
                playlist_type = (
                    "Exploration" if "Exploration" in title else "Jams"
                )
                date_str = title.split("week of ")[1].split(" ")[0]
                date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                identifier = playlist_info.get("identifier")
                id = identifier.split("/")[-1]
                listenbrainz_playlists.append(
                    {"type": playlist_type, "date": date, "identifier": id}
                )
        return listenbrainz_playlists

    def get_playlist(self, identifier):
        """Returns a playlist."""
        url = f"{self.ROOT}/playlist/{identifier}"
        return self._make_request(url)

    def get_tracks_from_playlist(self, playlist):
        """This function returns a list of tracks in the playlist."""
        tracks = []
        for track in playlist.get("playlist").get("track"):
            tracks.append(
                {
                    "artist": track.get("creator"),
                    "identifier": track.get("identifier").split("/")[-1],
                    "title": track.get("title"),
                }
            )
        return self.get_track_info(tracks)

    def get_track_info(self, tracks):
        track_info = []
        for track in tracks:
            identifier = track.get("identifier")
            resp = musicbrainzngs.get_recording_by_id(
                identifier, includes=["releases", "artist-credits"]
            )
            recording = resp.get("recording")
            title = recording.get("title")
            artist_credit = recording.get("artist-credit", [])
            if artist_credit:
                artist = artist_credit[0].get("artist", {}).get("name")
            else:
                artist = None
            releases = recording.get("release-list", [])
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

    def get_weekly_playlist(self, index):
        """Returns a list of weekly playlists based on the index."""
        playlists = self.get_listenbrainz_playlists()
        playlist = self.get_playlist(playlists[index].get("identifier"))
        return self.get_tracks_from_playlist(playlist)

    def get_weekly_exploration(self):
        """Returns a list of weekly exploration."""
        return self.get_weekly_playlist(0)

    def get_weekly_jams(self):
        """Returns a list of weekly jams."""
        return self.get_weekly_playlist(1)

    def get_last_weekly_exploration(self):
        """Returns a list of weekly exploration."""
        return self.get_weekly_playlist(3)

    def get_last_weekly_jams(self):
        """Returns a list of weekly jams."""
        return self.get_weekly_playlist(3)
