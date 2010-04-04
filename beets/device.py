import gpod
import os
import sys
import socket
import locale

def start_sync(pod):
    # Make sure we have a version of libgpod with these
    # iPhone-specific functions.
    if hasattr(gpod, 'itdb_start_sync'):
        gpod.itdb_start_sync(pod._itdb)
def stop_sync(pod):
    if hasattr(gpod, 'itdb_stop_sync'):
        gpod.itdb_stop_sync(pod._itdb)

def pod_path(name):
    #FIXME: os.path.expanduser('~') to get $HOME is hacky!
    return os.path.join(os.path.expanduser('~'), '.gvfs', name)

def get_pod(path):
    return gpod.Database(path)

def add(pod, items):
    def cbk(db, track, it, total):
        print 'copying', track
    start_sync(pod)
    try:
        for item in items:
            track = pod.new_Track()
            track['userdata'] = {
                'transferred': 0,
                'hostname': socket.gethostname(),
                'charset': locale.getpreferredencoding(),
                'pc_mtime': os.stat(item.path).st_mtime,
            }
            track._set_userdata_utf8('filename', item.path.encode())
            track['artist'] = item.artist
            track['title'] = item.title
            track['BPM'] = item.bpm
            track['genre'] = item.genre
            track['album'] = item.album
            track['cd_nr'] = item.disc
            track['cds'] = item.disctotal
            track['track_nr'] = item.track
            track['tracks'] = item.tracktotal
            track['tracklen'] = int(item.length * 1000)
        pod.copy_delayed_files(cbk)
    finally:
        pod.close()
        stop_sync(pod)

