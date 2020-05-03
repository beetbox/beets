# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2016, Adrian Sampson.
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

"""Updates Subsonic library on Beets import
Your Beets configuration file should contain
a "subsonic" section like the following:
    subsonic:
        host: 192.168.x.y (Subsonic server IP)
        port: 4040 (default)
        user: <your username>
        pass: <your password>
        contextpath: /subsonic
"""
from __future__ import division, absolute_import, print_function

import hashlib
import random
import string

import requests

from beets import config
from beets.plugins import BeetsPlugin

__author__ = 'https://github.com/maffo999'


def create_token():
    """Create salt and token from given password.

    :return: The generated salt and hashed token
    """
    password = config['subsonic']['pass'].as_str()

    # Pick the random sequence and salt the password
    r = string.ascii_letters + string.digits
    salt = "".join([random.choice(r) for _ in range(6)])
    salted_password = password + salt
    token = hashlib.md5().update(salted_password.encode('utf-8')).hexdigest()

    # Put together the payload of the request to the server and the URL
    return salt, token


def format_url():
    """Get the Subsonic URL to trigger a scan. Uses either the url
    config option or the deprecated host, port, and context_path config
    options together.

    :return: Endpoint for updating Subsonic
    """

    url = config['subsonic']['url'].as_str()
    if url and url.endsWith('/'):
        url = url[:-1]

    # @deprecated("Use url config option instead")
    if not url:
        host = config['subsonic']['host'].as_str()
        port = config['subsonic']['port'].get(int)
        context_path = config['subsonic']['contextpath'].as_str()
        if context_path == '/':
            context_path = ''
        url = "http://{}:{}{}".format(host, port, context_path)

    return url + '/rest/startScan'


class SubsonicUpdate(BeetsPlugin):
    def __init__(self):
        super(SubsonicUpdate, self).__init__()

        # Set default configuration values
        config['subsonic'].add({
            'host': 'localhost',
            'port': '4040',
            'user': 'admin',
            'pass': 'admin',
            'contextpath': '/',
            'url': 'http://localhost:4040',
        })

        config['subsonic']['pass'].redact = True
        self.register_listener('import', self.start_scan)

    def start_scan(self):
        user = config['subsonic']['user'].as_str()
        url = format_url()
        salt, token = create_token()

        payload = {
            'u': user,
            't': token,
            's': salt,
            'v': '1.15.0',  # Subsonic 6.1 and newer.
            'c': 'beets'
        }

        response = requests.post(url, params=payload)

        if response.status_code == 403:
            self._log.error(u'Server authentication failed')
        elif response.status_code == 200:
            self._log.debug(u'Updating Subsonic')
        else:
            self._log.error(
                u'Generic error, please try again later [Status Code: {}]'
                .format(response.status_code))
