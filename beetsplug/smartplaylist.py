from __future__ import print_function

from beets.plugins import BeetsPlugin
from beets import config, ui
from beets.util import normpath, syspath
import os

database_changed = False
library = None


def update_playlists(lib):
    print("Updating smart playlists...")
    playlists = config['smartplaylist']['playlists'].get(list)
    playlist_dir = config['smartplaylist']['playlist_dir'].get(unicode)
    relative_to = config['smartplaylist']['relative_to'].get()
    if relative_to:
        relative_to = normpath(relative_to)

    for playlist in playlists:
        items = lib.items(playlist['query'])
        if relative_to:
            paths = [os.path.relpath(item.path, relative_to) for item in items]
        else:
            paths = [item.path for item in items]
        basename = playlist['name'].encode('utf8')
        m3u_path = os.path.join(playlist_dir, basename)
        with open(syspath(m3u_path), 'w') as f:
            for path in paths:
                f.write(path + '\n')
    print("... Done")


class SmartPlaylistPlugin(BeetsPlugin):
    def __init__(self):
        super(SmartPlaylistPlugin, self).__init__()
        self.config.add({
            'relative_to': None,
            'playlists': []
        })

    def commands(self):
        def update(lib, opts, args):
            update_playlists(lib)
        spl_update = ui.Subcommand('spl_update',
            help='update the smart playlists')
        spl_update.func = update
        return [spl_update]


@SmartPlaylistPlugin.listen('database_change')
def handle_change(lib):
    global library
    global database_changed
    library = lib
    database_changed = True


@SmartPlaylistPlugin.listen('cli_exit')
def update():
    if database_changed:
        update_playlists(library)
