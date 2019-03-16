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

from beets.plugins import BeetsPlugin
from beets import config
import requests
import string
import hashlib
import random

__author__ = 'https://github.com/maffo999'


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
        })
        config['subsonic']['pass'].redact = True
        self.register_listener('import', self.loaded)

    def loaded(self):
        host = config['subsonic']['host'].as_str()
        port = config['subsonic']['port'].get(int)
        user = config['subsonic']['user'].as_str()
        passw = config['subsonic']['pass'].as_str()
        contextpath = config['subsonic']['contextpath'].as_str()

        # To avoid sending plaintext passwords, authentication will be
        # performed via username, a token, and a 6 random
        # letters/numbers sequence.
        # The token is the concatenation of your password and the 6 random
        # letters/numbers (the salt) which is hashed with MD5.

        # Pick the random sequence and salt the password
        r = string.ascii_letters + string.digits
        salt = "".join([random.choice(r) for n in range(6)])
        t = passw + salt
        token = hashlib.md5()
        token.update(t.encode('utf-8'))

        # Put together the payload of the request to the server and the URL
        payload = {
            'u': user,
            't': token.hexdigest(),
            's': salt,
            'v': '1.15.0',  # Subsonic 6.1 and newer.
            'c': 'beets'
        }
        if contextpath == '/':
            contextpath = ''
        url = "http://{}:{}{}/rest/startScan".format(host, port, contextpath)
        response = requests.post(url, params=payload)

        if response.status_code != 200:
            self._log.error(u'Generic error, please try again later.')
