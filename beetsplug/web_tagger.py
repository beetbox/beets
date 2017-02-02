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

"""Runs a local HTTP server for MusicBrainz web tagger and handles
users' requests.
"""

from __future__ import division, absolute_import, print_function

import socket
import webbrowser
from io import BytesIO
from six.moves.urllib_parse import urlparse, urlencode, parse_qs
from six.moves.BaseHTTPServer import BaseHTTPRequestHandler
from beets import autotag
from beets.plugins import BeetsPlugin
from beets.ui.commands import PromptChoice
from beets import config
from beets import ui

PORT = config['mbweb']['port'].as_number()


# Simple HTTP parser
class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        self.rfile = BytesIO(request_text)
        self.raw_requestline = self.rfile.readline()
        self.parse_request()


# Get 'id' parameter from URI
def parse(data):
    r = HTTPRequest(data)
    parsed = urlparse(r.path)
    return parse_qs(parsed.query)['id'][0]


class Server(object):
    def __init__(self):
        self.host = '127.0.0.1'
        self.port = PORT
        try:  # Start TCP socket, catch soket.error
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET,
                                       socket.SO_REUSEADDR, 1)
            self.sock.bind((self.host, self.port))
        except socket.error as error_msg:
            print("Error occurred: {0}".format(error_msg))

    def listen(self, size=1024):
        self.sock.listen(1)
        while True:
            con, addr = self.sock.accept()
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

    def prompt(self, session, task):
        return [PromptChoice('l', 'Lookup', self.choice)]

    def choice(self, session, task):
        url = 'http://musicbrainz.org/taglookup?{0}'
        query = {'tport': self.port,
                 'artist': '',
                 'track': '',
                 'release': '',
                 }
        prompt = u"Choose your {0} and click 'tagger' button to add." \
        .format(u'album' if task.is_album else u'track')
        ui.print_(prompt)
        if task.is_album:
            query['artist'] = task.cur_artist
            query['release'] = task.cur_album
            webbrowser.open(url.format(urlencode(query)))
            id_choice = self.server.listen()
            _, _, proposal = autotag.tag_album(task.items,
                                               search_ids=id_choice)
            return proposal
        else:
            query['artist'] = task.item.artist
            query['track'] = task.item.title
            webbrowser.open(url.format(urlencode(query)))
            id_choice = self.server.listen()
            return autotag.tag_item(task.item, search_ids=id_choice)
