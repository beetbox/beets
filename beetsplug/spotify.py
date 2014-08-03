import json, re, webbrowser
import requests
from pprint import pprint
from operator import attrgetter
from beets.plugins import BeetsPlugin
from beets.ui import decargs
from beets import config, ui, library
from requests.exceptions import HTTPError

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
            'tiebreak' : 'popularity',
            'show_failures': False,
            'verbose': False,
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
        spotify_cmd = ui.Subcommand('spotify',
            help='build spotify playlist of results'
        )
        spotify_cmd.parser.add_option('-m', '--mode', action='store',
            help='"open" to open spotify with playlist, "list" to copy/paste (default)'
        )
        spotify_cmd.parser.add_option('-f', '--show_failures', action='store_true',
            help='Print out list of any tracks that did not match a Sptoify ID'
        )
        spotify_cmd.parser.add_option('-v', '--verbose', action='store_true',
            help='show extra output'
        )
        spotify_cmd.func = queries
        return [spotify_cmd]

    def parse_opts(self, opts):
        if opts.mode:
            self.config['mode'].set(opts.mode)

        if opts.show_failures:
            self.config['show_failures'].set(True)

        if self.config['mode'].get() not in ['list', 'open']:
            print self.config['mode'].get() + " is not a valid mode"
            return False

        self.opts = opts
        return True

    def query_spotify(self, lib, query):

        results = []
        failures = []

        items = lib.items(query)

        if not items:
            self.out("Your beets query returned no items, skipping spotify")
            return

        print "Processing " + str(len(items)) + " tracks..."

        for item in items:

            # Apply regex transformations if provided
            for regex in self.config['regex'].get():
                if not regex['field'] or not regex['search'] or not regex['replace']:
                    continue
                value = item[regex['field']]
                item[regex['field']] = re.sub(regex['search'], regex['replace'], value)

            # Custom values can be passed in the config (just in case)
            artist = item[self.config['artist_field'].get()]
            album = item[self.config['album_field'].get()]
            query = item[self.config['track_field'].get()]
            search_url = query + " album:" + album + " artist:" + artist

            # Query the Web API for each track and look for the items' JSON data
            r = requests.get(self.base_url, params={"q": search_url, "type": "track"})
            self.out(r.url)
            try:
                r.raise_for_status()
            except HTTPError as e:
                self.out("URL returned a " + e.response.status_code + "error")
                failures.append(search_url)
                continue

            r_data = r.json()['tracks']['items']
            
            # Apply market filter if requested
            region_filter = self.config['region_filter'].get()
            if region_filter:
                r_data = filter(lambda x: region_filter in x['available_markets'], r_data)
            
            # Simplest, take the first result
            chosen_result = None
            if len(r_data) == 1 or self.config['tiebreak'].get() == "first":
                self.out("Spotify track(s) found, count: " + str(len(r_data)))
                chosen_result = r_data[0]
            elif len(r_data) > 1:
                # Use the popularity filter
                self.out("Most popular track chosen, count: " + str(len(r_data)))
                chosen_result = max(r_data, key=lambda x: x['popularity'])

            if chosen_result:
                results.append(chosen_result)
            else:
                self.out("No spotify track found: " + search_url)
                failures.append(search_url)

        failure_count = len(failures)
        if failure_count > 0:
            if self.config['show_failures'].get():
                print
                print str(failure_count) + " track(s) did not match a Spotify ID"
                print "#########################"
                for track in failures:
                    print "track:" + track
                print "#########################"
            else:
                print str(failure_count) + " track(s) did not match a Spotify ID, --show_failures to display"

        return results

    def output_results(self, results):
        if results:
            ids = map(lambda x: x['id'], results)
            if self.config['mode'].get() == "open":
                print "Attempting to open Spotify with playlist"
                spotify_url = self.playlist_partial + ",".join(ids)
                webbrowser.open(spotify_url)

            else:
                print
                print "Copy everything between the hashes and paste into a Spotify playlist"
                print "#########################"
                for item in ids:
                    print unicode.encode(self.open_url + item)
                print "#########################"
        else:
            print "No Spotify tracks found from beets query"

    def out(self, msg):
        if self.config['verbose'].get() or self.opts.verbose:
            print msg;

