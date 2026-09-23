from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypedDict, overload

import mpd
from typing_extensions import NotRequired

from beets import config, plugins, ui
from beets.dbcore import types
from beets.dbcore.query import PathQuery
from beets.exceptions import UserError
from beets.util import displayable_path

if TYPE_CHECKING:
    import optparse

    from beets.library import Item, Library
    from beets.logging import BeetsLogger as Logger

    from ._typing import JSONDict


#: When playlist is empty and status is "stop", it is an empty dictionary.
MPDCurrentSong = TypedDict(
    "MPDCurrentSong",
    {
        "added": NotRequired[str],
        "artist": NotRequired[str],
        "date": NotRequired[str],
        "duration": NotRequired[str],
        "file": NotRequired[str],
        "format": NotRequired[str],
        "id": NotRequired[str],
        "last-modified": NotRequired[str],
        "pos": NotRequired[str],
        "time": NotRequired[str],
        "title": NotRequired[str],
    },
)


class MPDStatus(TypedDict):
    state: Literal["play", "pause", "stop"]
    volume: str
    repeat: str
    random: str
    single: str
    consume: str
    partition: str
    playlist: str
    playlistlength: str
    mixrampdb: str
    lastloadedplaylist: str
    song: str
    songid: str
    # below are only set when status is "play" or "pause"
    time: NotRequired[str]
    elapsed: NotRequired[str]
    bitrate: NotRequired[str]
    duration: NotRequired[str]
    audio: NotRequired[str]
    nextsong: NotRequired[str]
    nextsongid: NotRequired[str]


class NowPlaying(TypedDict):
    started: float
    elapsed_at_start: int
    duration: int
    path: str
    id: str
    beets_item: Item | None


# If we lose the connection, how many times do we want to retry and how
# much time should we wait between retries?
RETRIES = 10
RETRY_INTERVAL = 5
DUPLICATE_PLAY_THRESHOLD = 10.0


mpd_config = config["mpd"]


def is_url(path: str) -> bool:
    """Try to determine if the path is an URL."""
    if isinstance(path, bytes):  # if it's bytes, then it's a path
        return False
    return path.split("://", 1)[0] in ["http", "https"]


class MPDClientWrapper:
    def __init__(self, log: Logger) -> None:
        self._log = log

        self.music_directory = mpd_config["music_directory"].as_str()
        self.strip_path = mpd_config["strip_path"].as_str()

        # Ensure strip_path end with '/'
        if not self.strip_path.endswith("/"):
            self.strip_path += "/"

        self._log.debug("music_directory: {.music_directory}", self)
        self._log.debug("strip_path: {.strip_path}", self)

        self.client = mpd.MPDClient()

    def connect(self) -> None:
        """Connect to the MPD."""
        host = mpd_config["host"].as_str()
        port = mpd_config["port"].get(int)

        if host[0] in ["/", "~"]:
            host = os.path.expanduser(host)

        self._log.info("connecting to {}:{}", host, port)
        try:
            self.client.connect(host, port)
        except OSError as e:
            raise UserError(f"could not connect to MPD: {e}")

        password = mpd_config["password"].as_str()
        if password:
            try:
                self.client.password(password)
            except mpd.CommandError as e:
                raise UserError(f"could not authenticate to MPD: {e}")

    def disconnect(self) -> None:
        """Disconnect from the MPD."""
        self.client.close()
        self.client.disconnect()

    @overload
    def get(
        self, command: Literal["currentsong"], retries: int = RETRIES
    ) -> MPDCurrentSong: ...
    @overload
    def get(
        self, command: Literal["status"], retries: int = RETRIES
    ) -> MPDStatus: ...
    @overload
    def get(
        self, command: Literal["idle"], retries: int = RETRIES
    ) -> list[str]: ...
    @overload
    def get(self, command: str, retries: int = RETRIES) -> Any: ...
    def get(self, command: str, retries: int = RETRIES) -> Any:
        """Wrapper for requests to the MPD server. Tries to re-connect if the
        connection was lost (f.ex. during MPD's library refresh).
        """
        try:
            return getattr(self.client, command)()
        except (OSError, mpd.ConnectionError) as err:
            self._log.error("{}", err)

        if retries <= 0:
            # if we exited without breaking, we couldn't reconnect in time :(
            raise UserError("communication with MPD server failed")

        time.sleep(RETRY_INTERVAL)

        try:
            self.disconnect()
        except mpd.ConnectionError:
            pass

        self.connect()
        return self.get(command, retries=retries - 1)

    def currentsong(self) -> tuple[str | None, str | None]:
        """Return the path to the currently playing song, along with its
        songid.  Prefixes paths with the music_directory, to get the absolute
        path.
        In some cases, we need to remove the local path from MPD server,
        we replace 'strip_path' with ''.
        `strip_path` defaults to ''.
        """
        entry = self.get("currentsong")
        file, id_ = entry.get("file"), entry.get("id")
        if file and not is_url(file):
            if file.startswith(self.strip_path):
                file = file[len(self.strip_path) :]
            file = os.path.join(self.music_directory, file)
        self._log.debug("returning: {}", file)
        return file, id_

    def status(self) -> MPDStatus:
        """Return the current status of the MPD."""
        return self.get("status")

    def events(self) -> list[str]:
        """Return list of events. This may block a long time while waiting for
        an answer from MPD.
        """
        return self.get("idle")


