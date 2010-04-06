import gpod
import os
import sys
import socket
import locale
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

    @classmethod
    def by_name(cls, name):
        return cls(os.path.join(os.path.expanduser('~'), '.gvfs', name))

    def _start_sync(self):
        # Make sure we have a version of libgpod with these
        # iPhone-specific functions.
        if hasattr(gpod, 'itdb_start_sync'):
            gpod.itdb_start_sync(self.db._itdb)

    def _stop_sync(self):
        if hasattr(gpod, 'itdb_stop_sync'):
            gpod.itdb_stop_sync(self.db._itdb)
    
    def add_items(self, items):
        self._start_sync()
        try:
            for item in items:
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
        finally:
            self.db.close()
            self._stop_sync()

    def add(self, path):
        raise NotImplementedError

    def get(self, query=None):
        raise NotImplementedError

    def save(self):
        raise NotImplementedError

    # Browsing convenience.
    def artists(self, query=None):
        raise NotImplementedError

    def albums(self, artist=None, query=None):
        raise NotImplementedError

    def items(self, artist=None, album=None, title=None, query=None):
        raise NotImplementedError

