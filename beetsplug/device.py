# This file is part of beets.
# Copyright 2010, Adrian Sampson.
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

import os
import sys
import socket
import locale
import gpod

from beets.library import BaseLibrary, Item
from beets.plugins import BeetsPlugin
import beets.ui

FIELD_MAP = {
    'artist':   'artist',
    'title':    'title',
    'BPM':      'bpm',
    'genre':    'genre',
    'album':    'album',
    'cd_nr':    'disc',
    'cds':      'disctotal',
    'track_nr': 'track',
    'tracks':   'tracktotal',
}

def track_to_item(track):
    data = {}
    for dname, bname in FIELD_MAP.items():
        data[bname] = track[dname]
    data['length'] = float(track['tracklen']) / 1000
    data['path'] = track.ipod_filename()
    return Item(data)

class PodLibrary(BaseLibrary):
    def __init__(self, path):
        self.db = gpod.Database(path)
        self.syncing = False
    
    @classmethod
    def by_name(cls, name):
        return cls(os.path.join(os.path.expanduser('~'), '.gvfs', name))

    def _start_sync(self):
        # Make sure we have a version of libgpod with these
        # iPhone-specific functions.
        if self.syncing:
            return
        if hasattr(gpod, 'itdb_start_sync'):
            gpod.itdb_start_sync(self.db._itdb)
        self.syncing = True

    def _stop_sync(self):
        if not self.syncing:
            return
        if hasattr(gpod, 'itdb_stop_sync'):
            gpod.itdb_stop_sync(self.db._itdb)
        self.syncing = False

    def add(self, item):
        self._start_sync()
        track = self.db.new_Track()
        track['userdata'] = {
            'transferred': 0,
            'hostname': socket.gethostname(),
            'charset': locale.getpreferredencoding(),
            'pc_mtime': os.stat(item.path).st_mtime,
        }
        track._set_userdata_utf8('filename', item.path.encode())
        for dname, bname in FIELD_MAP.items():
            track[dname] = getattr(item, bname)
        track['tracklen'] = int(item.length * 1000)
        self.db.copy_delayed_files()

    def get(self, query=None):
        query = self._get_query(query)
        for track in self.db:
            item = track_to_item(track)
            if query.match(item):
                yield item

    def save(self):
        self._stop_sync()
        gpod.itdb_write(self.db._itdb, None)

    def load(self, item, load_id=None):
        raise NotImplementedError

    def store(self, item, store_id=None, store_all=False):
        raise NotImplementedError

    def remove(self, item):
        raise NotImplementedError


# Plugin hook.

class DevicePlugin(BeetsPlugin):
    def commands(self):
        cmd = beets.ui.Subcommand('dadd', help='add files to a device')
        def func(lib, config, opts, args):
            if not args:
                raise beets.ui.UserError('no device name specified')
            name = args.pop(0)
            
            items = lib.items(query=beets.ui.make_query(args))
            pod = PodLibrary.by_name(name)
            for item in items:
                pod.add(item)
            pod.save()
        cmd.func = func
        return [cmd]
