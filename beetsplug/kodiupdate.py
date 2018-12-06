# -*- coding: utf-8 -*-
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

Put something like the following in your config.yaml to configure this plugin
to re-scan your entire library after importing one or more albums:
    kodi:
        host: localhost
        port: 8080
        user: user
        pwd: secret

Alternatively, you can choose to only scan each newly imported album directory.
To do so, add all the config.yaml settings above, but also add 'source' and
'library' settings that look something like this:

       source: nfs://myserver.local/music/library/
       library: /home/music/library/

The value for 'source' should be the Kodi Music source found in
.kodi/userdata/sources.xml.

The value for 'library' should be the path to your beets library.

After an album is imported, this plugin strips off the 'library' portion of
the album path and appends the remaining portion to the 'source', then issues
a Kodi update for that path.

"""
from __future__ import division, absolute_import, print_function

import requests
from beets import config
from beets.plugins import BeetsPlugin
import six
import os


def update_kodi(host, port, user, password, path=None):
    """Sends request to the Kodi api to start a library refresh.
       If 'path' is provided, only refresh that path.
    """
    url = "http://{0}:{1}/jsonrpc".format(host, port)

    """Content-Type: application/json is mandatory
    according to the kodi jsonrpc documentation"""

    headers = {'Content-Type': 'application/json'}

    # Create the payload. Id seems to be mandatory.
    payload = {'jsonrpc': '2.0', 'method': 'AudioLibrary.Scan', 'id': 1}
    if path is not None:
        payload['params'] = {'directory': path}
    r = requests.post(
        url,
        auth=(user, password),
        json=payload,
        headers=headers)

    return r


class KodiUpdate(BeetsPlugin):
    def __init__(self):
        super(KodiUpdate, self).__init__()

        # Adding defaults.
        config['kodi'].add({
            u'host': u'localhost',
            u'port': 8080,
            u'user': u'kodi',
            u'pwd': u'kodi',
            u'source': u'',
            u'library': u''})

        config['kodi']['pwd'].redact = True
        if config['source'] == '':
            # rescan entire library
            self.register_listener('database_change',
                                   self.listen_for_db_change)
        else:
            # only rescan the path to this album
            self.register_listener('album_imported',
                                   self.album_imported)

    def listen_for_db_change(self, lib, model):
        """Listens for beets db change, waits for cli exit,
        then registers the update"""
        self.register_listener('cli_exit', self.cli_exit)

    def album_imported(self, lib, album):
        source = config['kodi']['source'].get()
        library = config['kodi']['library'].get()
        apath = album.item_dir()
        suffix = os.path.relpath(apath, library)
        self.update(path=os.path.join(source, suffix.decode('utf-8')))

    def cli_exit(self, lib):
        """When the client exits try to send refresh request to Kodi server.
        """
        self.update()

    def update(self, path=None):
        if path is None:
            self._log.info(u'Requesting a Kodi library update...')
        else:
            self._log.info(u'Requesting a Kodi update for {0}', path)

        # Try to send update request.
        try:
            r = update_kodi(
                config['kodi']['host'].get(),
                config['kodi']['port'].get(),
                config['kodi']['user'].get(),
                config['kodi']['pwd'].get(),
                path)
            r.raise_for_status()

        except requests.exceptions.RequestException as e:
            self._log.warning(u'Kodi update failed: {0}',
                              six.text_type(e))
            return

        json = r.json()
        if json.get('result') != 'OK':
            self._log.warning(u'Kodi update failed: JSON response was {0!r}',
                              json)
            return

        self._log.info(u'Kodi update triggered')
