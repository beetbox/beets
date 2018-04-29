# -*- coding: utf-8 -*-
# This file is part of beets.
# Copyright 2017, Tigran Kostandyan.
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

"""Upload files to Google Play Music and list songs in its library."""

from __future__ import absolute_import, division, print_function
import os.path

from beets.plugins import BeetsPlugin
from beets import ui
from beets import config
from beets.ui import Subcommand
from gmusicapi import Musicmanager, Mobileclient
from gmusicapi.exceptions import NotLoggedIn
import gmusicapi.clients


class Gmusic(BeetsPlugin):
    def __init__(self):
        super(Gmusic, self).__init__()
        # Checks for OAuth2 credentials,
        # if they don't exist - performs authorization
        self.m = Musicmanager()
        if os.path.isfile(gmusicapi.clients.OAUTH_FILEPATH):
            self.m.login()
        else:
            self.m.perform_oauth()

    def commands(self):
        gupload = Subcommand('gmusic-upload',
                             help=u'upload your tracks to Google Play Music')
        gupload.func = self.upload

        search = Subcommand('gmusic-songs',
                            help=u'list of songs in Google Play Music library'
                            )
        search.parser.add_option('-t', '--track', dest='track',
                                 action='store_true',
                                 help='Search by track name')
        search.parser.add_option('-a', '--artist', dest='artist',
                                 action='store_true',
                                 help='Search by artist')
        search.func = self.search
        return [gupload, search]

    def upload(self, lib, opts, args):
        items = lib.items(ui.decargs(args))
        files = [x.path.decode('utf-8') for x in items]
        ui.print_(u'Uploading your files...')
        self.m.upload(filepaths=files)
        ui.print_(u'Your files were successfully added to library')

    def search(self, lib, opts, args):
        password = config['gmusic']['password']
        email = config['gmusic']['email']
        password.redact = True
        email.redact = True
        # Since Musicmanager doesn't support library management
        # we need to use mobileclient interface
        mobile = Mobileclient()
        try:
            mobile.login(email.as_str(), password.as_str(),
                         Mobileclient.FROM_MAC_ADDRESS)
            files = mobile.get_all_songs()
        except NotLoggedIn:
            ui.print_(
                u'Authentication error. Please check your email and password.'
            )
            return
        if not args:
            for i, file in enumerate(files, start=1):
                print(i, ui.colorize('blue', file['artist']),
                      file['title'], ui.colorize('red', file['album']))
        else:
            if opts.track:
                self.match(files, args, 'title')
            else:
                self.match(files, args, 'artist')

    @staticmethod
    def match(files, args, search_by):
        for file in files:
            if ' '.join(ui.decargs(args)) in file[search_by]:
                print(file['artist'], file['title'], file['album'])
