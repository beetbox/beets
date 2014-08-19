from __future__ import print_function
import re
import webbrowser
import requests
import logging
from beets.plugins import BeetsPlugin
from beets.ui import decargs
from beets import ui
from requests.exceptions import HTTPError

log = logging.getLogger('beets')


class SpotifyPlugin(BeetsPlugin):

    # URL for the Web API of Spotify
    # Documentation here: https://developer.spotify.com/web-api/search-item/
    base_url = "https://api.spotify.com/v1/search"
    open_url = "http://open.spotify.com/track/"
    playlist_partial = "spotify:trackset:Playlist:"

    def __init__(self):
        super(SpotifyPlugin, self).__init__()
        self.config.add({
            'mode': 'list',
            'tiebreak': 'popularity',
            'show_failures': False,
            'artist_field': 'albumartist',
            'album_field': 'album',
            'track_field': 'title',
            'region_filter': None,
            'regex': []
        })

    def commands(self):
        def queries(lib, opts, args):
            success = self.parse_opts(opts)
            if success:
                results = self.query_spotify(lib, decargs(args))
                self.output_results(results)
        spotify_cmd = ui.Subcommand(
            'spotify',
            help='build a Spotify playlist'
        )
        spotify_cmd.parser.add_option(
            '-m', '--mode', action='store',
            help='"open" to open Spotify with playlist, '
                 '"list" to print (default)'
        )
        spotify_cmd.parser.add_option(
            '-f', '--show-failures', action='store_true',
            help='list tracks that did not match a Sptoify ID',
            dest='show_failures',
        )
        spotify_cmd.func = queries
        return [spotify_cmd]

    def parse_opts(self, opts):
        if opts.mode:
            self.config['mode'].set(opts.mode)

        if opts.show_failures:
            self.config['show_failures'].set(True)

        if self.config['mode'].get() not in ['list', 'open']:
            log.warn(self.config['mode'].get() + " is not a valid mode")
            return False

        self.opts = opts
        return True

    def query_spotify(self, lib, query):

        results = []
        failures = []

        items = lib.items(query)

        if not items:
            log.debug("Your beets query returned no items, skipping spotify")
            return

        log.info("Processing " + str(len(items)) + " tracks...")

        for item in items:

            # Apply regex transformations if provided
            for regex in self.config['regex'].get():
                if (
                    not regex['field'] or
                    not regex['search'] or
                    not regex['replace']
                ):
                    continue

                value = item[regex['field']]
                item[regex['field']] = re.sub(
                    regex['search'], regex['replace'], value
                )

            # Custom values can be passed in the config (just in case)
            artist = item[self.config['artist_field'].get()]
            album = item[self.config['album_field'].get()]
            query = item[self.config['track_field'].get()]
            search_url = query + " album:" + album + " artist:" + artist

            # Query the Web API for each track, look for the items' JSON data
            r = requests.get(self.base_url, params={
                "q": search_url, "type": "track"
            })
            log.debug(r.url)
            try:
                r.raise_for_status()
            except HTTPError as e:
                log.debug("URL returned a " + e.response.status_code + "error")
                failures.append(search_url)
                continue

            r_data = r.json()['tracks']['items']

            # Apply market filter if requested
            region_filter = self.config['region_filter'].get()
            if region_filter:
                r_data = filter(
                    lambda x: region_filter in x['available_markets'], r_data
                )

            # Simplest, take the first result
            chosen_result = None
            if len(r_data) == 1 or self.config['tiebreak'].get() == "first":
                log.debug("Spotify track(s) found, count: " + str(len(r_data)))
                chosen_result = r_data[0]
            elif len(r_data) > 1:
                # Use the popularity filter
                log.debug(
                    "Most popular track chosen, count: " + str(len(r_data))
                )
                chosen_result = max(r_data, key=lambda x: x['popularity'])

            if chosen_result:
                results.append(chosen_result)
            else:
                log.debug("No spotify track found: " + search_url)
                failures.append(search_url)

        failure_count = len(failures)
        if failure_count > 0:
            if self.config['show_failures'].get():
                log.info("{0} track(s) did not match a Spotify ID:".format(
                    failure_count
                ))
                for track in failures:
                    log.info("track:" + track)
                log.info("")
            else:
                log.warn(
                    str(failure_count) + " track(s) did not match "
                    "a Spotify ID; use --show-failures to display\n"
                )

        return results

    def output_results(self, results):
        if results:
            ids = map(lambda x: x['id'], results)
            if self.config['mode'].get() == "open":
                log.info("Attempting to open Spotify with playlist")
                spotify_url = self.playlist_partial + ",".join(ids)
                webbrowser.open(spotify_url)

            else:
                for item in ids:
                    print(unicode.encode(self.open_url + item))
        else:
            log.warn("No Spotify tracks found from beets query")
