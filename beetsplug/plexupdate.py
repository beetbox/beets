# -*- coding: utf-8 -*-

"""Updates an Plex library whenever the beets library is changed.

Plex Home users enter the Plex Token to enable updating.
Put something like the following in your config.yaml to configure:
    plex:
        host: localhost
        port: 32400
        token: token
"""
from __future__ import division, absolute_import, print_function

import requests
import xml.etree.ElementTree as ET
from six.moves.urllib.parse import urljoin, urlencode
from beets import config
from beets.plugins import BeetsPlugin


def get_music_section(host, port, token, library_name):
    """Getting the section key for the music library in Plex.
    """
    api_endpoint = append_token('library/sections', token)
    url = urljoin('http://{0}:{1}'.format(host, port), api_endpoint)

    # Sends request.
    r = requests.get(url)

    # Parse xml tree and extract music section key.
    tree = ET.fromstring(r.content)
    for child in tree.findall('Directory'):
        if child.get('title') == library_name:
            return child.get('key')


def update_plex(host, port, token, library_name):
    """Sends request to the Plex api to start a library refresh.
    """
    # Getting section key and build url.
    section_key = get_music_section(host, port, token, library_name)
    api_endpoint = 'library/sections/{0}/refresh'.format(section_key)
    api_endpoint = append_token(api_endpoint, token)
    url = urljoin('http://{0}:{1}'.format(host, port), api_endpoint)

    # Sends request and returns requests object.
    r = requests.get(url)
    return r


def append_token(url, token):
    """Appends the Plex Home token to the api call if required.
    """
    if token:
        url += '?' + urlencode({'X-Plex-Token': token})
    return url


class PlexUpdate(BeetsPlugin):
    def __init__(self):
        super(PlexUpdate, self).__init__()

        # Adding defaults.
        config['plex'].add({
            u'host': u'localhost',
            u'port': 32400,
            u'token': u'',
            u'library_name': u'Music'})

        self.register_listener('database_change', self.listen_for_db_change)

    def listen_for_db_change(self, lib, model):
        """Listens for beets db change and register the update for the end"""
        self.register_listener('cli_exit', self.update)

    def update(self, lib):
        """When the client exists try to send refresh request to Plex server.
        """
        self._log.info(u'Updating Plex library...')

        # Try to send update request.
        try:
            update_plex(
                config['plex']['host'].get(),
                config['plex']['port'].get(),
                config['plex']['token'].get(),
                config['plex']['library_name'].get())
            self._log.info(u'... started.')

        except requests.exceptions.RequestException:
            self._log.warning(u'Update failed.')
