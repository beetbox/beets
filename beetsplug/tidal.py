import json
import optparse
import re
from datetime import datetime

import backoff
import confuse
from tidalapi import *

from beets import ui
from beets.autotag.hooks import AlbumInfo, TrackInfo
from beets.importer import ImportSession, ImportTask
from beets.library import Library
from beets.plugins import BeetsPlugin
import os.path
from beets.util import bytestring_path, displayable_path, normpath, syspath

""" TidalPlugin is a TIDAL source for the autotagger """


class TidalPlugin(BeetsPlugin):
    data_source = "tidal"
    track_share_regex = r"(tidal.com\/browse\/track\/)([0-9]*)(\?u)"  # Format: https://tidal.com/browse/track/221182395?u
    album_share_regex = r"(tidal.com\/browse\/album\/)([0-9]*)(\?u)"  # Format: https://tidal.com/browse/album/221182592?u
    # Number of times to retry when we get a TooManyRequests exception, this implements an exponential backoff.
    rate_limit_retries = 16

    def __init__(self):
        super().__init__()
        self.import_stages = [self.stage]

        # Import config
        self.config.add(
            {
                "auto": True,
                "lyrics": True,
                "synced_lyrics": True,
                "overwrite_lyrics": True,
                "tokenfile": "tidal_token.json",
                "write_sidecar": False # Write lyrics to LRC file
            }
        )

        self.sessfile = self.config["tokenfile"].get(
            confuse.Filename(in_app_dir=True)
        )

        # tidalapi.session.Session object we throw around to execute API calls with
        self.sess = None

    """ Loads a TIDAL session from a JSON file to the class singleton """

    def _load_session(self):
        if self.sess:
            self._log.debug(
                "Not attempting to load session state as we already have a session!"
            )
            return True

        self._log.debug(
            f"Attempting to load session state from {self.sessfile}!"
        )
        self.sess = session.Session()

        # Attempt to load OAuth data from token file
        try:
            with open(self.sessfile) as file:
                sess_data = json.load(file)

                # Don't keep trying to ping the API with a cleared session file
                if not sess_data:
                    self._log.debug(
                        "Session state file has been cleared... please login"
                    )

                    return False
        except OSError:
            # Error occured, most likely token file does not exist.
            self._log.debug("Session state file does not exist")
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

                    json.dump({})

                return False

            return True

    """ Saves a TIDAL session to a JSON file """

    def _save_session(self, sess):
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

    """ Creates a session to use with the TIDAL API """

    def _login(self):
        self.sess = session.Session()
        login, future = self.sess.login_oauth()
        print(
            f"Open the following URL to complete login: https://{login.verification_uri_complete}"
        )
        print(f"The link expires in {int(login.expires_in)} seconds!")

        if not future.result():
            self._log.error("Login failure! See above output for more info.")

        self._save_session(self.sess)

    def cmd_main(self, lib: Library, opts: optparse.Values, arg: list):
        if opts.login:
            self._log.debug("Running login routine!")
            self._login()
        elif opts.dump_sess:
            self._log.debug(f"Session state file: {self.sessfile}")
            try:
                with open(self.sessfile) as file:
                    sess_data = json.load(file)
                    print(sess_data)
            except OSError:
                self._log.info(
                    f"Session state file {self.sessfile} does not exist!"
                )

    def commands(self):
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
            "-d",
            "--dump",
            dest="dump_sess",
            action="store_true",
            default=False,
            help="dump session state",
        )

        cmd.func = self.cmd_main
        return [cmd]

    """ Return TIDAL metadata for a specific TIDAL Album ID """

    def album_for_id(self, album_id):
        # Check for session
        self._log.debug(f"Running album_for_id with track {album_id}!")
        if not self._load_session():
            self._log.info(
                "Skipping album_for_id because we have no session! Please login."
            )
            return None

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
                    f"Album share URL parsing failed because we got {len(regx.groups())} groups when 3 was expected"
                )
                return None

            tidal_album_id = int(regx.groups()[-2])

        try:
            album = self.sess.album(tidal_album_id)
        except exceptions.ObjectNotFound:
            self._log.debug(f"No album for ID {tidal_album_id}")
            return None

        return self._album_to_albuminfo(album)

    """ Return TIDAL metadata for a specific TIDAL Track ID """

    def track_for_id(self, track_id):
        # Check for session
        self._log.debug(f"Running track_for_id with track {track_id}!")
        if not self._load_session():
            self._log.info(
                "Skipping track_for_id because we have no session! Please login."
            )
            return None

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
                    f"Track share URL parsing failed because we got {len(regx.groups())} groups when 3 was expected"
                )
                return None

            tidal_track_id = int(regx.groups()[-2])

        try:
            track = self.sess.track(tidal_track_id, with_album=True)
        except exceptions.ObjectNotFound:
            self._log.debug(f"No track for ID {tidal_track_id}")
            return None

        return self._track_to_trackinfo(track, track.album)

    """ Returns TIDAL metadata candidates for a specific set of items, typically an album """

    def candidates(self, items, artist, album, va_likely, extra_tags):
        if not self._load_session():
            self._log.info(
                "Skipping candidates because we have no session! Please login."
            )
            return []

        candidates = []

        self._log.debug(
            "Searching for candidates using tidal_album_id from items"
        )
        for item in items:
            if item.get("tidal_album_id", None):
                try:
                    album = self._album_to_albuminfo(
                        self.sess.album(item.tidal_album_id)
                    )
                    candidates.append(album)
                except exceptions.ObjectNotFound:
                    self._log.debug(
                        f"No album found for ID {item.tidal_album_id}"
                    )

        self._log.debug(
            f"{len(candidates)} Candidates found using tidal_album_id from items!"
        )
        self._log.debug("Searching for candidates using album + artist search")

        # Create query
        query = []
        if album:
            query.append(album)
        if artist:
            query.append(artist)

        candidates = candidates + self._search_album(" ".join(query))

        return candidates

    """ Returns TIDAL metadata candidates for a specific item """

    def item_candidates(self, item, artist, album):
        if not self._load_session():
            self._log.info(
                "Skipping item_candidates because we have no session! Please login."
            )
            return []

        self._log.debug(f"Searching TIDAL for {item}!")

        if item.title:
            return self._search_track(item.title)
        elif item.album:
            return self._search_track(item.album, limit=25)
        elif item.artist:
            return self._search_track(item.artist, limit=50)

        return []

    """ Converts a TIDAL album to a beets AlbumInfo """

    def _album_to_albuminfo(self, album):
        tracks = []

        # Process tracks
        # Not using sparse albums as we already have the album
        # so it's not using up any additional API calls.
        for track in album.tracks(sparse_album=False):
            tracks.append(self._track_to_trackinfo(track, album))

        albuminfo = AlbumInfo(
            album=album.name,
            album_id=album.id,
            tidal_album_id=album.id,
            artist=album.artist.name,
            artist_id=album.artist.id,
            tidal_artist_id=album.artist.id,
            va=len(album.artists) == 1
            and album.artist.name.lower() == "various artists",
            mediums=album.num_volumes,
            data_source=self.data_source,
            data_url=album.share_url,
            tracks=tracks,
            barcode=album.universal_product_number,
            albumtype=album.type,
        )

        # Add release date if we have one
        if album.release_date:
            albuminfo.year = album.release_date.year
            albuminfo.month = album.release_date.month
            albuminfo.day = album.release_date.day

        return albuminfo

    """ Converts a TIDAL track to a beets TrackInfo """

    def _track_to_trackinfo(self, track, album=None):
        trackinfo = TrackInfo(
            title=track.name,
            track_id=track.id,
            tidal_track_id=track.id,
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
        )

        # If we're given an album, add it's data to the track.
        # Tidal does NOT return a lot of info on searches to save on bandwidth.
        if album:
            trackinfo.medium_total = album.num_tracks

        # if self.config["lyrics"]:
        #    trackinfo.lyrics = self._get_lyrics(track)

        return trackinfo

    """ Searches TIDAL for tracks matching the query """

    def _search_track(self, query, limit=10, offset=0):
        self._log.debug(f"_search_track query {query}")
        results = self._tidal_search(query, [Track], limit, offset)

        candidates = []

        # top_hit is the most relevant to our query, add that first.
        if results["top_hit"]:
            album = self.sess.album(results["top_hit"].album.id)
            candidates = [self._track_to_trackinfo(results["top_hit"], album)]

        for result in results["tracks"]:
            album = self.sess.album(result.album.id)
            candidates.append(self._track_to_trackinfo(result, album))

        self._log.debug(f"_search_track found {len(candidates)} results")
        return candidates

    """ Searches TIDAL for albums matching the query """

    def _search_album(self, query, limit=10, offset=0):
        self._log.debug(f"_search_album query {query}")
        results = self._tidal_search(query, [Album], limit, offset)
        candidates = []

        # top_hit is the most relevant to our query, add that first.
        if results["top_hit"]:
            candidates = [self._album_to_albuminfo(results["top_hit"])]

        for result in results["albums"]:
            candidates.append(self._album_to_albuminfo(result))

        self._log.debug(f"_search_album found {len(candidates)} results")
        return candidates

    """ Simple wrapper for TIDAL search to check for session and to implement rate limiting """

    @backoff.on_exception(
        backoff.expo, exceptions.TooManyRequests, max_tries=rate_limit_retries
    )
    def _tidal_search(self, *args, **kwargs):
        if not self._load_session():
            self.log.debug(
                "Cannot perform search with no session... please login."
            )

            # We only use these three keys, even though the API returns more
            return {"albums": [], "tracks": [], "top_hit": None}

        return self.sess.search(*args, **kwargs)

    """ Grabs lyrics from a TIDAL track """

    @backoff.on_exception(
        backoff.expo, exceptions.TooManyRequests, max_tries=rate_limit_retries
    )
    def _get_lyrics(self, track):
        if not self._load_session():
            self._log.debug(
                "Cannot grab lyrics with no session... please login."
            )
            return None

        self._log.debug(f"Grabbing lyrics for track {track.id}")

        # Grab lyrics
        try:
            lyrics = track.lyrics()
        except exceptions.MetadataNotAvailable:
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
                    f"Synced lyrics not available for track {track.id}, returning unsynced lyrics"
                )
                return lyrics.text
        else:
            return lyrics.text

    """ Searches for lyrics using a non-TIDAL metadata source """

    def _search_lyrics(self, item, limit=10):
        if not self._load_session():
            self._log.debug(
                "Cannot grab lyrics with no session... please login."
            )
            return None

        self._log.debug(
            f"Searching for lyrics from non-TIDAL metadata for {item.title}"
        )

        query = []
        tracks = []

        # Search using title
        if item.title:
            query.append(item.title)
            trackids = [x.tidal_track_id for x in tracks]
            tracks += self._search_track(" ".join(query), limit=limit)

        # Search using title + artist
        if item.artist:
            query.append(item.artist)
            tracks += self._search_track(" ".join(query), limit=limit)

        # Search using title + artist + album
        if item.album:
            query.append(item.album)
            tracks += self._search_track(" ".join(query), limit=limit)

        # Reverse list so the more specific result is first
        tracks = reversed(tracks)

        # Remove duplicates
        trackids = []
        newtracks = []
        for track in tracks:
            if track.tidal_track_id in trackids:
                self._log.debug(
                    f"Removing duplicate track {track.tidal_track_id}"
                )
                continue
            else:
                trackids.append(track.tidal_track_id)
                newtracks.append(track)

        tracks = newtracks

        # Fetch lyrics for tracks
        for track in tracks:
            track.lyrics = self._get_lyrics(
                self.sess.track(track.tidal_track_id)
            )

        # Filter out tracks with no lyrics
        tracks = [x for x in tracks if x.lyrics != None]

        if not tracks:
            self._log.info(f"No results found for {item.title}")
            return None

        # Pick best one, aka the first one with lyrics
        return tracks[0].lyrics

    def _process_item(self, item):
            # Fetch lyrics if enabled
            if self.config["lyrics"]:
                # Don't overwrite lyrics
                if not self.config["overwrite_lyrics"] and item.lyrics:
                    self._log.info(
                        "Not fetching lyrics because item already has them"
                    )
                    return

                self._log.debug(
                    "Fetching lyrics during import... this may fail"
                )
                # Use tidal_track_id if defined, aka the metadata came from us
                if item.get("tidal_track_id", None):
                    self._log.debug(
                        f"Using tidal_track_id of {item.tidal_track_id} to fetch lyrics!"
                    )
                    try:
                        track = self.sess.track(track)
                    except exceptions.ObjectNotFound:
                        self._log.warn(
                            "tidal_track_id is defined but the API returned not found"
                        )
                        return

                    item.lyrics = self._get_lyrics(track)
                else:
                    self._log.debug(
                        "tidal_track_id is undefined... searching"
                    )
                    item.lyrics = self._search_lyrics(item)

                # Write out item if global write is enabled
                if ui.should_write():
                    self._log.debug(
                        "Global write is enabled... writing lyrics"
                    )
                    item.try_write()

                # Write out lyrics to sidecar file if enabled
                if self.config["write_sidecar"] and item.lyrics:
                    self._log.debug("write_sidecar is enabled and we have lyrics... writing sidecar files")

                    # Do tons of os.path operations to get the sidecar path
                    filepath, filename = os.path.split(syspath(item.path))
                    basename, ext = os.path.splitext(filename)
                    sidecar_file = f"{basename}.lrc"
                    sidecar_path = os.path.join(filepath, sidecar_file)

                    self._log.debug(f"Saving lyrics to sidecar file {sidecar_path}")

                    # Save lyrics
                    with open(sidecar_path, "w") as file:
                        file.write(item.lyrics)

                item.store()

    def stage(self, session: ImportSession, task: ImportTask):
        self._log.debug("Running import stage for TidalPlugin!")

        if not self._load_session():
            self._log.info(
                "Skipping import stage because we have no session! Please login."
            )
            return

        if self.config["auto"]:
            self._log.debug("Processing ImportTask as auto is True!")
            for item in task.imported_items():
                self._process_item(item)