class MPDStats:
    now_playing: NowPlaying | None = None

    def __init__(self, lib: Library, log: Logger) -> None:
        self.lib = lib
        self._log = log

        self.do_rating = mpd_config["rating"].get(bool)
        self.rating_mix = mpd_config["rating_mix"].get(float)
        self.played_ratio_threshold = mpd_config["played_ratio_threshold"].get(
            float
        )
        self.mpd = MPDClientWrapper(log)

    def rating(
        self, play_count: int, skip_count: int, rating: float, skipped: bool
    ) -> float:
        """Calculate a new rating for a song based on play count, skip count,
        old rating and the fact if it was skipped or not.
        """
        if skipped:
            rolling = rating - rating / 2.0
        else:
            rolling = rating + (1.0 - rating) / 2.0
        stable = (play_count + 1.0) / (play_count + skip_count + 2.0)
        return self.rating_mix * stable + (1.0 - self.rating_mix) * rolling

    def get_item(self, path: str) -> Item | None:
        """Return the beets item related to path."""
        query = PathQuery("path", os.fsencode(path))
        item = self.lib.items(query).get()
        if item:
            return item
        self._log.info("item not found: {}", displayable_path(path))
        return None

    def update_item(
        self,
        item: Item | None,
        attribute: str,
        value: float | None = None,
        increment: float | None = None,
    ) -> None:
        """Update the beets item. Set attribute to value or increment the value
        of attribute. If the increment argument is used the value is cast to
        the corresponding type.
        """
        if item is None:
            return

        if increment is not None:
            item.load()
            value = type(increment)(item.get(attribute, 0)) + increment

        if value is not None:
            item[attribute] = value
            item.store()

            self._log.debug(
                "updated: {} = {} [{.filepath}]",
                attribute,
                item[attribute],
                item,
            )

    def update_rating(self, item: Item | None, skipped: bool) -> None:
        """Update the rating for a beets item. The `item` can either be a
        beets `Item` or None. If the item is None, nothing changes.
        """
        if item is None:
            return

        item.load()
        rating = self.rating(
            int(item.get("play_count", 0)),
            int(item.get("skip_count", 0)),
            float(item.get("rating", 0.5)),
            skipped,
        )

        self.update_item(item, "rating", rating)

    def handle_song_change(self, song: NowPlaying) -> bool:
        """Determine if a song was skipped or not and update its attributes.
        To this end the difference between the song's supposed end time
        and the current time is calculated. If it's greater than a threshold,
        the song is considered skipped.

        Returns whether the change was manual (skipped previous song or not)
        """
        elapsed = song["elapsed_at_start"] + (time.time() - song["started"])
        skipped = elapsed / song["duration"] < self.played_ratio_threshold
        if skipped:
            self.handle_skipped(song)
        else:
            self.handle_played(song)

        if self.do_rating:
            self.update_rating(song["beets_item"], skipped)

        return skipped

    def handle_played(self, song: NowPlaying) -> None:
        """Updates the play count of a song."""
        self.update_item(song["beets_item"], "play_count", increment=1)
        self._log.info("played {}", displayable_path(song["path"]))

    def handle_skipped(self, song: NowPlaying) -> None:
        """Updates the skip count of a song."""
        self.update_item(song["beets_item"], "skip_count", increment=1)
        self._log.info("skipped {}", displayable_path(song["path"]))

    def on_stop(self, status: JSONDict) -> None:
        self._log.info("stop")

        # if the current song stays the same it means that we stopped on the
        # current track and should not record a skip.
        if self.now_playing and self.now_playing["id"] != status.get("songid"):
            self.handle_song_change(self.now_playing)

        self.now_playing = None

    def on_pause(self, status: JSONDict) -> None:
        self._log.info("pause")
        self.now_playing = None

    def on_play(self, status: JSONDict) -> None:
        path, songid = self.mpd.currentsong()
        if not path or not songid:
            return

        played, duration = map(int, status["time"].split(":", 1))
        if self.now_playing:
            if self.now_playing["path"] != path:
                self.handle_song_change(self.now_playing)
            else:
                # In case we got mpd play event with same song playing
                # multiple times,
                # assume low diff means redundant second play event
                # after natural song start.
                diff = abs(time.time() - self.now_playing["started"])

                if diff <= DUPLICATE_PLAY_THRESHOLD:
                    return

                if self.now_playing["path"] == path and played == 0:
                    self.handle_song_change(self.now_playing)

        if is_url(path):
            self._log.info("playing stream {}", displayable_path(path))
            self.now_playing = None
            return

        self._log.info("playing {}", displayable_path(path))

        self.now_playing = {
            "started": time.time(),
            "elapsed_at_start": played,
            "duration": duration,
            "path": path,
            "id": songid,
            "beets_item": self.get_item(path),
        }

        self.update_item(
            self.now_playing["beets_item"],
            "last_played",
            value=int(time.time()),
        )

    def run(self) -> None:
        self.mpd.connect()
        events = ["player"]

        while True:
            if "player" in events:
                status = self.mpd.status()
                getattr(self, f"on_{status['state']}")(status)

            events = self.mpd.events()


