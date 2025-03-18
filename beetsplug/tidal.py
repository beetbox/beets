import json
import optparse
import os.path
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

import backoff
import cachetools
import confuse
import requests
import tidalapi

from beets import logging, ui
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.importer import ImportSession, ImportTask
from beets.library import Item, Library
from beets.plugins import BeetsPlugin
from beets.util import bytestring_path, remove, syspath


def backoff_handler(details: dict[Any, Any]) -> None:
    """Handler for rate limiting backoff"""
    TidalPlugin.logger.debug(
        "Rate limited! Cooling off for {wait:0.1f} seconds \
            after calling function {target.__name__} {tries} times".format(
            **details
        )
    )


class TidalPlugin(BeetsPlugin):
    """TidalPlugin is a TIDAL source for the autotagger"""

    # The built-in beets logger is an instance variable, so to access it
    # in the backoff_handler, we have to assign it to a static variable.
    logger: logging.BeetsLogger = None

    data_source: str = "tidal"
    track_share_regex: str = r"(tidal.com\/browse\/track\/)([0-9]*)(\?u)"  # Format: https://tidal.com/browse/track/221182395?u
    album_share_regex: str = r"(tidal.com\/browse\/album\/)([0-9]*)(\?u)"  # Format: https://tidal.com/browse/album/221182592?u

    # Grabs record label name from copyright info
    # Essentially, this just grabs all non-whitespace, non-numerical characters
    # This is needed as the copyright value is freeform for the distributors
    # This has been tested with the following formats:
    # (C) 2020 record label, 2025 record label, © 2020 record label, © record label,
    # and just record label.
    copyright_regex: str = r"(?!\()(?![Cc])(?!\))(?!©)(?!\s)[\D]+"

    # List is NOT sorted in _grab_art, must be lowest to highest
    valid_art_res: list[int] = [80, 160, 320, 640, 1280]

    # Number of times to retry when we get a TooManyRequests exception
    rate_limit_retries: int = 16

    def __init__(self) -> None:
        super().__init__()
        TidalPlugin.logger = self._log

        # A separate write handler is needed as import stages are ran
        # before any file manipulation is done therefore
        # any file writes in the import stage operate on the original file
        self.import_stages = [self.stage]
        self.register_listener("write", self.write_file)

        # This handler runs before import to load our session and to error out
        # if needed... If this code is put in __init__, then the plugin CLI
        # cannot run.
        self.register_listener("import_begin", self.import_begin)

        # Import config
        # The lyrics search limit is much smaller than the metadata search limit
        # as the current implementation is very API-heavy and TIDAL heavily
        # rate limits the lyrics API so increasing the limit causes
        # an __exponential__ increase in API calls.
        self.config.add(
            {
                "auto": False,
                "lyrics": True,
                "synced_lyrics": True,
                "overwrite_lyrics": False,
                "metadata_search_limit": 25,
                "lyrics_search_limit": 10,
                "lyrics_no_duration_valid": False,
                "search_max_altartists": 5,
                "max_lyrics_time_difference": 5,
                "tokenfile": "tidal_token.json",
                "write_sidecar": False,
                "max_art_resolution": 1280,
            }
        )

        # Validate that max_art_resolution is a valid value
        if self.config["max_art_resolution"].get() not in self.valid_art_res:
            raise ui.UserError(
                (
                    f"Config value max_art_resolution "
                    f"has to be one of {self.valid_art_res} "
                    f"and is currently {self.config["max_art_resolution"].as_number()}"
                )
            )

        self.sessfile = self.config["tokenfile"].get(
            confuse.Filename(in_app_dir=True)
        )

        # tidalapi.session.Session object we throw around to execute API calls with
        self.sess: tidalapi.Session | None = None

    def _load_session(self, fatal: bool = False) -> bool:
        """Loads a TIDAL session from a JSON file to the class singleton"""
        if self.sess:
            self._log.debug(
                "Not attempting to load session state as we already have a session!"
            )
            return True

        self._log.debug(
            f"Attempting to load session state from {self.sessfile}!"
        )
        self.sess = tidalapi.session.Session()

        # Attempt to load OAuth data from token file
        try:
            with open(self.sessfile) as file:
                sess_data = json.load(file)
        except (OSError, json.JSONDecodeError):
            # Error occured, most likely token file does not exist.
            self._log.debug("Session state file does not exist or is corrupt")
            if fatal:
                raise ui.UserError(
                    (
                        "Please login to TIDAL"
                        " using `beets tidal --login` or disable tidal plugin"
                    )
                )
            else:
                return False
        else:
            # Got some JSON data from the file
            # Let's load the data into a session and check for validity.
            self.sess.load_oauth_session(
                sess_data["token_type"],
                sess_data["access_token"],
                sess_data["refresh_token"],
                datetime.fromisoformat(sess_data["expiry_time"]),
            )

            if not self.sess.check_login():
                self._log.debug(
                    "Session state loaded but check_login() returned False"
                )

                # Clear session file so we don't keep spamming the API
                with open(self.sessfile, "w") as file:
                    self._log.debug(
                        "Clearing session state file to avoid unneeded API calls"
                    )

                    remove(bytestring_path(self.sessfile), soft=True)

                if fatal:
                    raise ui.UserError(
                        (
                            "Please login to TIDAL"
                            " using `beets tidal --login` or disable tidal plugin"
                        )
                    )
                else:
                    return False

            # Resave the session if login succeeded and the token has expired
            # This means we renewed the token
            if datetime.now() > datetime.fromisoformat(
                sess_data["expiry_time"]
            ):
                self._log.debug("Resaving session due to token renewal...")
                self._save_session(self.sess)

            return True

    def _save_session(self, sess: tidalapi.session.Session) -> None:
        """Saves a TIDAL session to a JSON file"""
        self._log.debug(f"Saving session state to {self.sessfile}!")
        with open(self.sessfile, "w") as file:
            json.dump(
                {
                    "token_type": sess.token_type,
                    "access_token": sess.access_token,
                    "refresh_token": sess.refresh_token,
                    "expiry_time": sess.expiry_time.isoformat(),
                },
                file,
            )

    def _login(self) -> None:
        """Creates a session to use with the TIDAL API"""
        self.sess = tidalapi.session.Session()
        login, future = self.sess.login_oauth()
        ui.print_(
            f"Open the following URL to complete login: https://{login.verification_uri_complete}"
        )
        ui.print_(f"The link expires in {int(login.expires_in)} seconds!")

        if not future.result():
            raise ui.UserError("Login failure! See above output for more info.")
        else:
            ui.print_("Login successful.")

        self._save_session(self.sess)

    def _refresh_metadata(self, lib: Library) -> None:
        """Refreshes metadata for TIDAL tagged tracks.

        Currently, this only updates popularity."""
        self._log.debug("Refreshing metadata for TIDAL tracks")
        self._load_session(fatal=True)
        assert self.sess is tidalapi.session.Session

        for item in lib.items("tidal_track_id::[0-9]+"):
            self._log.debug(f"Processing item {item.title}")
            try:
                tidaltrack = self.sess.track(item["tidal_track_id"])
            except tidalapi.exceptions.ObjectNotFound:
                self._log.warn(
                    (
                        f"TIDAL ID exists for track {item.title} "
                        "yet TIDAL returns no track"
                    )
                )
                continue

            item["tidal_track_popularity"] = tidaltrack.popularity
            item.try_sync(ui.should_write(), ui.should_move())

        for album in lib.albums("tidal_album_id::[0-9]+"):
            self._log.debug(f"Processing album {album.album}")
            try:
                tidalalbum = self.sess.album(item["tidal_album_id"])
            except tidalapi.exceptions.ObjectNotFound:
                self._log.warn(
                    (
                        f"TIDAL ID exists for album {album.album} "
                        " yet TIDAL returns no album"
                    )
                )
                continue

            album["popularity"] = tidalalbum.popularity
            album.try_sync(ui.should_write(), ui.should_move())

    def cmd_main(
        self, lib: Library, opts: optparse.Values, arg: list[Any]
    ) -> None:
        if opts.login:
            self._log.debug("Running login routine!")
            self._login()
        elif opts.fetch:
            self._log.debug(f"Force fetching lyrics for track ID {opts.fetch}")
            self._load_session(fatal=True)
            assert self.sess is tidalapi.session.Session

            try:
                track = self.sess.track(opts.fetch)
            except tidalapi.exceptions.ObjectNotFound:
                raise ui.UserError(f"Track with ID {opts.fetch} not found")

            ui.print_(self._get_lyrics(track))
        elif opts.refresh:
            self._refresh_metadata(lib)

    def commands(
        self,
    ) -> list[Callable[[Library, optparse.Values, list[Any]], None]]:
        cmd = ui.Subcommand("tidal", help="fetch metadata from TIDAL")
        cmd.parser.add_option(
            "-l",
            "--login",
            dest="login",
            action="store_true",
            default=False,
            help="login to TIDAL",
        )

        cmd.parser.add_option(
            "-f",
            "--fetch",
            dest="fetch",
            default=None,
            help="Fetch lyrics",
        )

        cmd.parser.add_option(
            "-r",
            "--refresh",
            dest="refresh",
            action="store_true",
            default=False,
            help="Refresh metadata for TIDAL tagged tracks",
        )

        cmd.func = self.cmd_main
        return [cmd]

    def album_for_id(self, album_id: str) -> AlbumInfo | None:
        """Return TIDAL metadata for a specific TIDAL Album ID"""
        assert self.sess is tidalapi.session.Session
        # This is just the numerical album ID to use with the TIDAL API
        tidal_album_id = None

        # Try to use album_id directly, otherwise parse it from URL
        try:
            tidal_album_id = int(album_id)
            self._log.debug("Using track_id directly in album_for_id")
        except ValueError:
            self._log.debug("album_id is NOT an integer, parsing it with regex")
            regx = re.search(self.album_share_regex, album_id)
            if not regx:
                self._log.debug("Regex returned no matches")
                return None

            if len(regx.groups()) != 3:
                self._log.debug(
                    (
                        "Album share URL parsing failed because we got"
                        f"{len(regx.groups())} groups when 3 was expected"
                    )
                )
                return None

            tidal_album_id = int(regx.groups()[-2])

        try:
            album = self.sess.album(tidal_album_id)
        except tidalapi.exceptions.ObjectNotFound:
            self._log.debug(f"No album for ID {tidal_album_id}")
            return None

        return self._album_to_albuminfo(album)

    def track_for_id(self, track_id: str) -> TrackInfo | None:
        """Return TIDAL metadata for a specific TIDAL Track ID"""
        self._log.debug(f"Running track_for_id with track {track_id}!")
        assert self.sess is tidalapi.session.Session

        # This is just the numerical track ID to use with the TIDAL API
        tidal_track_id = None

        # Try to use track_id directly, otherwise parse it from URL
        try:
            tidal_track_id = int(track_id)
            self._log.debug("Using track_id directly in track_for_id")
        except ValueError:
            self._log.debug("track_id is NOT an integer, parsing it with regex")
            regx = re.search(self.track_share_regex, track_id)
            if not regx:
                self._log.debug("Regex returned no matches")
                return None

            if len(regx.groups()) != 3:
                self._log.debug(
                    (
                        "Track share URL parsing failed because we got"
                        f"{len(regx.groups())} groups when 3 was expected"
                    )
                )
                return None

            tidal_track_id = int(regx.groups()[-2])

        try:
            track = self.sess.track(tidal_track_id, with_album=True)
        except tidalapi.exceptions.ObjectNotFound:
            self._log.debug(f"No track for ID {tidal_track_id}")
            return None

        return self._track_to_trackinfo(track, track.album)

    def candidates(
        self,
        items: list[Item],
        artist: str | None,
        album: str | None,
        va_likely: bool,
        extra_tags: dict[Any, Any],
    ) -> list[AlbumInfo]:
        """Returns TIDAL album candidates for a specific set of items"""
        candidates = []

        self._log.debug(
            "Searching for candidates using tidal_album_id from items"
        )
        assert self.sess is tidalapi.session.Session
        for item in items:
            if item.get("tidal_album_id", None):
                try:
                    albumi = self._album_to_albuminfo(
                        self.sess.album(item.tidal_album_id)
                    )
                    candidates.append(albumi)
                except tidalapi.exceptions.ObjectNotFound:
                    self._log.debug(
                        f"No album found for ID {item.tidal_album_id}"
                    )

        self._log.debug(
            f"{len(candidates)} Candidates found using tidal_album_id from items!"
        )
        self._log.debug("Searching for candidates using _search_album search")

        if va_likely:
            candidates += [
                self._album_to_albuminfo(x)
                for x in self._tidal_search(
                    album,
                    tidalapi.Album,
                    limit=self.config["metadata_search_limit"].get(int),
                )
            ]

        else:
            candidates += [
                self._album_to_albuminfo(x)
                for x in self._tidal_search(
                    f"{artist} {album}",
                    tidalapi.Album,
                    limit=self.config["metadata_search_limit"].get(int),
                )
            ]

        if len(items) == 1:
            self._log.debug(
                "Searching for candidates using _search_from_metadata due to singleton"
            )
            for track in self._search_from_metadata(items[0]):
                # Albums might be optional for tracks,
                # Let's not break if it isn't defined.
                if not track.album:
                    continue

                try:
                    candidates.append(
                        self._album_to_albuminfo(
                            self.sess.album(track.album.id)
                        )
                    )
                except tidalapi.exceptions.ObjectNotFound:
                    self._log.debug(f"Album ID {track.album.id} not found")

        return candidates

    def item_candidates(
        self, item: Item, artist: str | None, album: str | None
    ) -> list[TrackInfo]:
        """Returns TIDAL track candidates for a specific item"""
        self._log.debug(f"Searching TIDAL for {item}!")

        return [
            self._track_to_trackinfo(x)
            for x in self._search_from_metadata(
                item, limit=self.config["metadata_search_limit"].as_number()
            )
        ]

    def _album_to_albuminfo(self, album: tidalapi.Album) -> AlbumInfo:
        """Converts a TIDAL album to a beets AlbumInfo"""
        tracks = []

        # Process tracks
        # Not using sparse albums as we already have the album
        # so it's not using up any additional API calls.
        for track in album.tracks(sparse_album=False):
            tracks.append(self._track_to_trackinfo(track, album))

        # Create basic albuminfo with standard fields
        albuminfo = AlbumInfo(
            album=album.name,
            album_id=album.id,
            artist=album.artist.name,
            artist_id=album.artist.id,
            va=len(album.artists) == 1
            and album.artist.name.lower() == "various artists",
            mediums=album.num_volumes,
            data_source=self.data_source,
            data_url=album.share_url,
            tracks=tracks,
            barcode=album.universal_product_number,
            albumtype=album.type,
            artists=[artist.name for artist in album.artists],
            artists_ids=[str(artist.id) for artist in album.artists],
            label=self._parse_copyright(album.copyright),
            cover_art_url=self._grab_art(album),
        )

        # Add TIDAL specific metadata
        albuminfo.tidal_album_id = album.id
        albuminfo.tidal_artist_id = album.artist.id
        albuminfo.tidal_album_popularity = album.popularity  # Range: 0 to 100

        # Add release date if we have one
        if album.release_date:
            albuminfo.year = album.release_date.year
            albuminfo.month = album.release_date.month
            albuminfo.day = album.release_date.day

        return albuminfo

    def _grab_art(self, album: tidalapi.Album) -> str | None:
        """Grabs the highest resolution valid cover art for a given album."""
        self._log.debug(f"Grabbing album art for album {album.id}")
        maxresindx = self.valid_art_res.index(
            self.config["max_art_resolution"].get()
        )
        artres = self.valid_art_res[: maxresindx + 1]

        # The list of art resolutions to use is reversed as the smaller
        # sized art is more likely to succeed.
        artres.reverse()

        for res in artres:
            # tidalapi.Album.image always returns a string if it does not
            # throw an exception.
            arturl: str = album.image(res)
            if self._validate_art(arturl):
                self._log.debug(f"Valid art of resolution {res} found")
                return arturl

        self._log.debug(f"No valid art was found for album {album.id}")
        return None

    def _validate_art(self, url: str) -> bool:
        """Validates album art by attempting to grab it"""
        self._log.debug(f"Validating album art URL: {url}")
        # HTTP HEAD is used here to reduce load on TIDAL servers
        # and we only really need the HTTP response code anyways.
        resp = requests.head(url)
        try:
            resp.raise_for_status()
            return True
        except requests.exceptions.HTTPError:
            return False

    def _parse_copyright(self, copyright: str) -> str:
        """Attempts to extract a record label from a freeform
        TIDAL copyright string."""
        # This isn't 100% needed, but it makes calling it easier
        if not copyright:
            return ""

        # The regex module is typed as list[Any] as it can even be a list of lists
        # however, the specific regexes that we're using only return strings.
        regx: list[str] = re.findall(self.copyright_regex, copyright)
        if not regx:
            self._log.warn(
                (
                    "Copyright regex returned no results but "
                    "we have a copyright, please make a bug report with `beets -vv`."
                )
            )
            self._log.debug(f"Copyright: {copyright}")
            return ""

        # The last group, if multiple were found, tends to be the correct one.
        return regx[-1]

    def _track_to_trackinfo(
        self, track: tidalapi.Track, album: tidalapi.Album | None = None
    ) -> TrackInfo:
        """Converts a TIDAL track to a beets TrackInfo"""
        # Create basic trackinfo with standard fields
        trackinfo = TrackInfo(
            title=track.name,
            track_id=track.id,
            artist=track.artist.name,
            artist_id=track.artist.id,
            album=track.album.name,
            length=track.duration,
            medium=track.volume_num,
            medium_index=track.track_num,
            index=track.track_num,
            data_source=self.data_source,
            data_url=track.share_url,
            isrc=track.isrc,
            artists=[artist.name for artist in track.artists],
            artists_ids=[str(artist.id) for artist in track.artists],
            label=self._parse_copyright(track.copyright),
        )

        # Add TIDAL specific metadata
        trackinfo.tidal_track_id = track.id
        trackinfo.tidal_track_popularity = track.popularity  # Range: 0 to 100
        trackinfo.tidal_artist_id = track.artist.id
        trackinfo.tidal_album_id = track.album.id

        # If we're given an album, add it's data to the track.
        # Tidal does NOT return a lot of info on searches to save on bandwidth.
        if album:
            trackinfo.medium_total = album.num_tracks

        return trackinfo

    def _search_from_metadata(
        self, item: Item, limit: int = 10
    ) -> list[tidalapi.Track]:
        """Searches TIDAL for tracks matching the given item.

        Currently, this function searches for title, album, artist,
        alternative artists, and tracks from album results."""
        self._log.debug(f"_search_from_metadata running for {item}")

        query = []
        tracks = []

        # Search using title
        if item.title:
            query = [item.title]
            results = self._tidal_search(
                " ".join(query),
                tidalapi.Track,
                limit=limit,
            )
            trackids = [x.id for x in results]
            tracks += results

        # Search using title + artist
        if item.artist:
            query = [item.title, item.artist]
            results = self._tidal_search(
                " ".join(query),
                tidalapi.Track,
                limit=limit,
            )
            trackids += [x.id for x in results]
            tracks += results

        # Search using title + artist + album
        if item.album:
            query = [item.title, item.artist, item.album]
            trackids += [x.id for x in tracks]
            results = self._tidal_search(
                " ".join(query),
                tidalapi.Track,
                limit=limit,
            )
            trackids += [x.id for x in results]
            tracks += results

        # Search using title + album
        if item.album:
            query = [item.title, item.album]
            results = self._tidal_search(
                " ".join(query),
                tidalapi.Track,
                limit=limit,
            )
            trackids += [x.id for x in results]
            tracks += results

        # Search using title + primary artist + alternative artists
        maxaltartists = self.config["search_max_altartists"].as_number()

        if item.artists and maxaltartists > 0:
            self._log.debug(
                "Track has alternative artists... adding them to query"
            )
            if len(item.artists) > maxaltartists:
                self._log.debug(
                    (
                        f"We have {len(item.artists)} alternative artists"
                        f"with a max of {maxaltartists}"
                    )
                )

            for artist in item.artists[:maxaltartists]:
                query.append(artist)
                results = self._tidal_search(
                    " ".join(query), tidalapi.Track, limit=limit
                )
                trackids += [x.id for x in results]
                tracks += results

        # Search using album
        # Does not exist for singletons (or albums imported using -s)
        if item.album:
            self._log.debug("Searching using album")
            for album in self._tidal_search(item.album, tidalapi.Album):
                self._log.debug(
                    f"Using album {album.name} from {album.artist.name}"
                )
                for track in album.tracks():
                    tracks.append(track)
                    trackids.append(track.id)

        # Reverse list so the more specific result is first
        tracks = list(reversed(tracks))

        # Remove duplicates
        trackids = []
        newtracks = []
        for track in tracks:
            if track.id in trackids:
                self._log.debug(f"Removing duplicate track {track.id}")
                continue
            else:
                trackids.append(track.id)
                newtracks.append(track)

        tracks = newtracks
        return tracks

    @cachetools.cached(
        cache=cachetools.LFUCache(maxsize=4096),
        key=lambda self, query, rtype, *args, **kwargs: (query, rtype),
        info=True,
    )
    @backoff.on_exception(
        backoff.expo,
        tidalapi.exceptions.TooManyRequests,
        max_tries=rate_limit_retries,
        on_backoff=backoff_handler,
        factor=2,
    )
    def _tidal_search(
        self,
        query: str,
        rtype: tidalapi.Track | tidalapi.Album,
        *args: list[Any],
        **kwargs: dict[Any, Any],
    ) -> tidalapi.Track | tidalapi.Album:
        """Simple wrapper for TIDAL search
        Used to implement rate limiting and query fixing"""
        assert self.sess is tidalapi.session.Session
        # Both of the substitutions borrowed from https://github.com/arsaboo/beets-tidal/blob/main/beetsplug/tidal.py
        # Strip non-word characters from query. Things like "!" and "-" can
        # cause a query to return no results, even if they match the artist or
        # album title. Use `re.UNICODE` flag to avoid stripping non-english
        # word characters.
        query = re.sub(r"(?u)\W+", " ", query)

        # Strip medium information from query, Things like "CD1" and "disk 1"
        # can also negate an otherwise positive result.
        query = re.sub(r"(?i)\b(CD|disc)\s*\d+", "", query)

        if not rtype == tidalapi.Track and not tidalapi.Album == rtype:
            raise ValueError(
                "Only Track, Album rtypes are supported in _tidal_search"
            )

        # Execute query
        self._log.debug(
            f"Using query {query} in _tidal_search, returning type {rtype}"
        )
        results = self.sess.search(query, [rtype], *args, **kwargs)

        returnresults = []

        # Process top_hit
        # It can not exist and it can also be a completely different type from rtype
        if results["top_hit"] and isinstance(results["top_hit"], rtype):
            returnresults.append(results["top_hit"])

            # Strip top_hit from the other results so it is not duplicated
            if rtype == tidalapi.Track:
                results["tracks"] = [
                    x for x in results["tracks"] if x.id != returnresults[0].id
                ]
            elif rtype == tidalapi.Album:
                results["albums"] = [
                    x for x in results["albums"] if x.id != returnresults[0].id
                ]

        else:
            self._log.debug(
                (
                    "Not using top_hit as it doesn't exist "
                    "or is the wrong type"
                )
            )

        # Shove the results from the tidalapi call to our list
        if rtype == tidalapi.Track:
            returnresults = results["tracks"]
        elif rtype == tidalapi.Album:
            returnresults = results["albums"]

        return returnresults

    @cachetools.cached(
        cache=cachetools.LFUCache(maxsize=4096),
        key=lambda self, track: track.id,
        info=True,
    )
    # _get_lyrics has a much higher factor as it is much more rate limited by TIDAL than
    # the metadata API
    @backoff.on_exception(
        backoff.expo,
        tidalapi.exceptions.TooManyRequests,
        max_tries=rate_limit_retries,
        on_backoff=backoff_handler,
        base=5,
        factor=3,
    )
    def _get_lyrics(self, track: tidalapi.Track) -> str | None:
        """Obtains lyrics from a TIDAL track"""
        self._log.debug(f"Grabbing lyrics for track {track.id}")

        # Grab lyrics
        try:
            lyrics: tidalapi.Lyrics = track.lyrics()
        except tidalapi.exceptions.MetadataNotAvailable:
            self._log.info(f"Lyrics not available for track {track.id}")
            return None

        # Return either synced lyrics or unsynced depending on config and availability
        if self.config["synced_lyrics"]:
            if lyrics.subtitles:
                self._log.debug(
                    f"Synced lyrics are available for track {track.id}"
                )
                return lyrics.subtitles
            else:
                self._log.info(
                    (
                        f"Synced lyrics not available for track {track.id},"
                        "returning unsynced lyrics"
                    )
                )
                return lyrics.text
        else:
            return lyrics.text

    def _validate_lyrics(
        self, lib_item: Item, tidal_item: tidalapi.Track
    ) -> bool:
        """Validates lyrics retrieved from TIDAL

        Currently we just use the difference of length in the TIDAL Item vs
        the Library item."""
        self._log.debug(f"Validating lyrics for {lib_item.title}!")
        maxdiff = self.config["max_lyrics_time_difference"].as_number()

        if maxdiff >= 1:
            # Validate that both the item and the Tidal metadata have values
            if not lib_item.length or tidal_item.duration == -1:
                self._log.debug(
                    (
                        "Not using duration difference to validate lyrics "
                        "as one or both items don't have a duration!"
                    )
                )
                return bool(self.config["lyrics_no_duration_valid"])

            self._log.debug("Using duration difference to validate lyrics")
            self._log.debug(
                (
                    f"Item duration: {lib_item.length}, "
                    f"Tidal duration: {tidal_item.duration}"
                )
            )

            # Calculate difference
            difference = abs(lib_item.length - tidal_item.duration)
            difference_over = abs(maxdiff - difference)

            if difference > maxdiff:
                self._log.debug(
                    (
                        f"Not using lyrics for {lib_item.title}"
                        f"as difference is {difference_over} over the max of {maxdiff}"
                    )
                )
                return False
        else:
            self._log.debug(
                (
                    "Not using timestamp lyrics validation "
                    "due to user configuration"
                )
            )

        # Nothing above invalidated the lyrics, assuming valid
        return True

    def _search_lyrics(self, item: Item, limit: int = 10) -> str | None:
        """Searches for lyrics using a non-TIDAL metadata source"""
        self._log.debug(
            f"Searching for lyrics from non-TIDAL metadata for {item.title}"
        )

        tracks = self._search_from_metadata(item, limit=limit)

        # Return lyrics for the first track that has valid lyrics
        for track in tracks:
            lyric = self._get_lyrics(track)
            if lyric and self._validate_lyrics(item, track):
                return lyric

        self._log.info(f"No valid results found for {item.title}")
        return None

    def _process_item(self, item: Item) -> None:
        """Processes an item from the import stage

        This is used to simplify the stage loop."""
        assert self.sess is tidalapi.session.Session

        # Fetch lyrics if enabled
        if self.config["lyrics"]:
            # Don't overwrite lyrics
            if not self.config["overwrite_lyrics"] and item.lyrics:
                self._log.info(
                    "Not fetching lyrics because item already has them"
                )
                return

            self._log.debug("Fetching lyrics during import... this may fail")
            # Use tidal_track_id if defined, aka the metadata came from us
            if item.get("tidal_track_id", None):
                self._log.debug(
                    f"Using tidal_track_id of {item.tidal_track_id} to fetch lyrics!"
                )
                try:
                    track = self.sess.track(item.tidal_track_id)
                except tidalapi.exceptions.ObjectNotFound:
                    self._log.warn(
                        "tidal_track_id is defined but the API returned not found"
                    )
                    return

                item.lyrics = self._get_lyrics(track)
            else:
                self._log.debug("tidal_track_id is undefined... searching")
                item.lyrics = self._search_lyrics(
                    item, limit=self.config["lyrics_search_limit"].as_number()
                )

            item.store()

    def write_file(self, item: Item, path: str, tags: dict[Any, Any]) -> None:
        self._log.debug("Running write handler")
        # Write out lyrics to sidecar file if enabled
        if self.config["write_sidecar"] and item.lyrics:
            # Do tons of os.path operations to get the sidecar path
            filepath, filename = os.path.split(syspath(path))
            basename, ext = os.path.splitext(filename)
            sidecar_file = f"{basename}.lrc"
            sidecar_path = os.path.join(filepath, sidecar_file)

            # Don't overwrite lyrics if we aren't suppose to
            if (
                os.path.exists(sidecar_path)
                and not self.config["overwrite_lyrics"]
            ):
                self._log.debug(
                    (
                        "Not writing sidecar file "
                        "as it already exists and overwrite_lyrics is False"
                    )
                )
                return

            self._log.debug(f"Saving lyrics to sidecar file {sidecar_path}")

            # Save lyrics
            with open(sidecar_path, "w") as file:
                file.write(item.lyrics)

    def import_begin(self) -> None:
        # Check for session and throw user error if we aren't logged in
        self._load_session(fatal=True)
        assert self.sess is tidalapi.session.Session

    def stage(self, session: ImportSession, task: ImportTask) -> None:
        self._log.debug("Running import stage")
        if not self.config["auto"]:
            self._log.debug("Not processing further due to auto being False")
            return

        for item in task.imported_items():
            self._process_item(item)

            self._log.debug(
                f"_get_lyrics cache: {self._get_lyrics.cache_info()}"
            )
            self._log.debug(
                f"_tidal_search cache: {self._tidal_search.cache_info()}"
            )
