"""Update and sync Plex music library.

Plex users enter the Plex Token to enable updating.
Put something like the following in your config.yaml to configure:
    plex:
        host: localhost
        token: token
"""

import os

from beets import config, ui
from beets.dbcore import types
from beets.library import DateType
from beets.plugins import BeetsPlugin
from plexapi import exceptions
from plexapi.server import PlexServer


class PlexSync(BeetsPlugin):
    """Define plexsync class."""
    data_source = 'Plex'

    item_types = {
        'plex_key': types.STRING,
        'plex_guid': types.STRING,
        'plex_ratingkey': types.INTEGER,
        'plex_userrating': types.FLOAT,
        'plex_skipcount': types.INTEGER,
        'plex_viewcount': types.INTEGER,
        'plex_skipcount': types.INTEGER,
        'plex_lastviewedat': DateType(),
        'plex_lastratedat': DateType(),
    }

    def __init__(self):
        """Initialize plexsync plugin."""
        super().__init__()

        # Adding defaults.
        config['plex'].add({
            'host': 'localhost',
            'port': 32400,
            'token': '',
            'library_name': 'Music',
            'secure': False,
            'ignore_cert_errors': False})

        config['plex']['token'].redact = True
        baseurl = "http://" + config['plex']['host'].get() + ":" \
            + str(config['plex']['port'].get())
        try:
            self.plex = PlexServer(baseurl,
                                   config['plex']['token'].get())
        except exceptions.Unauthorized:
            raise ui.UserError('Plex authorization failed')
        try:
            self.music = self.plex.library.section(
                config['plex']['library_name'].get())
        except exceptions.NotFound:
            raise ui.UserError(f"{config['plex']['library_name']} \
                library not found")
        self.register_listener('database_change', self.listen_for_db_change)

    def listen_for_db_change(self, lib, model):
        """Listens for beets db change and register the update for the end."""
        self.register_listener('cli_exit', self._plexupdate)

    def commands(self):
        """Add beet UI commands to interact with Plex."""
        plexupdate_cmd = ui.Subcommand(
            'plexupdate', help=f'Update {self.data_source} library')

        def func(lib, opts, args):
            self._plexupdate()

        plexupdate_cmd.func = func

        # plexsync command
        sync_cmd = ui.Subcommand('plexsync',
                                 help="fetch track attributes from Plex")
        sync_cmd.parser.add_option(
            '-f', '--force', dest='force_refetch',
            action='store_true', default=False,
            help='re-sync Plex data when already present'
        )

        def func_sync(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self._fetch_plex_info(items, ui.should_write(),
                                  opts.force_refetch)

        sync_cmd.func = func_sync

        # plexplaylistadd command
        playlistadd_cmd = ui.Subcommand('plexplaylistadd',
                                        help="add tracks to Plex playlist")

        playlistadd_cmd.parser.add_option('-p', '--playlist',
                                          default='Beets',
                                          help='add playlist to Plex')

        def func_playlist_add(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self._plex_add_playlist_item(items, opts.playlist)

        playlistadd_cmd.func = func_playlist_add

        # plexplaylistremove command
        playlistrem_cmd = ui.Subcommand('plexplaylistremove',
                                        help="Plex playlist to edit")

        playlistrem_cmd.parser.add_option('-p', '--playlist',
                                          default='Beets',
                                          help='Plex playlist to edit')

        def func_playlist_rem(lib, opts, args):
            items = lib.items(ui.decargs(args))
            self._plex_remove_playlist_item(items, opts.playlist)

        playlistrem_cmd.func = func_playlist_rem

        return [plexupdate_cmd, sync_cmd, playlistadd_cmd, playlistrem_cmd]

    def _plexupdate(self):
        """Update Plex music library."""
        try:
            self.music.update()
            self._log.info('Update started.')
        except exceptions.PlexApiException:
            self._log.warning("{} Update failed",
                              self.config['plex']['library_name'])

    def _fetch_plex_info(self, items, write, force):
        """Obtain track information from Plex."""
        for index, item in enumerate(items, start=1):
            self._log.info('Processing {}/{} tracks - {} ',
                           index, len(items), item)
            # If we're not forcing re-downloading for all tracks, check
            # whether the popularity data is already present
            if not force:
                if 'plex_userrating' in item:
                    self._log.debug('Plex rating already present for: {}',
                                    item)
                    continue
            plex_track = self.search_plex_track(item)
            if plex_track is None:
                self._log.info('No track found for: {}', item)
                continue
            item.plex_key = plex_track.key
            item.plex_guid = plex_track.guid
            item.plex_ratingkey = plex_track.ratingKey
            item.plex_userrating = plex_track.userRating
            item.plex_skipcount = plex_track.skipCount
            item.plex_viewcount = plex_track.viewCount
            item.plex_skipcount = plex_track.skipCount
            item.plex_lastviewedat = plex_track.lastViewedAt
            item.plex_lastratedat = plex_track.lastRatedAt
            item.store()
            if write:
                item.try_write()

    def search_plex_track(self, item):
        """Fetch the Plex track key."""
        tracks = self.music.searchTracks(
            **{'album.title': item.album, 'track.title': item.title})
        if len(tracks) == 1:
            return tracks[0]
        elif len(tracks) > 1:
            for track in tracks:
                if self.compare_file_name(track, item):
                    return track
        else:
            return None
        if len(tracks) == 0:
            return None
        elif len(tracks) == 1:
            return tracks[0]

    def get_plex_filename(self, track):
        """Fetch Plex filename."""
        return os.path.basename(track.media[0].parts[0].file)

    def compare_file_name(self, track, item):
        """Compare file names."""
        if self.get_plex_filename(track) == os.path.basename(item.path):
            return True
        else:
            return False

    def _plex_add_playlist_item(self, items, playlist):
        """Add items to Plex playlist."""
        try:
            plst = self.plex.playlist(playlist)
            playlist_set = set(plst.items())
        except exceptions.NotFound:
            plst = None
            playlist_set = set()
        plex_set = {self.plex.fetchItem(item.plex_ratingkey)
                    for item in items}
        to_add = plex_set - playlist_set
        self._log.info('Adding {} tracks to {} playlist',
                       len(to_add), playlist)
        if plst is None:
            self._log.info('{} playlist will be created', playlist)
            self.plex.createPlaylist(playlist, items=list(to_add))
        else:
            plst.addItems(items=list(to_add))

    def _plex_remove_playlist_item(self, items, playlist):
        """Remove items from Plex playlist."""
        try:
            plst = self.plex.playlist(playlist)
            playlist_set = set(plst.items())
        except exceptions.NotFound:
            self._log.error('{} playlist not found', playlist)
            return
        plex_set = {self.plex.fetchItem(item.plex_ratingkey)
                    for item in items}
        to_remove = plex_set.intersection(playlist_set)
        self._log.info('Removing {} tracks from {} playlist',
                       len(to_remove), playlist)
        plst.removeItems(items=list(to_remove))