class MPDStatsPlugin(plugins.BeetsPlugin):
    item_types: ClassVar[dict[str, types.Type]] = {
        "play_count": types.INTEGER,
        "skip_count": types.INTEGER,
        "last_played": types.DATE,
        "rating": types.FLOAT,
    }

    def __init__(self) -> None:
        super().__init__()
        mpd_config.add(
            {
                "music_directory": config["directory"].as_filename(),
                "strip_path": "",
                "rating": True,
                "rating_mix": 0.75,
                "host": os.environ.get("MPD_HOST", "localhost"),
                "port": int(os.environ.get("MPD_PORT", 6600)),
                "password": "",
                "played_ratio_threshold": 0.85,
            }
        )
        mpd_config["password"].redact = True

    def commands(self) -> list[ui.Subcommand]:
        cmd = ui.Subcommand(
            "mpdstats", help="run a MPD client to gather play statistics"
        )
        cmd.parser.add_option(
            "--host",
            dest="host",
            type="string",
            help="set the hostname of the server to connect to",
        )
        cmd.parser.add_option(
            "--port",
            dest="port",
            type="int",
            help="set the port of the MPD server to connect to",
        )
        cmd.parser.add_option(
            "--password",
            dest="password",
            type="string",
            help="set the password of the MPD server to connect to",
        )

        def func(lib: Library, opts: optparse.Values, args: list[str]) -> None:
            mpd_config.set_args(opts)

            try:
                MPDStats(lib, self._log).run()
            except KeyboardInterrupt:
                pass

        cmd.func = func
        return [cmd]
