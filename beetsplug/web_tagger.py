# -*- coding: utf-8 -*-
# Copyright 2016, Tigran Kostandyan <t.kostandyan1@gmail.com>
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

""" Runs local http server for MusicBrainz web tagger and handles users' requests """

from __future__ import division, absolute_import, print_function

import threading
import socket
import webbrowser
try:
    import urllib.parse as urlparse
    from urllib.parse import urlencode
except ImportError: # python 2 support
    import urlparse
    from urlparse import urlparse
from beets.plugins import BeetsPlugin
from beets.ui.commands import PromptChoice
from beets import ui
from beets import autotag

PORT = 8000


def parse(data):
    data = data.splitlines()
    s = data[0].decode()
    url = ''
    for char in s[5:]:
        if char != ' ':
            url += char
        else:
            break
    parsed = urlparse.urlparse(url)
    return str(urlparse.parse_qs(parsed.query)['id'][0])


class Server(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.host = '127.0.0.1'
        self.port = PORT
        try:  # Start TCP socket, catch soket.error
            self.run_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.run_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.run_server.bind((self.host, self.port))
        except socket.error as error_msg:
            print("Error occurred: {0}".format(error_msg))

    def listen(self, size=1024):
        self.run_server.listen(5)
        while True:
            con, addr = self.run_server.accept()
            while True:
                data = con.recv(size)
                con.send(data)
                if not data:
                    break
                return parse(data)


class MBWeb(BeetsPlugin):
    def __init__(self):
        super(MBWeb, self).__init__()
        self.port = PORT
        self.register_listener('before_choose_candidate', self.prompt)
        self.server = Server()
        self.server.start()
        self.server.join()

    def prompt(self, session, task):
        return [PromptChoice('l', 'Lookup', self.choice)]

    def choice(self, session, task):
        artist = ui.input_('Artist:')
        realise = ui.input_('Album:')
        track = ui.input_('Track:')
        if not (artist, realise, track):
            ui.print_('Please, fill the search query')
            return self.prompt
        else:
            query = {'tport': self.port,
                     'artist': artist,
                     'track': track,
                     'realise': realise,
                     }
            url = 'http://musicbrainz.org/taglookup?{0}'.format(urlencode(query))
            ui.print_("Choose your tracks and click 'tagger' button to add:")
            webbrowser.open(url)
            id_choice = self.server.listen()
            if task.is_album:
                _, _, proposal, _ = autotag.tag_album(task.items, search_ids=id_choice)
                return proposal
            else:
                return autotag.tag_item(task.item, search_ids=id_choice)
