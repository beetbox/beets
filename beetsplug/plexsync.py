"""Updates an Plex library whenever the beets library is changed.

Plex Home users enter the Plex Token to enable updating.
Put something like the following in your config.yaml to configure:
    plex:
        host: localhost
        port: 32400
        token: token
"""

from beets import config
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from plexapi.server import PlexServer

class PlexSync(BeetsPlugin):
    data_source = 'Plex'

    def __init__(self):
        super().__init__()

        # Adding defaults.
        config['plex'].add({
            'baseurl': 'localhost',
            'port': 32400,
            'token': '',
            'library_name': 'Music',
            'secure': False,
            'ignore_cert_errors': False})

        config['plex']['token'].redact = True
        self._log.info('Plex URL {}', config['plex']['baseurl'])
        plex = PlexServer(config['plex']['baseurl'].get(),
                          config['plex']['token'].get())
        self.music = plex.library.section(config['plex']['library_name']
                                          .get())
        self.register_listener('database_change', self.listen_for_db_change)

    def listen_for_db_change(self, lib, model):
        """Listens for beets db change and register the update for the end"""
        self.register_listener('cli_exit', self._plexupdate)

    def commands(self):
        plexupdate_cmd = Subcommand(
            'plexupdate', help=f'Update {self.data_source} library'
        )

        def func(lib, opts, args):
            self._plexupdate()

        plexupdate_cmd.func = func
        return [plexupdate_cmd]

    def _plexupdate(self):
        """Update Plex music library."""

        self._log.info('Music section {}', self.music.key)
        self.music.update()
