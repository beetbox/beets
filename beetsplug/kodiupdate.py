# This file is part of beets.
# Copyright 2017, Pauli Kettunen.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

"""Updates a Kodi library whenever the beets library is changed.
This is based on the Plex Update plugin.

Put something like the following in your config.yaml to configure:
    kodi:
        host: localhost
        port: 8080
        user: user
        pwd: secret
"""

import requests
from beets import config
from beets.plugins import BeetsPlugin


def update_kodi(host, port, user, password):
    """Sends request to the Kodi api to start a library refresh.
    """
    url = f"http://{host}:{port}/jsonrpc"

    """Content-Type: application/json is mandatory
    according to the kodi jsonrpc documentation"""

    headers = {'Content-Type': 'application/json'}

    # Create the payload. Id seems to be mandatory.
    payload = {'jsonrpc': '2.0', 'method': 'AudioLibrary.Scan', 'id': 1}
    r = requests.post(
        url,
        auth=(user, password),
        json=payload,
        headers=headers)

    return r


class KodiUpdate(BeetsPlugin):
    def __init__(self):
        super().__init__()

        # Adding defaults.
        config['kodi'].add({
            'host': 'localhost',
            'port': 8080,
            'user': 'kodi',
            'pwd': 'kodi'})

        config['kodi']['pwd'].redact = True
        self.register_listener('database_change', self.listen_for_db_change)

    def listen_for_db_change(self, lib, model):
        """Listens for beets db change and register the update"""
        self.register_listener('cli_exit', self.update)

    def update(self, lib):
        """When the client exists try to send refresh request to Kodi server.
        """
        self._log.info('Requesting a Kodi library update...')

        # Try to send update request.
        try:
            r = update_kodi(
                config['kodi']['host'].get(),
                config['kodi']['port'].get(),
                config['kodi']['user'].get(),
                config['kodi']['pwd'].get())
            r.raise_for_status()

        except requests.exceptions.RequestException as e:
            self._log.warning('Kodi update failed: {0}',
                              str(e))
            return

        json = r.json()
        if json.get('result') != 'OK':
            self._log.warning('Kodi update failed: JSON response was {0!r}',
                              json)
            return

        self._log.info('Kodi update triggered')
