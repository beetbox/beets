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
        self.m = Musicmanager()
        self.config.add({
            u'auto': False,
            u'uploader_id': '',
            u'uploader_name': '',
            u'device_id': '',
            u'oauth_file': gmusicapi.clients.OAUTH_FILEPATH,
        })
        if self.config['auto']:
            self.import_stages = [self.autoupload]

    def commands(self):
        gupload = Subcommand('gmusic-upload',
                             help=u'upload your tracks to Google Play Music')
        gupload.func = self.upload

        search = Subcommand('gmusic-songs',
                            help=u'list of songs in Google Play Music library')
        search.parser.add_option('-t', '--track', dest='track',
                                 action='store_true',
                                 help='Search by track name')
        search.parser.add_option('-a', '--artist', dest='artist',
                                 action='store_true',
                                 help='Search by artist')
        search.func = self.search
        return [gupload, search]

    def authenticate(self):
        if self.m.is_authenticated():
            return
        # Checks for OAuth2 credentials,
        # if they don't exist - performs authorization
        oauth_file = self.config['oauth_file'].as_str()
        if os.path.isfile(oauth_file):
            uploader_id = self.config['uploader_id']
            uploader_name = self.config['uploader_name']
            self.m.login(oauth_credentials=oauth_file,
                         uploader_id=uploader_id.as_str().upper() or None,
                         uploader_name=uploader_name.as_str() or None)
        else:
            self.m.perform_oauth(oauth_file)

    def upload(self, lib, opts, args):
        items = lib.items(ui.decargs(args))
        files = self.getpaths(items)
        self.authenticate()
        ui.print_(u'Uploading your files...')
        self.m.upload(filepaths=files)
        ui.print_(u'Your files were successfully added to library')

    def autoupload(self, session, task):
        items = task.imported_items()
        files = self.getpaths(items)
        self.authenticate()
        self._log.info(u'Uploading files to Google Play Music...', files)
        self.m.upload(filepaths=files)
        self._log.info(u'Your files were successfully added to your '
                       + 'Google Play Music library')

    def getpaths(self, items):
        return [x.path for x in items]

    def search(self, lib, opts, args):
        password = config['gmusic']['password']
        email = config['gmusic']['email']
        uploader_id = config['gmusic']['uploader_id']
        device_id = config['gmusic']['device_id']
        password.redact = True
        email.redact = True
        # Since Musicmanager doesn't support library management
        # we need to use mobileclient interface
        mobile = Mobileclient()
        try:
            new_device_id = (device_id.as_str()
                             or uploader_id.as_str().replace(':', '')
                             or Mobileclient.FROM_MAC_ADDRESS).upper()
            mobile.login(email.as_str(), password.as_str(), new_device_id)
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
