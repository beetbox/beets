# -*- coding: utf-8 -*-
# Subsonic plugin for Beets
# Allows to trigger a library scan on Subsonic
# after music has been imported with Beets
# Your Beets configuration file should contain
# a subsonic section like the following:
#   subsonic:
#       host: 192.168.x.y (the IP address where Subsonic listens on)
#       port: 4040 (default)
#       user: <your username>
#       pass: <your password>
# Plugin wrote by maffo999

"""Updates Subsonic library on Beets import
"""
from __future__ import division, absolute_import, print_function

from beets.plugins import BeetsPlugin
import requests
import string
import hashlib
import random


class Subsonic(BeetsPlugin):
    def __init__(self):
        super(Subsonic, self).__init__()
        self.register_listener('import', self.loaded)

    def loaded(self):
        host = self.config['host'].get()
        port = self.config['port'].get()
        user = self.config['user'].get()
        passw = self.config['pass'].get()
        r = string.ascii_letters + string.digits
        url = "http://"+str(host)+":"+str(port)+"/rest/startScan"
        salt = "".join([random.choice(r) for n in range(6)])
        t = passw + salt
        token = hashlib.md5()
        token.update(t.encode('utf-8'))
        payload = {
            'u': user,
            't': token.hexdigest(),
            's': salt,
            'v': '1.15.0',
            'c': 'beets'
            }
        response = requests.post(url, params=payload)
        if (response.status_code == 0):
            self._log.error(u'Generic error, please try again later.')
            print("Generic error, please try again later.")
        elif (response.status_code == 30):
            self._log.error(u'Subsonic server not compatible with plugin.')
            print("Subsonic server not compatible with plugin.")
        elif (response.status_code == 40):
            self._log.error(u'Wrong username or password.')
            print("Wrong username or password.")
        elif (response.status_code == 50):
            self._log.error(u'User not allowed to perform the operation.')
            print("User not allowed to perform the requested operation.")
        elif (response.status_code == 60):
            self._log.error(u'This feature requires Subsonic Premium.')
            print("This feature requires Subsonic Premium.")
        elif (response.status_code == 200):
            self._log.info('Operation completed successfully!')
            print("Operation completed successfully!")
        else:
            self._log.error(u'Unknown error code returned from server.')
            print("Unknown error code returned from server.")
