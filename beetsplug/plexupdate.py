"""Updates an Plex library whenever the beets library is changed.

Put something like the following in your config.yaml to configure:
    plex:
        host: localhost
        port: 32400
"""
from __future__ import (division, absolute_import, print_function,
                        unicode_literals)

import requests
from urlparse import urljoin
import xml.etree.ElementTree as ET
from beets import config
from beets.plugins import BeetsPlugin


def get_music_section(host, port):
    """Getting the section key for the music library in Plex.
    """
    api_endpoint = 'library/sections'
    url = urljoin('http://{0}:{1}'.format(host, port), api_endpoint)

    # Sends request.
    r = requests.get(url)

    # Parse xml tree and extract music section key.
    tree = ET.fromstring(r.text)
    for child in tree.findall('Directory'):
        if child.get('title') == 'Music':
            return child.get('key')


def update_plex(host, port):
    """Sends request to the Plex api to start a library refresh.
    """
    # Getting section key and build url.
    section_key = get_music_section(host, port)
    api_endpoint = 'library/sections/{0}/refresh'.format(section_key)
    url = urljoin('http://{0}:{1}'.format(host, port), api_endpoint)

    # Sends request and returns requests object.
    r = requests.get(url)
    return r


class PlexUpdate(BeetsPlugin):
    def __init__(self):
        super(PlexUpdate, self).__init__()

        # Adding defaults.
        config['plex'].add({
            u'host': u'localhost',
            u'port': 32400})

        self.register_listener('database_change', self.listen_for_db_change)

    def listen_for_db_change(self, lib):
        """Listens for beets db change and register the update for the end"""
        self.register_listener('cli_exit', self.update)

    def update(self, lib):
        """When the client exists try to send refresh request to Plex server.
        """
        self._log.info('Updating Plex library...')

        # Try to send update request.
        try:
            update_plex(
                config['plex']['host'].get(),
                config['plex']['port'].get())
            self._log.info('... started.')

        except requests.exceptions.RequestException:
            self._log.warning('Update failed.')
