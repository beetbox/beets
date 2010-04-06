# This file is part of beets.
# Copyright 2009, Adrian Sampson.
# 
# Beets is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Beets is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with beets.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import socket
import locale
import gpod
from beets.library import BaseLibrary, Item

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

class PodLibrary(BaseLibrary):
    def __init__(self, path):
        self.db = gpod.Database(path)
        self.syncing = False
    # Browsing convenience.
    def artists(self, query=None):
        raise NotImplementedError

    def albums(self, artist=None, query=None):
        raise NotImplementedError

    def items(self, artist=None, album=None, title=None, query=None):
        raise NotImplementedError
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
        raise NotImplementedError

    def save(self):
        self._stop_sync()
        gpod.itdb_write(self.db._itdb, None)

    def load(self, item, load_id=None):
        raise NotImplementedError

    def store(self, item, store_id=None, store_all=False):
        raise NotImplementedError

    def remove(self, item):
        raise NotImplementedError

