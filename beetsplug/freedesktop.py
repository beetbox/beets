from beets.plugins import BeetsPlugin
from beets.ui import Subcommand

from beets.ui import decargs

import os.path
import logging

log = logging.getLogger('beets.freedesktop')

freedesktop_command = Subcommand("freedesktop", help="Create .directory files")


def process_query(lib, opts, args):
    for album in lib.albums(decargs(args)):
        process_album(album)


def process_album(album):
    albumpath = album.item_dir()
    if album.artpath:
        fullartpath = album.artpath
        artfile = os.path.split(fullartpath)[1]
        create_file(albumpath, artfile)
    else:
        log.debug(u'freedesktop: album has no art')


def create_file(albumpath, artfile):
    file_contents = "[Desktop Entry]\nIcon=./" + artfile
    outfilename = os.path.join(albumpath, ".directory")

    if not os.path.exists(outfilename):
        file = open(outfilename, 'w')
        file.write(file_contents)
        file.close()
    pass


freedesktop_command.func = process_query


class FreedesktopPlugin(BeetsPlugin):
    """Creates freedesktop.org-compliant .directory files on an album level.
    """
    def __init__(self):
        super(FreedesktopPlugin, self).__init__()
        self.config.add({
            'auto': False
        })
        global automatic
        automatic = self.config['auto'].get(bool)

    def commands(self):
        return [freedesktop_command]


@FreedesktopPlugin.listen('album_imported')
def imported(lib, album):
    if not automatic:
        return
    process_album(album)
