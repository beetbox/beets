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
        url: https://mydomain.com:443/subsonic
        user: username
        pass: password
"""
from __future__ import division, absolute_import, print_function

import hashlib
import random
import string

import requests

from binascii import hexlify
from beets import config
from beets.plugins import BeetsPlugin

__author__ = 'https://github.com/maffo999'
AUTH_TOKEN_VERSION = (1, 12)


class SubsonicUpdate(BeetsPlugin):
    def __init__(self):
        super(SubsonicUpdate, self).__init__()
        # Set default configuration values
        config['subsonic'].add({
            'user': 'admin',
            'pass': 'admin',
            'url': 'http://localhost:4040',
        })
        config['subsonic']['pass'].redact = True
        self._version = None
        self._auth = None
        self.register_listener('import', self.start_scan)

    @property
    def version(self):
        if self._version is None:
            self._version = self.__get_version()
        return self._version

    @property
    def auth(self):
        if self._auth is None:
            if self.version is not None:
                if self.version > AUTH_TOKEN_VERSION:
                    self._auth = "token"
                else:
                    self._auth = "password"
            self._log.info(
                u"using '{}' authentication method".format(self._auth))
        return self._auth

    @staticmethod
    def __create_token():
        """Create salt and token from given password.

        :return: The generated salt and hashed token
        """
        password = config['subsonic']['pass'].as_str()

        # Pick the random sequence and salt the password
        r = string.ascii_letters + string.digits
        salt = "".join([random.choice(r) for _ in range(6)])
        salted_password = password + salt
        token = hashlib.md5(salted_password.encode('utf-8')).hexdigest()

        # Put together the payload of the request to the server and the URL
        return salt, token

    @staticmethod
    def __format_url(endpoint):
        """Get the Subsonic URL to trigger the given endpoint.
        Uses either the url config option or the deprecated host, port,
        and context_path config options together.

        :return: Endpoint for updating Subsonic
        """

        url = config['subsonic']['url'].as_str()
        if url and url.endswith('/'):
            url = url[:-1]

        # @deprecated("Use url config option instead")
        if not url:
            host = config['subsonic']['host'].as_str()
            port = config['subsonic']['port'].get(int)
            context_path = config['subsonic']['contextpath'].as_str()
            if context_path == '/':
                context_path = ''
            url = "http://{}:{}{}".format(host, port, context_path)

        return url + '/rest/{}'.format(endpoint)

    def __get_version(self):
        url = self.__format_url("ping.view")
        payload = {
            'c': 'beets',
            'f': 'json'
        }
        try:
            response = requests.get(url, params=payload)
            if response.status_code == 200:
                json = response.json()
                version = json['subsonic-response']['version']
                self._log.info(
                    u'subsonic version:{0} '.format(version))
                return tuple(int(s) for s in version.split('.'))
            else:
                self._log.error(u'Error: {0}', json)
                return None
        except Exception as error:
            self._log.error(u'Error: {0}'.format(error))
            return None

    def start_scan(self):
        user = config['subsonic']['user'].as_str()
        url = self.__format_url("startScan.view")

        if self.auth == 'token':
            salt, token = self.__create_token()
            payload = {
                'u': user,
                't': token,
                's': salt,
                'v': self.version,  # Subsonic 6.1 and newer.
                'c': 'beets',
                'f': 'json'
            }
        elif self.auth == 'password':
            password = config['subsonic']['pass'].as_str()
            encpass = hexlify(password.encode()).decode()
            payload = {
                'u': user,
                'p': 'enc:{}'.format(encpass),
                'v': self.version,
                'c': 'beets',
                'f': 'json'
            }
        else:
            return
        try:
            response = requests.get(url, params=payload)
            json = response.json()

            if response.status_code == 200 and \
                    json['subsonic-response']['status'] == "ok":
                count = json['subsonic-response']['scanStatus']['count']
                self._log.info(
                    u'Updating Subsonic; scanning {0} tracks'.format(count))
            elif response.status_code == 200 and \
                    json['subsonic-response']['status'] == "failed":
                error_message = json['subsonic-response']['error']['message']
                self._log.error(u'Error: {0}'.format(error_message))
            else:
                self._log.error(u'Error: {0}', json)
        except Exception as error:
            self._log.error(u'Error: {0}'.format(error))
